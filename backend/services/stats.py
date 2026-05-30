from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Trade, Position, DailySnapshot
from datetime import date, datetime, timedelta
from calendar import monthrange


def get_overview(db: Session) -> dict:
    """获取总览数据"""
    positions = db.query(Position).filter(Position.is_closed == 0).all()

    total_cost = 0.0
    total_market_value = 0.0
    latest_pnl = 0.0
    latest_date = None

    for pos in positions:
        snap = db.query(DailySnapshot).filter(
            DailySnapshot.code == pos.code
        ).order_by(DailySnapshot.date.desc()).first()

        price = snap.close if snap and snap.close else pos.current_price
        mv = pos.quantity * price if price else pos.total_cost
        total_cost += pos.total_cost
        total_market_value += mv

        if snap and snap.daily_pnl is not None:
            latest_pnl += snap.daily_pnl
            if latest_date is None or snap.date > latest_date:
                latest_date = snap.date

    total_pnl = total_market_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
    latest_pnl_pct = (latest_pnl / total_cost * 100) if total_cost > 0 else 0

    return {
        "total_cost": round(total_cost, 2),
        "total_market_value": round(total_market_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "daily_pnl": round(latest_pnl, 2),
        "daily_pnl_pct": round(latest_pnl_pct, 2),
        "latest_date": latest_date.isoformat() if latest_date else None,
        "position_count": len(positions),
    }


# ---------------------------------------------------------------------------
# 核心辅助：期内已实现收益
# ---------------------------------------------------------------------------

def _calc_realized_in_period(trades: list, start_date: date) -> float:
    """回放全历史交易，返回 [start_date, ...) 内卖出的已实现收益。

    trades 已按 trade_date 升序排列，且只包含到统计期 end_date 为止的交易。
    通过回放全量历史确保期前建仓的成本基础被正确纳入，解决只看期内交易时
    running_qty=0 导致卖出收益被漏算的问题。
    """
    running_cost = 0.0
    running_qty = 0.0
    realized = 0.0

    for t in trades:
        if t.direction == 'buy':
            running_cost += t.amount
            running_qty += t.quantity or 0
        elif t.direction == 'sell':
            if running_qty > 0:
                avg = running_cost / running_qty
                sell_cost = (t.quantity or 0) * avg
                if t.trade_date >= start_date:
                    realized += (t.amount - (t.fee or 0)) - sell_cost
                running_cost -= sell_cost
                running_qty -= (t.quantity or 0)
        elif t.direction == 'dividend':
            running_qty += t.quantity or 0

    return realized


# ---------------------------------------------------------------------------
# 核心函数：任意区间的持仓收益明细
# ---------------------------------------------------------------------------

def get_period_position_details(db: Session, start_date: date, end_date: date) -> dict:
    """任意日期区间内各持仓的收益明细。

    计算公式：
        period_pnl      = Δ(unrealized) + realized_within_period
        Δ(unrealized)   = end_total_pnl  - prev_period_total_pnl
        realized        = 期内所有卖出的实际盈亏（使用全历史成本基础回放）

    其中 total_pnl 含义为当日浮盈 = market_value - running_cost，
    卖出后已实现收益以现金形式离开持仓，不再计入 total_pnl，
    因此必须单独累加才能得到完整的期间收益。
    """
    # 期内快照
    snapshots = db.query(DailySnapshot).filter(
        DailySnapshot.date >= start_date,
        DailySnapshot.date <= end_date,
    ).all()

    # 期初前最后一个交易日的快照（浮盈基准）
    prev_date = db.query(func.max(DailySnapshot.date)).filter(
        DailySnapshot.date < start_date
    ).scalar()
    prev_snaps: dict[str, DailySnapshot] = {}
    if prev_date:
        prev_snaps = {
            s.code: s
            for s in db.query(DailySnapshot).filter(
                DailySnapshot.date == prev_date
            ).all()
        }

    # 全历史交易（到 end_date 为止）——用于回放各标的成本基础
    all_trades = (
        db.query(Trade)
        .filter(Trade.trade_date <= end_date)
        .order_by(Trade.trade_date)
        .all()
    )
    trades_by_code: dict[str, list] = {}
    for t in all_trades:
        trades_by_code.setdefault(t.code, []).append(t)

    # 持仓元数据（名称、关联ETF简称）
    pos_meta: dict[str, Position] = {p.code: p for p in db.query(Position).all()}

    # 期内快照按 code 分组
    snaps_by_code: dict[str, list] = {}
    for s in snapshots:
        snaps_by_code.setdefault(s.code, []).append(s)

    result_positions = []
    total_realized = 0.0
    total_unrealized = 0.0

    # --- 有期内快照的标的 ---
    for code, code_snaps in snaps_by_code.items():
        code_snaps.sort(key=lambda x: x.date)

        first_snap = code_snaps[0]
        last_snap = code_snaps[-1]
        start_mv = first_snap.market_value or 0
        end_mv = last_snap.market_value or 0
        end_total_pnl = last_snap.total_pnl or 0

        prev = prev_snaps.get(code)
        prev_total_pnl = (prev.total_pnl or 0) if prev else 0

        # 先算 realized，再决定是否跳过（period内有清仓收益也需保留）
        realized = _calc_realized_in_period(trades_by_code.get(code, []), start_date)
        delta_unrealized = end_total_pnl - prev_total_pnl
        period_pnl = delta_unrealized + realized

        # 跳过：整个区间均无持仓且无已实现收益
        if all((s.market_value or 0) == 0 for s in code_snaps) and abs(realized) < 0.01:
            continue

        # 成本 = 市值 - 浮盈；全月清仓时回退到期初前快照成本
        start_cost = start_mv - (first_snap.total_pnl or 0)
        end_cost = end_mv - end_total_pnl
        base_cost = start_cost if start_cost > 0 else end_cost
        if base_cost <= 0 and prev:
            prev_mv = prev.market_value or 0
            prev_cost = prev_mv - (prev.total_pnl or 0)
            base_cost = prev_cost if prev_cost > 0 else 0
        pnl_pct = round(period_pnl / base_cost * 100, 2) if base_cost > 0 else 0

        pos = pos_meta.get(code)
        result_positions.append({
            "code": code,
            "name": pos.name if pos else code,
            "linked_short_name": pos.linked_short_name if pos else None,
            "start_market_value": round(start_mv, 2),
            "end_market_value": round(end_mv, 2),
            "start_cost": round(base_cost, 2),
            "realized_pnl": round(realized, 2),
            "unrealized_pnl": round(delta_unrealized, 2),
            "pnl": round(period_pnl, 2),
            "pnl_pct": pnl_pct,
        })
        total_realized += realized
        total_unrealized += delta_unrealized

    # --- 期内有卖出但无快照的标的（已清仓且行情数据缺失）---
    codes_with_snaps = set(snaps_by_code.keys())
    seen: set[str] = set()
    for t in all_trades:
        if (t.trade_date < start_date
                or t.direction != 'sell'
                or t.code in codes_with_snaps
                or t.code in seen):
            continue
        seen.add(t.code)

        realized = _calc_realized_in_period(trades_by_code.get(t.code, []), start_date)
        if abs(realized) < 0.01:
            continue

        total_buy = sum(
            tr.amount for tr in trades_by_code.get(t.code, [])
            if tr.direction == 'buy'
        )
        pos = pos_meta.get(t.code)
        result_positions.append({
            "code": t.code,
            "name": pos.name if pos else (t.name or t.code),
            "linked_short_name": pos.linked_short_name if pos else None,
            "start_market_value": 0,
            "end_market_value": 0,
            "start_cost": round(total_buy, 2),
            "realized_pnl": round(realized, 2),
            "unrealized_pnl": 0,
            "pnl": round(realized, 2),
            "pnl_pct": round(realized / total_buy * 100, 2) if total_buy > 0 else 0,
        })
        total_realized += realized

    result_positions.sort(key=lambda x: x["pnl"], reverse=True)

    total_end_mv = sum(p["end_market_value"] for p in result_positions)
    total_pnl = total_realized + total_unrealized
    total_pnl_pct = round(total_pnl / total_end_mv * 100, 2) if total_end_mv > 0 else 0

    return {
        "positions": result_positions,
        "summary": {
            "total_start_market_value": round(
                sum(p["start_market_value"] for p in result_positions), 2
            ),
            "total_end_market_value": round(total_end_mv, 2),
            "total_realized_pnl": round(total_realized, 2),
            "total_unrealized_pnl": round(total_unrealized, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": total_pnl_pct,
            "position_count": len(result_positions),
        },
    }


# ---------------------------------------------------------------------------
# 对外接口：月度 / 年度 —— 统一调用核心函数
# ---------------------------------------------------------------------------

def get_monthly_position_details(db: Session, year: int, month: int) -> dict:
    _, last_day = monthrange(year, month)
    return get_period_position_details(db, date(year, month, 1), date(year, month, last_day))


def get_yearly_position_details(db: Session, year: int) -> dict:
    return get_period_position_details(db, date(year, 1, 1), date(year, 12, 31))


def get_monthly_stats(db: Session, year: int | None = None) -> list[dict]:
    """月度收益汇总列表"""
    if not year:
        year = date.today().year

    snap_months = {
        s.date.strftime("%Y-%m")
        for s in db.query(DailySnapshot).filter(
            DailySnapshot.date >= date(year, 1, 1),
            DailySnapshot.date <= date(year, 12, 31),
        ).all()
    }
    sell_months = {
        t.trade_date.strftime("%Y-%m")
        for t in db.query(Trade).filter(
            Trade.trade_date >= date(year, 1, 1),
            Trade.trade_date <= date(year, 12, 31),
            Trade.direction == 'sell',
        ).all()
    }

    result = []
    for month_key in sorted(snap_months | sell_months):
        y, m = map(int, month_key.split("-"))
        details = get_monthly_position_details(db, y, m)
        if not details["positions"]:
            continue
        s = details["summary"]
        result.append({
            "month": month_key,
            "realized_pnl": s["total_realized_pnl"],
            "unrealized_pnl": s["total_unrealized_pnl"],
            "pnl": s["total_pnl"],
            "holding_market_value": s["total_end_market_value"],
            "pnl_pct": s["total_pnl_pct"],
        })

    return result


def get_yearly_stats(db: Session) -> list[dict]:
    """年度收益汇总列表"""
    years = sorted({
        s.date.year
        for s in db.query(DailySnapshot).all()
    })

    result = []
    for year in years:
        details = get_yearly_position_details(db, year)
        if not details["positions"]:
            continue
        s = details["summary"]
        result.append({
            "year": year,
            "realized_pnl": s["total_realized_pnl"],
            "unrealized_pnl": s["total_unrealized_pnl"],
            "pnl": s["total_pnl"],
            "end_market_value": s["total_end_market_value"],
            "pnl_pct": s["total_pnl_pct"],
        })

    return result
