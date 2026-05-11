
"""
历史行情数据获取与缓存层
========================
L1 大盘指数（7个宽基，必拉）
L2 行业板块（~90个，必拉）
L3 概念板块（~400个，按需）
L4 ETF（宽基+行业必拉，主题按需）
L5 个股（纯按需）
L6 市场情绪（P1后）
"""

import akshare as ak
import time
import pandas as pd
from datetime import date, datetime, timedelta
from sqlalchemy import func
from typing import Literal

from database import SessionLocal
from models import AssetMeta, HistQuotesCache, AssetSectorMapping

# ── 限速 ──────────────────────────────────────────────
_MIN_INTERVAL = 1.0  # 秒，同一标的连续调用间隔

# ── 进度追踪 ──────────────────────────────────────────
_sync_progress = {
    "active": False,
    "task": "",           # 当前任务描述
    "current": 0,         # 当前进度
    "total": 0,           # 总任务数
    "current_code": "",   # 当前正在处理的代码
    "message": "",        # 状态消息
}

def get_sync_progress() -> dict:
    """获取当前同步进度"""
    return _sync_progress.copy()

def _set_progress(task: str, current: int, total: int, current_code: str = "", message: str = ""):
    """设置进度状态"""
    _sync_progress["active"] = True
    _sync_progress["task"] = task
    _sync_progress["current"] = current
    _sync_progress["total"] = total
    _sync_progress["current_code"] = current_code
    _sync_progress["message"] = message

def _clear_progress():
    """清除进度状态"""
    _sync_progress["active"] = False
    _sync_progress["task"] = ""
    _sync_progress["current"] = 0
    _sync_progress["total"] = 0
    _sync_progress["current_code"] = ""
    _sync_progress["message"] = "空闲"


# ══════════════════════════════════════════════════════
# 基础行情拉取（akshare 封装）
# ══════════════════════════════════════════════════════

def _ak_index_daily(symbol: str, start: str, end: str) -> pd.DataFrame | None:
    """拉取指数日线（000/399开头走 stock_zh_index_daily，全量拉取后截取）"""
    try:
        # stock_zh_index_daily 只接受 symbol，无日期参数，拉全量后截取
        # 399 开头走 sz，其余走 sh
        ak_symbol = f"sz{symbol}" if symbol.startswith("399") else f"sh{symbol}"
        df = ak.stock_zh_index_daily(symbol=ak_symbol)
        if df is None or df.empty:
            return None
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        # start/end 传入的是 %Y%m%d 格式，转换为 %Y-%m-%d 以便比较
        start_fmt = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
        end_fmt = f"{end[:4]}-{end[4:6]}-{end[6:8]}"
        df = df[(df["date"] >= start_fmt) & (df["date"] <= end_fmt)]
        if df.empty:
            return None
        # 计算 pct_change（akshare 指数接口不返回涨跌幅）
        df["pct_change"] = df["close"].pct_change() * 100
        # turnover 不存在，设为 NaN
        if "turnover" not in df.columns:
            df["turnover"] = None
        return df
    except Exception as e:
        print(f"[index] {symbol} 拉取失败: {e}")
        return None


def _ak_stock_hist(symbol: str, start: str, end: str) -> pd.DataFrame | None:
    """拉取个股/ETF 日线（stock_zh_a_hist）"""
    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol, period="daily",
            start_date=start, end_date=end, adjust="qfq"
        )
        if df is None or df.empty:
            return None
        # akshare 返回中文列名
        col_map = {
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume",
            "成交额": "turnover", "涨跌幅": "pct_change",
        }
        df = df.rename(columns=col_map)
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        # 保证 pct_change 列存在
        if "pct_change" not in df.columns:
            df["pct_change"] = df["close"].pct_change() * 100
        if "turnover" not in df.columns:
            df["turnover"] = None
        if "volume" not in df.columns:
            df["volume"] = None
        return df
    except Exception as e:
        print(f"[stock] {symbol} 拉取失败: {e}")
        return None


def _ak_fund_nav_hist(symbol: str, start: str, end: str) -> pd.DataFrame | None:
    """拉取开放式基金净值历史"""
    try:
        df = ak.fund_open_fund_info_em(symbol=symbol, indicator="单位净值走势")
        if df is None or df.empty:
            return None
        df["date"] = pd.to_datetime(df["净值日期"]).dt.strftime("%Y-%m-%d")
        mask = (df["date"] >= start) & (df["date"] <= end)
        df = df[mask]
        df["open"] = df["单位净值"].astype(float)
        df["close"] = df["单位净值"].astype(float)
        df["high"] = df["单位净值"].astype(float)
        df["low"] = df["单位净值"].astype(float)
        df["pct_change"] = df["close"].pct_change() * 100
        return df
    except Exception as e:
        print(f"[fund] {symbol} 拉取失败: {e}")
        return None


def _ak_sector_industry() -> pd.DataFrame | None:
    """拉取东方财富行业板块列表（带重试）
    注意：板块历史行情接口 stock_board_industry_hist_em 需要板块名称，
    所以 code 字段存板块名称，拉历史时直接用 code 即可。
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            df = ak.stock_board_industry_name_em()
            if df is None or df.empty:
                return None
            # 东方财富返回含 '板块名称' 列
            if "板块名称" in df.columns:
                result = df[["板块名称"]].copy()
                result.columns = ["name"]
                result["code"] = result["name"]  # code = name
                return result[["code", "name"]]
            return None
        except Exception as e:
            print(f"[sector] 行业板块列表拉取失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避: 1s, 2s, 4s
            else:
                return None


def _ak_sector_concept() -> pd.DataFrame | None:
    """拉取东方财富概念板块列表（带重试）
    注意：概念板块历史行情接口需要板块名称，code = name。
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            df = ak.stock_board_concept_name_em()
            if df is None or df.empty:
                return None
            if "板块名称" in df.columns:
                result = df[["板块名称"]].copy()
                result.columns = ["name"]
                result["code"] = result["name"]
                return result[["code", "name"]]
            return None
        except Exception as e:
            print(f"[sector] 概念板块列表拉取失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None


def _ak_sector_hist(code: str, start: str, end: str) -> pd.DataFrame | None:
    """拉取板块历史行情（东方财富）
    注意：stock_board_industry_hist_em 需要板块名称而非代码。
    此处先尝试用 code 当名称拉，失败则查 asset_meta 获取名称再试。
    """
    # 尝试1：直接用 code 作为名称
    df = _try_sector_hist(code, start, end)
    if df is not None:
        return df

    # 尝试2：从 asset_meta 查名称
    name = _get_name_from_cache(code)
    if name and name != code:
        df = _try_sector_hist(name, start, end)
        if df is not None:
            return df

    return None


def _try_sector_hist(symbol: str, start: str, end: str, max_retries: int = 2) -> pd.DataFrame | None:
    """尝试拉取板块历史行情（带重试）"""
    for attempt in range(max_retries):
        try:
            df = ak.stock_board_industry_hist_em(
                symbol=symbol, period="日k",
                start_date=start, end_date=end, adjust=""
            )
            if df is None or df.empty:
                return None
            df["date"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")
            df = df.rename(columns={
                "开盘": "open", "收盘": "close", "最高": "high",
                "最低": "low", "成交量": "volume", "成交额": "turnover",
                "涨跌幅": "pct_change"
            })
            if "pct_change" not in df.columns:
                df["pct_change"] = df["close"].pct_change() * 100
            if "turnover" not in df.columns:
                df["turnover"] = None
            if "volume" not in df.columns:
                df["volume"] = None
            return df[["date", "open", "close", "high", "low", "volume", "turnover", "pct_change"]]
        except Exception as e:
            err_msg = str(e)
            print(f"[sector] {symbol} 拉取失败 (尝试 {attempt+1}/{max_retries}): {err_msg[:100]}")
            if attempt < max_retries - 1:
                # 东方财富限流时增加较长等待
                if "RemoteDisconnected" in err_msg or "Connection" in err_msg:
                    _set_progress("L2行业板块同步", _sync_progress.get("current", 0), _sync_progress.get("total", 0), symbol, f"{symbol} 被限流，等待5秒后重试...")
                    time.sleep(5)
                else:
                    time.sleep(2)
            else:
                # 最终失败时更新进度显示错误
                _set_progress("L2行业板块同步", _sync_progress.get("current", 0), _sync_progress.get("total", 0), symbol, f"{symbol} 拉取失败: {err_msg[:50]}")
                return None


# ══════════════════════════════════════════════════════
# 核心：数据拉取 + 增量写入
# ══════════════════════════════════════════════════════

def _fetch_and_cache(
    db,
    code: str,
    asset_type: str,
    start_date: date,
    end_date: date,
) -> int:
    """
    拉取指定标的的历史行情并写入 hist_quotes_cache。
    自动判断增量：只拉 DB 中不存在的日期区间。
    返回新增记录数，0 表示无新增（或拉取失败）。
    """
    s_start = start_date.strftime("%Y%m%d")
    s_end   = end_date.strftime("%Y%m%d")

    # ── 判断已有数据范围 ──────────────────────────────
    existing = db.query(func.min(HistQuotesCache.date), func.max(HistQuotesCache.date)).filter(
        HistQuotesCache.code == code
    ).one_or_none()

    if existing and existing[0] and existing[1]:
        db_min, db_max = existing[0], existing[1]
        # 确定实际需要拉的区间（与请求区间取并集）
        target_start = min(start_date, db_min)
        target_end   = max(end_date, db_max)
        # 若请求区间已在 DB 范围内且够新（最近3天内），跳过
        if start_date >= db_min and end_date <= db_max and end_date >= date.today() - timedelta(days=3):
            return 0
        # 从 DB 已有范围之外开始拉
        s_start = (db_max + timedelta(days=1)).strftime("%Y%m%d")
        if s_start > s_end:
            return 0

    # ── 按资产类型拉取 ────────────────────────────────
    if asset_type == "index":
        df = _ak_index_daily(code, s_start, s_end)
    elif asset_type in ("sector_industry", "sector_concept"):
        df = _ak_sector_hist(code, s_start, s_end)
    elif asset_type == "fund":
        df = _ak_fund_nav_hist(code, s_start, s_end)
    else:  # stock / etf / default
        df = _ak_stock_hist(code, s_start, s_end)

    if df is None or df.empty:
        return 0

    # ── 写入 DB（upsert）───────────────────────────────
    saved = 0
    for _, row in df.iterrows():
        d = row["date"]
        if isinstance(d, str):
            d = datetime.strptime(d, "%Y-%m-%d").date()

        existing_row = db.query(HistQuotesCache).filter(
            HistQuotesCache.code == code,
            HistQuotesCache.date == d
        ).first()

        if existing_row:
            existing_row.open        = float(row["open"])  if pd.notna(row.get("open"))        else None
            existing_row.close       = float(row["close"])
            existing_row.high        = float(row["high"])  if pd.notna(row.get("high"))        else None
            existing_row.low         = float(row["low"])   if pd.notna(row.get("low"))         else None
            existing_row.volume      = float(row["volume"])if pd.notna(row.get("volume"))      else None
            existing_row.turnover    = float(row["turnover"])if pd.notna(row.get("turnover")) else None
            existing_row.pct_change  = float(row["pct_change"])if pd.notna(row.get("pct_change")) else None
        else:
            db.add(HistQuotesCache(
                code=code,
                date=d,
                open       = float(row["open"])        if pd.notna(row.get("open"))        else None,
                close      = float(row["close"]),
                high       = float(row["high"])        if pd.notna(row.get("high"))        else None,
                low        = float(row["low"])         if pd.notna(row.get("low"))          else None,
                volume     = float(row["volume"])       if pd.notna(row.get("volume"))       else None,
                turnover   = float(row["turnover"])   if pd.notna(row.get("turnover"))     else None,
                pct_change = float(row["pct_change"])  if pd.notna(row.get("pct_change"))   else None,
            ))
            saved += 1

    # ── 更新 asset_meta.is_cached ────────────────────
    meta = db.query(AssetMeta).filter(AssetMeta.code == code).first()
    if meta:
        meta.is_cached = 1
        meta.updated_at = datetime.now()

    return saved


# ══════════════════════════════════════════════════════
# 预定义标的清单
# ══════════════════════════════════════════════════════

# L1 大盘指数（7个宽基，必拉）
L1_INDEX_CODES = {
    "000001": "上证指数",
    "399001": "深证成指",
    "000300": "沪深300",
    "000905": "中证500",
    "000852": "中证1000",
    "399006": "创业板指",
    "000688": "科创50",
}

# L2 申万一级行业（31个）
L2_INDUSTRY_CODES = {
    # 申万一级行业指数，代码从 akshare sw_index_* 接口获取
    # 这里先放东方财富行业板块代码作为种子
}
# L3 概念板块：由 akshare 动态获取
# L4 ETF：宽基（必拉）+ 行业（按需）
L4_ETF_BROAD = {
    "510300": "沪深300ETF",
    "510500": "中证500ETF",
    "159915": "创业板ETF",
    "588000": "科创50ETF",
    "510050": "上证50ETF",
    "512880": "证券ETF",
    "512760": "芯片ETF",
    "515050": "5GETF",
    "515000": "科技ETF",
    "159928": "消费ETF",
    "512690": "酒ETF",
    "512660": "军工ETF",
    "512010": "医药ETF",
    "159825": "农业ETF",
    "515220": "煤炭ETF",
    "515790": "光伏ETF",
    "516110": "地产ETF",
    "512800": "银行ETF",
    "512200": "房地产ETF",
    "515030": "新能源车ETF",
}


# ══════════════════════════════════════════════════════
# 公开 API
# ══════════════════════════════════════════════════════

def sync_single(code: str, asset_type: str = "stock",
                start_date: date = None, end_date: date = None) -> dict:
    """
    拉取单个标的行情并缓存。
    asset_type: index / sector_industry / sector_concept / etf / stock / fund
    默认 5 年数据（指数/ETF 拉更长），传 None 表示拉取全部历史。
    返回 {"ok": bool, "saved": int, "message": str}
    """
    if not end_date:
        end_date = date.today()
    if not start_date:
        # 指数/ETF 拉 10 年，个股/板块拉 5 年
        days = 365 * 10 if asset_type in ("index", "etf") else 365 * 5
        start_date = end_date - timedelta(days=days)

    db = SessionLocal()
    try:
        saved = _fetch_and_cache(db, code, asset_type, start_date, end_date)
        # 确保元数据存在
        meta = db.query(AssetMeta).filter(AssetMeta.code == code).first()
        if not meta:
            name = _get_name_from_cache(code)
            db.add(AssetMeta(
                code=code,
                name=name or code,
                asset_type=asset_type,
                is_cached=1,
            ))
        db.commit()
        return {"ok": True, "saved": saved, "code": code}
    except Exception as e:
        return {"ok": False, "code": code, "message": str(e)}
    finally:
        db.close()


def sync_batch(codes: list[str], asset_type: str = "stock",
               start_date: date = None, end_date: date = None,
               task_name: str = "批量同步") -> dict:
    """
    批量拉取多个标的。
    start_date / end_date 可选，默认 5 年。
    返回汇总报告。
    """
    if not end_date:
        end_date = date.today()
    if not start_date:
        days = 365 * 10 if asset_type in ("index", "etf") else 365 * 5
        start_date = end_date - timedelta(days=days)

    results = []
    total_saved = 0
    total = len(codes)

    _set_progress(task_name, 0, total, "", f"开始{task_name}，共{total}个标的")

    # 板块类型增加间隔避免限流
    interval = 3.0 if asset_type in ("sector_industry", "sector_concept") else _MIN_INTERVAL
    
    for i, code in enumerate(codes):
        _set_progress(task_name, i + 1, total, code, f"正在同步 {code} ({i+1}/{total})")
        r = sync_single(code, asset_type)
        results.append(r)
        total_saved += r.get("saved", 0)
        time.sleep(interval)

    _clear_progress()

    return {
        "total": len(codes),
        "saved": total_saved,
        "results": results,
    }


def sync_l1_indexes() -> dict:
    """同步 L1 大盘指数（7个宽基，全部历史数据）"""
    codes = list(L1_INDEX_CODES.keys())

    # 逐个拉取全部历史（不限制日期范围）
    results = []
    total_saved = 0
    total = len(codes)

    _set_progress("L1宽基指数同步", 0, total, "", f"开始L1同步，共{total}个指数")

    for i, code in enumerate(codes):
        _set_progress("L1宽基指数同步", i + 1, total, code, f"正在同步 {code} ({i+1}/{total})")
        # 传 None 表示拉取全部历史
        r = sync_single(code, "index", start_date=None, end_date=None)
        results.append(r)
        total_saved += r.get("saved", 0)
        time.sleep(_MIN_INTERVAL)

    _clear_progress()

    # 补充元数据
    db = SessionLocal()
    try:
        for code, name in L1_INDEX_CODES.items():
            meta = db.query(AssetMeta).filter(AssetMeta.code == code).first()
            if not meta:
                db.add(AssetMeta(code=code, name=name, asset_type="index", category="宽基", is_cached=1))
            else:
                meta.name = name
                meta.asset_type = "index"
                meta.category = "宽基"
                meta.is_cached = 1
        db.commit()
    finally:
        db.close()

    return {
        "total": len(codes),
        "saved": total_saved,
        "results": results,
    }


def sync_l2_industry() -> dict:
    """同步 L2 行业板块（首次全量，后续增量）"""
    # 动态获取板块列表
    _set_progress("L2行业板块同步", 0, 1, "", "正在获取行业板块列表...")
    df = _ak_sector_industry()
    if df is None or df.empty:
        _set_progress("L2行业板块同步", 0, 1, "", "获取板块列表失败，请稍后重试")
        return {"ok": False, "message": "无法获取行业板块列表（网络问题或API限流）"}

    codes = df["code"].tolist()
    names = df["name"].tolist()

    # 批量拉取
    batch_result = sync_batch(codes, asset_type="sector_industry", task_name="L2行业板块同步")

    # 补充元数据
    db = SessionLocal()
    try:
        for code, name in zip(codes, names):
            meta = db.query(AssetMeta).filter(AssetMeta.code == code).first()
            if not meta:
                db.add(AssetMeta(code=code, name=name, asset_type="sector_industry", is_cached=1))
            else:
                meta.name = name
                meta.asset_type = "sector_industry"
                meta.is_cached = 1
        db.commit()
    finally:
        db.close()

    return batch_result


def sync_l3_concept() -> dict:
    """同步 L3 概念板块（首次全量，后续增量）"""
    # 动态获取板块列表
    _set_progress("L3概念板块同步", 0, 1, "", "正在获取概念板块列表...")
    df = _ak_sector_concept()
    if df is None or df.empty:
        _set_progress("L3概念板块同步", 0, 1, "", "获取板块列表失败，请稍后重试")
        return {"ok": False, "message": "无法获取概念板块列表（网络问题或API限流）"}

    codes = df["code"].tolist()
    names = df["name"].tolist()

    # 批量拉取
    batch_result = sync_batch(codes, asset_type="sector_concept", task_name="L3概念板块同步")

    # 补充元数据
    db = SessionLocal()
    try:
        for code, name in zip(codes, names):
            meta = db.query(AssetMeta).filter(AssetMeta.code == code).first()
            if not meta:
                db.add(AssetMeta(code=code, name=name, asset_type="sector_concept", is_cached=1))
            else:
                meta.name = name
                meta.asset_type = "sector_concept"
                meta.is_cached = 1
        db.commit()
    finally:
        db.close()

    return batch_result


def get_cache_status() -> dict:
    """返回缓存概况"""
    db = SessionLocal()
    try:
        # 按资产类型统计
        rows = db.query(
            AssetMeta.asset_type,
            AssetMeta.category,
            func.count(AssetMeta.code).label("count"),
            func.sum(AssetMeta.is_cached).label("cached"),
        ).group_by(AssetMeta.asset_type, AssetMeta.category).all()

        # 各标的最早/最新缓存日期
        date_ranges = db.query(
            HistQuotesCache.code,
            func.min(HistQuotesCache.date).label("min_date"),
            func.max(HistQuotesCache.date).label("max_date"),
            func.count(HistQuotesCache.id).label("row_count"),
        ).group_by(HistQuotesCache.code).all()
        date_ranges_dict = {
            r[0]: {"start": str(r[1]), "end": str(r[2]), "rows": r[3]}
            for r in date_ranges
        }

        # 已缓存的资产列表（含名称）
        cached_assets = db.query(AssetMeta).filter(AssetMeta.is_cached == 1).all()
        assets_list = [
            {
                "code": a.code,
                "name": a.name or "",
                "asset_type": a.asset_type,
                "category": a.category or "",
                "start": date_ranges_dict.get(a.code, {}).get("start"),
                "end": date_ranges_dict.get(a.code, {}).get("end"),
            }
            for a in cached_assets
        ]

        total_quotes = db.query(func.count(HistQuotesCache.id)).scalar()
        total_assets = db.query(func.count(AssetMeta.code)).scalar()
        cached_assets_count = db.query(func.count(AssetMeta.code)).filter(AssetMeta.is_cached == 1).scalar()

        return {
            "total_assets": total_assets or 0,
            "cached_assets": cached_assets_count or 0,
            "total_quotes": total_quotes or 0,
            "by_type": [
                {
                    "asset_type": r[0] or "unknown",
                    "category": r[1] or "",
                    "count": r[2] or 0,
                    "cached": r[3] or 0,
                }
                for r in rows
            ],
            "date_ranges": date_ranges_dict,
            "assets": assets_list,
        }
    finally:
        db.close()


def get_cached_data(
    code: str,
    start_date: date = None,
    end_date: date = None,
    fields: list[str] = None,
) -> pd.DataFrame:
    """
    从缓存读取历史数据，返回 DataFrame。
    start_date / end_date 可限定范围。
    fields 指定返回列，默认全部。
    """
    db = SessionLocal()
    try:
        q = db.query(HistQuotesCache).filter(HistQuotesCache.code == code)
        if start_date:
            q = q.filter(HistQuotesCache.date >= start_date)
        if end_date:
            q = q.filter(HistQuotesCache.date <= end_date)
        q = q.order_by(HistQuotesCache.date)

        rows = q.all()
        if not rows:
            return pd.DataFrame()

        data = [{
            "date": r.date,
            "open": r.open,
            "close": r.close,
            "high": r.high,
            "low": r.low,
            "volume": r.volume,
            "turnover": r.turnover,
            "pct_change": r.pct_change,
        } for r in rows]

        df = pd.DataFrame(data)
        if fields:
            df = df[["date"] + [f for f in fields if f != "date"]]
        return df
    finally:
        db.close()


def _get_name_from_cache(code: str) -> str | None:
    """从 asset_meta 查名称（不创建记录）"""
    db = SessionLocal()
    try:
        meta = db.query(AssetMeta).filter(AssetMeta.code == code).first()
        return meta.name if meta else None
    finally:
        db.close()
