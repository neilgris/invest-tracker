import akshare as ak
import time
import requests
from datetime import date, datetime, timedelta


import re

# 常见基金公司后缀，用于生成短名
_FUND_SUFFIXES = [
    "华泰柏瑞", "嘉实", "华夏", "易方达", "南方", "广发", "天弘", "工银瑞信",
    "银华", "鹏华", "博时", "国泰", "富国", "汇添富", "招商", "景顺长城",
    "大成", "中银", "华安", "长盛", "诺安", "融通", "万家", "浦银安盛",
    "建信", "交银施罗德", "兴证全球", "中欧", "泓德", "睿远", "东方",
    "兴业", "长城", "平安", "海富通", "上投摩根", "泰康",
]


def _make_short_name(name: str, classify: str = "") -> str:
    """生成简化名称：ETF去掉基金公司后缀，个股保持原名"""
    if classify == "Fund" or "ETF" in name or "LOF" in name:
        for suffix in _FUND_SUFFIXES:
            if name.endswith(suffix):
                return name[:-len(suffix)]
    return name


def _search_code(code: str) -> dict:
    """用东方财富搜索接口快速校验代码，返回名称、短名和市场类型"""
    try:
        url = f"https://searchapi.eastmoney.com/api/suggest/get"
        params = {
            "input": code,
            "type": "14",
            "token": "D43BF722C8E33BDC906FB84D85E326E8",
            "count": "5",
        }
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        if data.get("QuotationCodeTable") and data["QuotationCodeTable"]["Data"]:
            for item in data["QuotationCodeTable"]["Data"]:
                if item["Code"] == code:
                    full_name = item["Name"]
                    classify = item.get("Classify", "")
                    short = _make_short_name(full_name, classify)
                    return {"name": full_name, "short_name": short, "type": item.get("MktNum", "")}
    except Exception:
        pass
    return {}


def get_stock_name(code: str) -> str:
    """根据代码获取股票/ETF名称"""
    # 优先用轻量搜索接口
    result = _search_code(code)
    if result and result.get("name"):
        return result["name"]

    # fallback: akshare个股信息
    try:
        df = ak.stock_individual_info_em(symbol=code)
        if df is not None and not df.empty:
            row = df[df["item"] == "股票简称"]
            if not row.empty:
                return str(row.iloc[0]["value"])
    except Exception:
        pass

    return ""


# 已知的A股指数代码（不是基金，需要走指数行情接口）
# 只列出常见的宽基/行业指数，其余000开头的可能是基金（如000216华安黄金ETF联接）
_INDEX_CODES = {
    "000001",  # 上证指数
    "000002",  # A股指数
    "000003",  # B股指数
    "000016",  # 上证50
    "000300",  # 沪深300
    "000905",  # 中证500
    "000906",  # 中证800
    "000852",  # 中证1000
    "000688",  # 科创50
    "000071",  # 沪深300等权重
    "000073",  # 创业板指数
    "000077",  # 中证100
    "000807",  # 食品饮料
    "000819",  # 有色金属
    "000827",  # 环境治理
    "000831",  # 新能源
    "000833",  # 中证医药
    "000849",  # 沪深300非银
    "000860",  # 医药卫生
    "000861",  # 中证医疗
    "000862",  # 科技龙头
    "000863",  # 中证军工
    "000922",  # 中证红利
    "000963",  # 中证地展
    "000967",  # 中证新能源汽车
    "000977",  # 中证全指半导体
    "000985",  # 中证全指
    "000988",  # 中证主题
    "000991",  # 全指医药
    "000993",  # 全指信息
}


def _is_fund_code(code: str) -> bool:
    """判断是否为开放式基金代码（非交易所交易的基金）
    开放式基金代码通常以 0、1、2 开头且不在交易所交易，
    如 025856、110011、202101、000216 等。
    交易所 ETF：510xxx、511xxx、512xxx、513xxx、515xxx、159xxx
    指数：仅已知指数代码走指数接口，其余000开头也可能是基金
    """
    if not code or len(code) != 6:
        return False
    # 交易所 ETF 不算
    if code.startswith(('51', '15', '50', '56')):
        return False
    # 已知指数代码不算基金
    if code in _INDEX_CODES:
        return False
    # 其余 0/1/2 开头的6位代码，视为开放式基金
    if code[0] in ('0', '1', '2'):
        return True
    return False


def _get_fund_nav(code: str) -> float | None:
    """获取开放式基金最新净值"""
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is not None and not df.empty:
            return float(df.iloc[-1]["单位净值"])
    except Exception:
        pass
    return None


def _get_fund_nav_hist(code: str, start_date: str, end_date: str) -> list[dict]:
    """获取开放式基金历史净值，start_date/end_date 支持 YYYYMMDD 或 YYYY-MM-DD 格式"""
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or df.empty:
            return []
        # 统一日期格式为 YYYY-MM-DD
        def _fmt(d):
            s = str(d).strip()
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and '-' not in s else s
        start_fmt = _fmt(start_date)
        end_fmt = _fmt(end_date)
        df["净值日期"] = df["净值日期"].astype(str)
        mask = (df["净值日期"] >= start_fmt) & (df["净值日期"] <= end_fmt)
        df = df[mask]
        result = []
        for _, row in df.iterrows():
            nav = float(row["单位净值"])
            result.append({
                "date": str(row["净值日期"]),
                "open": nav,
                "close": nav,
                "high": nav,
                "low": nav,
            })
        return result
    except Exception as e:
        print(f"获取基金净值失败 {code}: {e}")
        return []


def get_fund_nav_on_date(code: str, date_str: str) -> float | None:
    """获取开放式基金指定日期的净值，date_str 支持 YYYY-MM-DD 或 YYYYMMDD"""
    # 统一日期格式
    s = str(date_str).strip()
    target_date = f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and '-' not in s else s
    
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or df.empty:
            return None
        df["净值日期"] = df["净值日期"].astype(str)
        row = df[df["净值日期"] == target_date]
        if not row.empty:
            return float(row.iloc[0]["单位净值"])
    except Exception as e:
        print(f"获取基金净值失败 {code} {date_str}: {e}")
    return None


def get_latest_price(code: str) -> float | None:
    """获取最新收盘价/净值"""
    # 开放式基金：走净值接口
    if _is_fund_code(code):
        return _get_fund_nav(code)

    try:
        # 指数
        if code.startswith("000") and len(code) == 6:
            df = ak.stock_zh_index_daily(symbol=f"sh{code}")
            if df is not None and not df.empty:
                return float(df.iloc[-1]["close"])

        # 个股/ETF - 统一用stock_zh_a_hist
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
        if df is not None and not df.empty:
            return float(df.iloc[-1]["收盘"])
    except Exception:
        pass

    # ETF备用：用实时行情
    try:
        df = ak.fund_etf_spot_em()
        row = df[df["代码"] == code]
        if not row.empty:
            return float(row.iloc[0]["最新价"])
    except Exception:
        pass

    return None


def _normalize_date(d: str) -> str:
    """将日期统一为 YYYY-MM-DD 格式"""
    s = str(d).strip()
    if len(s) == 8 and '-' not in s:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def get_hist_prices(code: str, start_date: str, end_date: str) -> list[dict]:
    """获取历史行情数据"""
    # 开放式基金：走净值接口
    if _is_fund_code(code):
        return _get_fund_nav_hist(code, start_date, end_date)

    start_fmt = _normalize_date(start_date)
    end_fmt = _normalize_date(end_date)

    try:
        if code.startswith("000") and len(code) == 6:
            df = ak.stock_zh_index_daily(symbol=f"sh{code}")
            if df is not None and not df.empty:
                df = df.rename(columns={"date": "日期", "open": "开盘", "close": "收盘", "high": "最高", "low": "最低"})
                df["日期"] = df["日期"].astype(str)
                mask = (df["日期"] >= start_fmt) & (df["日期"] <= end_fmt)
                df = df[mask]
        else:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
            if df is not None and not df.empty:
                df["日期"] = df["日期"].astype(str)

        if df is None or df.empty:
            return []

        result = []
        for _, row in df.iterrows():
            result.append({
                "date": str(row["日期"]),
                "open": float(row["开盘"]) if "开盘" in row else None,
                "close": float(row["收盘"]),
                "high": float(row["最高"]) if "最高" in row else None,
                "low": float(row["最低"]) if "最低" in row else None,
            })
        return result
    except Exception as e:
        print(f"获取历史行情失败 {code}: {e}")
        return []


def _is_trading_day(d: date) -> bool:
    """判断是否为交易日（简单版：周一到周五，不包含法定节假日）"""
    return d.weekday() < 5  # 0-4 是周一到周五


def _save_snapshots(db, code: str, prices: list[dict], quantity: float = 0, total_cost: float = 0):
    """将行情数据保存到 daily_snapshots（只存价格，pnl 由 recalc_snapshots_pnl 计算）
    
    注意：
    1. 只保存交易日数据（周一到周五），跳过周末
    2. 对于今天的数据，如果 akshare 还没更新（返回的日期不是今天），跳过
    """
    from models import DailySnapshot

    if not prices:
        return 0

    today = date.today()
    saved = 0
    
    # 检查 prices 中是否包含今天的数据
    has_today = False
    today_price = None
    for p in prices:
        d = p["date"]
        if isinstance(d, str):
            d = datetime.strptime(d, "%Y-%m-%d").date()
        if d == today:
            has_today = True
            today_price = p
            break
    
    # 如果 prices 声称包含今天，但实际数据可能还没更新
    # 对于基金，检查 akshare 返回的最新日期
    if has_today and _is_fund_code(code):
        # 获取 akshare 实际返回的最新日期
        latest_date = None
        for p in prices:
            d = p["date"]
            if isinstance(d, str):
                d = datetime.strptime(d, "%Y-%m-%d").date()
            if latest_date is None or d > latest_date:
                latest_date = d
        # 如果 akshare 最新数据不是今天，说明今天数据还没更新
        if latest_date < today:
            print(f"  {code} 今天数据尚未更新，跳过")
            # 过滤掉今天的数据
            prices = [p for p in prices if p["date"] != today.strftime("%Y-%m-%d")]

    for p in prices:
        d = p["date"]
        if isinstance(d, str):
            d = datetime.strptime(d, "%Y-%m-%d").date()
        
        # 跳过非交易日（周末）
        if not _is_trading_day(d):
            continue

        existing = db.query(DailySnapshot).filter(
            DailySnapshot.code == code,
            DailySnapshot.date == d
        ).first()

        if existing:
            # 只更新价格字段
            existing.open = p.get("open")
            existing.close = p["close"]
            existing.high = p.get("high")
            existing.low = p.get("low")
            continue

        snap = DailySnapshot(
            code=code,
            date=d,
            open=p.get("open"),
            close=p["close"],
            high=p.get("high"),
            low=p.get("low"),
            # pnl 字段暂不填，由 recalc_snapshots_pnl 统一计算
            market_value=None,
            daily_pnl=None,
            total_pnl=None,
        )
        db.add(snap)
        saved += 1

    return saved


def recalc_snapshots_pnl(code: str = None):
    """根据交易时间线重算 daily_snapshots 的 pnl 字段
    
    逻辑：按时间顺序遍历快照，根据交易记录确定每天的实际持仓量，
    正确计算 daily_pnl / total_pnl / market_value。
    
    - 买入前的快照：无持仓，pnl 全为 0
    - 买入当天起：开始计算持仓市值和收益
    - 多笔买卖：按时间顺序累加/扣减持仓
    """
    from database import SessionLocal
    from models import Trade, DailySnapshot

    db = SessionLocal()
    try:
        codes = [code] if code else [c[0] for c in db.query(DailySnapshot.code).distinct().all()]

        for c in codes:
            # 按日期排序获取所有交易
            trades = db.query(Trade).filter(Trade.code == c).order_by(Trade.trade_date).all()
            if not trades:
                continue

            # 构建交易日 -> 持仓变动映射
            # holding_changes[date] = list of (direction, quantity, amount, fee)
            trade_map = {}
            for t in trades:
                d = t.trade_date
                qty = t.quantity if t.quantity else _calc_quantity(t.amount, t.price, t.fee or 0)
                if d not in trade_map:
                    trade_map[d] = []
                trade_map[d].append({
                    "direction": t.direction,
                    "quantity": qty,
                    "amount": t.amount,
                    "fee": t.fee or 0,
                })

            # 按日期顺序遍历快照
            snaps = db.query(DailySnapshot).filter(
                DailySnapshot.code == c
            ).order_by(DailySnapshot.date).all()

            running_qty = 0.0
            running_cost = 0.0
            prev_close = None

            # 先处理第一个快照之前的所有交易（可能交易日期早于已有快照）
            first_snap_date = snaps[0].date if snaps else date.max
            for d in sorted(trade_map.keys()):
                if d < first_snap_date:
                    for trade in trade_map[d]:
                        if trade["direction"] == "buy":
                            running_qty += trade["quantity"]
                            running_cost += trade["amount"]
                        elif trade["direction"] == "sell":
                            running_qty -= trade["quantity"]
                            running_cost -= (trade["amount"] - trade["fee"])
                        elif trade["direction"] == "dividend":
                            running_qty += trade["quantity"]

            for snap in snaps:
                d = snap.date

                # 处理当天的交易
                if d in trade_map:
                    for trade in trade_map[d]:
                        if trade["direction"] == "buy":
                            running_qty += trade["quantity"]
                            running_cost += trade["amount"]
                        elif trade["direction"] == "sell":
                            running_qty -= trade["quantity"]
                            running_cost -= (trade["amount"] - trade["fee"])
                        elif trade["direction"] == "dividend":
                            # 分红再投资：增加份额，不增加成本
                            running_qty += trade["quantity"]

                if running_qty <= 0:
                    # 无持仓
                    snap.market_value = 0
                    snap.daily_pnl = 0
                    snap.total_pnl = 0
                    prev_close = snap.close
                    continue

                # 有持仓
                snap.market_value = round(running_qty * snap.close, 4)
                snap.total_pnl = round(snap.market_value - running_cost, 4)

                # 日收益 = (今日收盘 - 昨日收盘) * 持仓量
                if prev_close and prev_close > 0:
                    snap.daily_pnl = round((snap.close - prev_close) * running_qty, 4)
                else:
                    snap.daily_pnl = 0

                prev_close = snap.close

            db.commit()
            print(f"  {c} pnl 重算完成")
    finally:
        db.close()


def fetch_and_save_daily(scheduler_ctx=None):
    """定时任务：拉取所有持仓的当日行情并保存快照"""
    from database import SessionLocal
    from models import Position, DailySnapshot

    db = SessionLocal()
    try:
        positions = db.query(Position).all()
        today = date.today()

        for pos in positions:
            time.sleep(0.3)  # 限速
            try:
                prices = get_hist_prices(pos.code, today.strftime("%Y%m%d"), today.strftime("%Y%m%d"))
                if not prices:
                    latest = get_latest_price(pos.code)
                    if latest:
                        prices = [{"date": today.strftime("%Y-%m-%d"), "close": latest, "open": latest, "high": latest, "low": latest}]

                if not prices:
                    continue

                _save_snapshots(db, pos.code, prices)

                p = prices[0]
                pos.current_price = p["close"]
                pos.updated_at = datetime.now()
            except Exception as e:
                print(f"处理持仓 {pos.code} 失败: {e}")
                continue

        db.commit()
    finally:
        db.close()

    # 重算 pnl
    recalc_snapshots_pnl()


def fetch_and_save_history():
    """同步所有持仓的历史行情数据到 daily_snapshots（增量：只拉缺失区间的新数据）"""
    from database import SessionLocal
    from models import Position, DailySnapshot, Trade
    from sqlalchemy import func

    db = SessionLocal()
    try:
        positions = db.query(Position).all()
        today = date.today()

        for pos in positions:
            time.sleep(0.5)  # 限速
            try:
                # 每个持仓的历史起点：5年前 vs 该持仓最早交易日期，取更早的
                pos_earliest = db.query(func.min(Trade.trade_date)).filter(Trade.code == pos.code).scalar()
                pos_start = today - timedelta(days=365 * 5)
                if pos_earliest and pos_earliest < pos_start:
                    pos_start = pos_earliest

                # 查 DB 里已有数据的日期范围
                first_snap = db.query(DailySnapshot).filter(
                    DailySnapshot.code == pos.code
                ).order_by(DailySnapshot.date).first()

                last_snap = db.query(DailySnapshot).filter(
                    DailySnapshot.code == pos.code
                ).order_by(DailySnapshot.date.desc()).first()

                # 确定需要拉的区间
                gaps = []  # [(start, end, mode)]

                if not first_snap:
                    # 完全没有数据：拉全量（覆盖最早交易）
                    gaps.append((pos_start.strftime("%Y%m%d"),
                                 (today + timedelta(days=1)).strftime("%Y%m%d"), "全量"))
                else:
                    # 有数据，检查前面是否有缺口
                    if first_snap.date > pos_start:
                        gaps.append((pos_start.strftime("%Y%m%d"),
                                     first_snap.date.strftime("%Y%m%d"), "补历史"))
                    # 检查后面是否有缺口（最晚记录是否到今天）
                    if last_snap.date < today:
                        gaps.append(((last_snap.date + timedelta(days=1)).strftime("%Y%m%d"),
                                     (today + timedelta(days=1)).strftime("%Y%m%d"), "增量"))

                if not gaps:
                    print(f"  {pos.code}({pos.short_name or pos.name}) 数据已完整，跳过")
                    continue

                total_saved = 0
                for start_date, end_date, mode in gaps:
                    prices = get_hist_prices(pos.code, start_date, end_date)
                    if not prices:
                        print(f"  {pos.code}({pos.short_name or pos.name}) {mode}同步无新数据")
                        continue

                    saved = _save_snapshots(db, pos.code, prices)
                    total_saved += saved
                    print(f"  {pos.code}({pos.short_name or pos.name}) {mode}同步 {len(prices)} 条, 新增 {saved} 条")

                # 更新当前价格
                if total_saved > 0:
                    latest = db.query(DailySnapshot).filter(
                        DailySnapshot.code == pos.code
                    ).order_by(DailySnapshot.date.desc()).first()
                    if latest:
                        pos.current_price = latest.close
                        pos.updated_at = datetime.now()

            except Exception as e:
                print(f"同步历史 {pos.code} 失败: {e}")
                continue

        db.commit()
    finally:
        db.close()

    # 重算 pnl
    recalc_snapshots_pnl()


def get_fund_dividends(code: str) -> list[dict]:
    """获取基金（开放式基金/ETF联接）的分红记录
    返回 [{date, dividend_per_unit}, ...]

    策略：通过净值差值法检测分红，带健康性检查。
    - 正常开放式基金：diff 只在分红日跳变，其余时间恒定 → 方法有效
    - LOF/分级基金：diff 每天都在变（折算/估值差异）→ 健康性检查会直接返回空
    """
    try:
        df_nav = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        df_acc = ak.fund_open_fund_info_em(symbol=code, indicator="累计净值走势")
        if df_nav is None or df_acc is None or df_nav.empty or df_acc.empty:
            return []

        df = df_nav[["净值日期", "单位净值"]].merge(
            df_acc[["净值日期", "累计净值"]], on="净值日期"
        )
        df["diff"] = df["累计净值"] - df["单位净值"]
        df["diff_change"] = df["diff"].diff()

        # 健康性检查：如果 diff 在超过 5% 的交易日都有变化(>0.005)，
        # 说明此基金净值差值法不适用（如 LOF、分级基金），直接返回空
        changing_days = (df["diff_change"].abs() > 0.005).sum()
        total_days = len(df) - 1  # 排除第一行 NaN
        if total_days > 50 and changing_days / total_days > 0.05:
            return []

        # 严格阈值：diff_change >= 0.03
        candidates = df[df["diff_change"] >= 0.03].copy()
        if candidates.empty:
            return []

        result = []
        for idx_val, row in candidates.iterrows():
            div_amount = row["diff_change"]
            pre_diff = row["diff"] - div_amount
            pos = df.index.get_loc(idx_val)
            future = df.iloc[pos + 1: pos + 6]
            if future.empty:
                result.append({"date": str(row["净值日期"]), "dividend_per_unit": round(div_amount, 4)})
                continue
            min_future_diff = future["diff"].min()
            # 分红后 diff 不应回落超过分红金额的 20%
            if min_future_diff < pre_diff + div_amount * 0.8:
                continue
            result.append({
                "date": str(row["净值日期"]),
                "dividend_per_unit": round(div_amount, 4),
            })
        return result
    except Exception as e:
        print(f"获取基金分红失败 {code}: {e}")
        return []


def get_stock_dividends(code: str) -> list[dict]:
    """获取股票的分红记录（每10股派息）
    返回 [{date, dividend_per_share}, ...]
    """
    try:
        df = ak.stock_history_dividend_detail(symbol=code, indicator="分红")
        if df is None or df.empty:
            return []

        result = []
        for _, row in df.iterrows():
            if row.get("进度") != "实施":
                continue
            ex_date = row.get("除权除息日")
            if not ex_date or str(ex_date) == "NaT":
                continue
            # 派息是每10股，转为每股
            dividend_per_10 = row.get("派息", 0)
            if dividend_per_10 and dividend_per_10 > 0:
                result.append({
                    "date": str(ex_date).split(" ")[0],
                    "dividend_per_share": round(float(dividend_per_10) / 10, 4),
                })
        return result
    except Exception as e:
        print(f"获取股票分红失败 {code}: {e}")
        return []


def get_etf_dividends(code: str) -> list[dict]:
    """获取ETF的分红记录（同 get_fund_dividends 逻辑）
    返回 [{date, dividend_per_unit}, ...]
    """
    # 复用 get_fund_dividends 的逻辑（净值差值法+健康性检查）
    return get_fund_dividends(code)


def detect_and_record_dividends(code: str = None) -> list[dict]:
    """检测持仓的分红记录，返回在首笔买入之后的分红列表
    
    返回 [{code, name, short_name, date, dividend_per_unit, quantity, dividend_amount, price, reinvest_qty}, ...]
    """
    from database import SessionLocal
    from models import Trade, Position, DailySnapshot

    db = SessionLocal()
    try:
        codes = [code] if code else [c[0] for c in db.query(Position.code).all()]

        all_results = []
        for c in codes:
            # 获取首笔买入日期
            first_buy = db.query(Trade).filter(
                Trade.code == c, Trade.direction.in_(["buy"])
            ).order_by(Trade.trade_date).first()
            if not first_buy:
                continue

            position = db.query(Position).filter(Position.code == c).first()
            if not position:
                continue

            # 获取分红数据
            if _is_fund_code(c):
                dividends = get_fund_dividends(c)
            elif c.startswith(('51', '15', '50', '56')):
                dividends = get_etf_dividends(c)
            else:
                dividends = get_stock_dividends(c)

            if not dividends:
                continue

            # 过滤：只保留首笔买入后的分红
            first_date = str(first_buy.trade_date)
            dividends = [d for d in dividends if d["date"] >= first_date]

            # 已记录的分红交易日期
            existing_dividends = db.query(Trade).filter(
                Trade.code == c, Trade.direction == "dividend"
            ).all()
            existing_dates = {str(t.trade_date) for t in existing_dividends}

            # 构建交易时间线
            all_trades = db.query(Trade).filter(Trade.code == c).order_by(Trade.trade_date).all()

            for div in dividends:
                div_date = div["date"]
                if div_date in existing_dates:
                    continue

                # 计算到分红日为止的持仓量
                qty_at_date = 0.0
                for t in all_trades:
                    if str(t.trade_date) > div_date:
                        break
                    tqty = t.quantity if t.quantity else _calc_quantity(t.amount, t.price, t.fee or 0)
                    if t.direction == "buy":
                        qty_at_date += tqty
                    elif t.direction == "sell":
                        qty_at_date -= tqty
                    elif t.direction == "dividend":
                        qty_at_date += tqty

                if qty_at_date <= 0:
                    continue

                # 获取分红日收盘价/净值
                snap = db.query(DailySnapshot).filter(
                    DailySnapshot.code == c, DailySnapshot.date == div_date
                ).first()
                if not snap:
                    prices = get_hist_prices(c, div_date.replace("-", ""), div_date.replace("-", ""))
                    if prices:
                        price = prices[0]["close"]
                    else:
                        continue
                else:
                    price = snap.close

                if not price or price <= 0:
                    continue

                # 分红计算
                div_per_unit = div.get("dividend_per_unit", div.get("dividend_per_share", 0))
                div_amount = round(div_per_unit * qty_at_date, 2)
                reinvest_qty = round(div_amount / price, 2)

                all_results.append({
                    "code": c,
                    "name": position.name,
                    "short_name": position.short_name or position.name,
                    "date": div_date,
                    "dividend_per_unit": div_per_unit,
                    "quantity": qty_at_date,
                    "dividend_amount": div_amount,
                    "price": price,
                    "reinvest_qty": reinvest_qty,
                })

        return all_results
    finally:
        db.close()
