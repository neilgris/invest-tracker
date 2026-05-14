
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
_MIN_INTERVAL = 5.0  # 秒，同一标的连续调用间隔（避免限流）

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
    """拉取申万一级行业指数列表（替代东方财富）
    申万指数更稳定，不会被限流
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            df = ak.sw_index_first_info()
            if df is None or df.empty:
                return None
            # 申万返回含 '行业代码' 和 '行业名称' 列
            if "行业代码" in df.columns and "行业名称" in df.columns:
                result = df[["行业代码", "行业名称"]].copy()
                result.columns = ["code", "name"]
                return result
            return None
        except Exception as e:
            print(f"[sector] 申万行业列表拉取失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
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
                time.sleep(5)  # 统一 5 秒间隔
            else:
                return None


def _ak_sector_hist(code: str, start: str, end: str) -> pd.DataFrame | None:
    """拉取申万行业指数历史行情（替代东方财富）"""
    return _try_sw_sector_hist(code, start, end)


def _try_sw_sector_hist(symbol: str, start: str, end: str, max_retries: int = 2) -> pd.DataFrame | None:
    """尝试拉取申万行业指数历史行情（带重试）"""
    for attempt in range(max_retries):
        try:
            # 申万指数接口：symbol 不需要 .SI 后缀
            symbol_clean = symbol.replace('.SI', '')
            df = ak.index_hist_sw(symbol=symbol_clean, period='day')
            if df is None or df.empty:
                return None

            # 列名映射（中文 -> 英文）
            df["date"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")
            df = df.rename(columns={
                "开盘": "open", "收盘": "close", "最高": "high",
                "最低": "low", "成交量": "volume", "成交额": "turnover"
            })

            # 计算涨跌幅
            df["pct_change"] = df["close"].pct_change() * 100

            # 筛选日期范围（如果不是拉全部历史）
            if start != "19900101" or end != date.today().strftime("%Y%m%d"):
                df = df[(df["date"] >= start) & (df["date"] <= end)]
            
            # 确保所有列存在
            for col in ["volume", "turnover"]:
                if col not in df.columns:
                    df[col] = None
            
            return df[["date", "open", "close", "high", "low", "volume", "turnover", "pct_change"]]
        except Exception as e:
            err_msg = str(e)
            print(f"[sector] {symbol} 拉取失败 (尝试 {attempt+1}/{max_retries}): {err_msg[:100]}")
            if attempt < max_retries - 1:
                _set_progress("L2行业板块同步", _sync_progress.get("current", 0), _sync_progress.get("total", 0), symbol, f"{symbol} 失败，5秒后重试...")
                time.sleep(5)
            else:
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
    # 处理 None 情况（拉全部历史）
    if start_date is None:
        start_date = date(1990, 1, 1)  # 足够早的日期
    if end_date is None:
        end_date = date.today()

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
    # sector/index 类型传 None 表示拉全部历史，不设置默认日期
    if asset_type in ("sector_industry", "sector_concept", "index"):
        if start_date is None and end_date is None:
            # 拉全部历史，不限制日期
            pass
        else:
            if not end_date:
                end_date = date.today()
            if not start_date:
                start_date = end_date - timedelta(days=365*10)
    else:
        if not end_date:
            end_date = date.today()
        if not start_date:
            # ETF 拉 10 年，个股拉 5 年
            days = 365 * 10 if asset_type == "etf" else 365 * 5
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
    # sector 类型拉全部历史，其他按默认
    if asset_type in ("sector_industry", "sector_concept"):
        # 拉全部历史
        start_date, end_date = None, None
    else:
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
    interval = _MIN_INTERVAL  # 统一使用 5 秒间隔

    for i, code in enumerate(codes):
        _set_progress(task_name, i + 1, total, code, f"正在同步 {code} ({i+1}/{total})")
        r = sync_single(code, asset_type, start_date=start_date, end_date=end_date)
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
                db.add(AssetMeta(code=code, name=name, asset_type="index", category="宽基", source="csindex", is_cached=1))
            else:
                meta.name = name
                meta.asset_type = "index"
                meta.category = "宽基"
                meta.source = "csindex"
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
    """同步 L2 行业板块（首次全量，后续增量）- 申万指数"""
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
                db.add(AssetMeta(code=code, name=name, asset_type="sector_industry", source="sw", is_cached=1))
            else:
                meta.name = name
                meta.asset_type = "sector_industry"
                meta.source = "sw"
                meta.is_cached = 1
        db.commit()
    finally:
        db.close()

    return batch_result


def sync_l2_industry_em() -> dict:
    """
    通过东方财富同步 L2 行业板块
    - 每5秒访问一次接口（限速）
    - 分页获取历史数据（每次2年）
    - 遇到错误继续下一个板块
    """
    _set_progress("L2行业板块同步(EM)", 0, 1, "", "正在获取东方财富行业板块列表...")
    
    # 1. 获取板块列表
    try:
        df_list = ak.stock_board_industry_name_em()
    except Exception as e:
        _set_progress("L2行业板块同步(EM)", 0, 1, "", f"获取板块列表失败: {e}")
        return {"ok": False, "message": f"获取板块列表失败: {e}"}
    
    if df_list is None or df_list.empty:
        _set_progress("L2行业板块同步(EM)", 0, 1, "", "板块列表为空")
        return {"ok": False, "message": "板块列表为空"}
    
    # 提取板块代码和名称
    boards = []
    for _, row in df_list.iterrows():
        code = str(row.get("板块代码", "")).strip()
        name = str(row.get("板块名称", "")).strip()
        if code and name:
            boards.append({"code": code, "name": name})
    
    total = len(boards)
    _set_progress("L2行业板块同步(EM)", 0, total, "", f"获取到 {total} 个板块，开始同步...")
    
    db = SessionLocal()
    saved_count = 0
    error_count = 0
    
    try:
        for idx, board in enumerate(boards, 1):
            code = board["code"]
            name = board["name"]
            
            _set_progress("L2行业板块同步(EM)", idx, total, code, f"正在同步 {name} ({idx}/{total})")
            print(f"[{idx}/{total}] {code} {name}")
            
            try:
                # 分页获取历史数据（每次2年）
                total_saved = _fetch_em_sector_pages(code, name, db)
                saved_count += total_saved
                
                # 更新或创建元数据
                meta = db.query(AssetMeta).filter(AssetMeta.code == code).first()
                if not meta:
                    db.add(AssetMeta(
                        code=code, name=name, asset_type="sector_industry",
                        category="行业板块", source="em", is_cached=1
                    ))
                else:
                    meta.name = name
                    meta.asset_type = "sector_industry"
                    meta.category = "行业板块"
                    meta.source = "em"
                    meta.is_cached = 1
                db.commit()
                
                print(f"  ✓ 保存 {total_saved} 条")
                
            except Exception as e:
                error_count += 1
                print(f"  ✗ 失败: {e}")
                db.rollback()
                continue
            
            # 5秒间隔限速
            if idx < total:
                time.sleep(5)
    
    finally:
        db.close()
        _clear_progress()
    
    return {
        "ok": True,
        "message": f"同步完成: {total} 个板块, {saved_count} 条数据, {error_count} 个错误",
        "total": total,
        "saved": saved_count,
        "errors": error_count
    }


def _fetch_em_sector_pages(symbol: str, name: str, db) -> int:
    """
    分页获取东方财富板块历史数据，每次2年
    返回保存的记录数
    """
    from datetime import datetime, timedelta
    
    saved = 0
    start_year = 1990
    end_year = datetime.now().year + 1
    
    for year in range(start_year, end_year, 2):
        start_date = f"{year}0101"
        end_date = f"{min(year+1, end_year)}1231"
        
        try:
            df = ak.stock_board_industry_hist_em(symbol=name, period="日k", 
                                                  start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                continue
            
            # 列名映射
            df["date"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")
            df = df.rename(columns={
                "开盘": "open", "收盘": "close", "最高": "high",
                "最低": "low", "成交量": "volume", "成交额": "turnover"
            })
            df["pct_change"] = df["close"].pct_change() * 100
            
            # 保存到数据库
            for _, row in df.iterrows():
                date_str = row["date"]
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                existing = db.query(HistQuotesCache).filter(
                    HistQuotesCache.code == symbol,
                    HistQuotesCache.date == date_obj
                ).first()
                
                if not existing:
                    db.add(HistQuotesCache(
                        code=symbol,
                        date=date_obj,
                        open=float(row["open"]) if pd.notna(row.get("open")) else None,
                        close=float(row["close"]),
                        high=float(row["high"]) if pd.notna(row.get("high")) else None,
                        low=float(row["low"]) if pd.notna(row.get("low")) else None,
                        volume=float(row["volume"]) if pd.notna(row.get("volume")) else None,
                        turnover=float(row["turnover"]) if pd.notna(row.get("turnover")) else None,
                        pct_change=float(row["pct_change"]) if pd.notna(row.get("pct_change")) else None,
                    ))
                    saved += 1
            
            db.commit()
            
        except Exception as e:
            print(f"  [{symbol}] {year}-{year+1} 获取失败: {e}")
            continue
        
        # 每次请求间隔1秒
        time.sleep(1)
    
    return saved


def _fetch_ths_sector_pages(symbol: str, name: str, db) -> int:
    """
    分页获取同花顺板块历史数据，每次200条
    返回保存的记录数
    """
    from datetime import datetime, timedelta
    
    saved = 0
    # 从1990年开始，每次获取2年数据（约500个交易日）
    start_year = 1990
    end_year = datetime.now().year + 1
    
    for year in range(start_year, end_year, 2):
        start_date = f"{year}0101"
        end_date = f"{min(year+1, end_year)}1231"
        
        try:
            df = ak.stock_board_industry_index_ths(symbol=name, start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                continue
                
            # 处理数据
            df["date"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")
            df = df.rename(columns={
                "开盘价": "open", "收盘价": "close", "最高价": "high",
                "最低价": "low", "成交量": "volume", "成交额": "turnover"
            })
            df["pct_change"] = df["close"].pct_change() * 100
            
            # 保存到数据库
            for _, row in df.iterrows():
                from datetime import datetime
                date_str = row["date"]
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                existing = db.query(HistQuotesCache).filter(
                    HistQuotesCache.code == symbol,
                    HistQuotesCache.date == date_obj
                ).first()
                
                if not existing:
                    db.add(HistQuotesCache(
                        code=symbol,
                        date=date_obj,
                        open=float(row["open"]) if pd.notna(row.get("open")) else None,
                        close=float(row["close"]),
                        high=float(row["high"]) if pd.notna(row.get("high")) else None,
                        low=float(row["low"]) if pd.notna(row.get("low")) else None,
                        volume=float(row["volume"]) if pd.notna(row.get("volume")) else None,
                        turnover=float(row["turnover"]) if pd.notna(row.get("turnover")) else None,
                        pct_change=float(row["pct_change"]) if pd.notna(row.get("pct_change")) else None,
                    ))
                    saved += 1
            
            db.commit()
            
        except Exception as e:
            print(f"  [{symbol}] {year}-{year+1} 获取失败: {e}")
            continue
        
        # 每次请求间隔1秒
        time.sleep(1)
    
    return saved


def sync_l2_industry_ths() -> dict:
    """
    通过同花顺同步 L2 行业板块
    - 每5秒访问一次接口
    - 分页获取历史数据（每次2年）
    - 遇到错误继续下一个板块
    """
    _set_progress("L2行业板块同步(THS)", 0, 1, "", "正在获取同花顺行业板块列表...")

    # 1. 获取板块列表
    try:
        df_list = ak.stock_board_industry_name_ths()
    except Exception as e:
        _set_progress("L2行业板块同步(THS)", 0, 1, "", f"获取板块列表失败: {e}")
        return {"ok": False, "message": f"获取板块列表失败: {e}"}

    if df_list is None or df_list.empty:
        _set_progress("L2行业板块同步(THS)", 0, 1, "", "板块列表为空")
        return {"ok": False, "message": "板块列表为空"}

    # 提取板块代码和名称
    boards = df_list.to_dict('records')
    total = len(boards)

    _set_progress("L2行业板块同步(THS)", 0, total, "", f"开始同步，共{total}个板块")

    db = SessionLocal()
    results = []
    total_saved = 0

    try:
        for i, board in enumerate(boards):
            symbol = board['code']
            name = board['name']
            _set_progress("L2行业板块同步(THS)", i + 1, total, symbol, f"正在同步 {name} ({i+1}/{total})")

            try:
                # 分页获取历史数据
                saved = _fetch_ths_sector_pages(symbol, name, db)
                
                # 更新或创建元数据
                meta = db.query(AssetMeta).filter(AssetMeta.code == symbol).first()
                if not meta:
                    db.add(AssetMeta(
                        code=symbol,
                        name=name,
                        asset_type="sector_industry",
                        source="ths",
                        is_cached=1
                    ))
                else:
                    meta.name = name
                    meta.asset_type = "sector_industry"
                    meta.source = "ths"
                    meta.is_cached = 1
                
                db.commit()
                results.append({"code": symbol, "name": name, "ok": True, "saved": saved})
                total_saved += saved
                
            except Exception as e:
                print(f"[{symbol}] {name} 同步失败: {e}")
                results.append({"code": symbol, "name": name, "ok": False, "error": str(e)})

    finally:
        db.close()

    _clear_progress()
    return {"ok": True, "total": total, "saved": total_saved, "results": results}


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
                db.add(AssetMeta(code=code, name=name, asset_type="sector_concept", source="em", is_cached=1))
            else:
                meta.name = name
                meta.asset_type = "sector_concept"
                meta.source = "em"
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
                "source": a.source or "",
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
