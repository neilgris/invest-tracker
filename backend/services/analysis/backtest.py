"""
参数网格搜索 & 策略回测服务
=============================
run_grid_search: 对单一退出模式扫描参数笛卡尔积，按目标排序，返回 top 组合 + 热力图 + 样本外验证

性能设计：
  - 网格搜索阶段用 _sim_exit_vec（numpy 向量化）+ _run_cohort_fast（不建 equity 曲线）
  - 只对最优组合调用 _run_cohort（完整 equity 曲线 + 详细 trade 信息）
"""

import itertools
import numpy as np
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# 1. 数据加载
# ═══════════════════════════════════════════════════════════════

def _load_prices(db, code: str, start=None, end=None):
    """返回 (date_str, close) 列表，按日期正序。"""
    from models import HistQuotesCache
    q = db.query(HistQuotesCache.date, HistQuotesCache.close).filter(
        HistQuotesCache.code == code,
        HistQuotesCache.close.isnot(None),
    )
    if start:
        q = q.filter(HistQuotesCache.date >= start)
    if end:
        q = q.filter(HistQuotesCache.date <= end)
    rows = q.order_by(HistQuotesCache.date).all()
    return [(r.date.isoformat(), float(r.close)) for r in rows]


# ═══════════════════════════════════════════════════════════════
# 2. 参数网格展开
# ═══════════════════════════════════════════════════════════════

_MODE_PARAMS = {
    "simple":           ["take_profit_pct"],
    "pmax_drawdown":    ["pmax_drawdown_pct"],
    "profit_retention": ["profit_trigger_pct", "profit_retention_pct"],
    "cost_protection":  ["cost_trigger_pct",   "cost_floor_pct"],
    "ma_cross":         ["ma_period"],
}
# ma_entry_period: 0=不限，>0=仅在 close > MA(N) 时入场
_COMMON_PARAMS = ["stop_loss_pct", "reentry_cooldown", "reentry_pullback_pct", "ma_entry_period"]


def _compute_ma(closes: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average，前 period-1 个点设为 NaN。"""
    if period <= 1:
        return closes.astype(float)
    ma  = np.full(len(closes), np.nan)
    ker = np.ones(period) / period
    valid = np.convolve(closes, ker, mode="valid")
    ma[period - 1:] = valid
    return ma


def _arange(start, stop, step):
    if step <= 0 or start >= stop:
        return [start]
    vals, v = [], start
    while v <= stop + step * 1e-9:
        vals.append(round(v, 6))
        v += step
    return vals


def _expand_grid(exit_mode: str, grid: dict, max_combos: int):
    sweep_keys = _COMMON_PARAMS + _MODE_PARAMS.get(exit_mode, [])
    axes = {}
    for key in sweep_keys:
        spec = grid.get(key, {})
        mn, mx, st = spec.get("min", 0), spec.get("max", 0), spec.get("step", 0)
        axes[key] = _arange(mn, mx, st) if st > 0 and mx > mn else [mn]

    swept  = [k for k, v in axes.items() if len(v) > 1]
    keys   = list(axes.keys())
    combos = list(itertools.product(*[axes[k] for k in keys]))
    if len(combos) > max_combos:
        combos = combos[:max_combos]
    return [{keys[i]: c[i] for i in range(len(keys))} for c in combos], swept


# ═══════════════════════════════════════════════════════════════
# 3a. 单笔交易模拟 — Python 循环版（用于完整 trade 信息）
# ═══════════════════════════════════════════════════════════════

def _sim_exit(closes: np.ndarray, entry_i: int, exit_mode: str, params: dict,
              ma_exit: np.ndarray = None):
    """返回 (exit_i, reason, pct, max_drawdown_pct)"""
    EPS = 1e-9
    n = len(closes)
    entry_price = closes[entry_i]
    peak = entry_price
    trough_from_peak = 0.0
    activated = False

    stop_loss_pct   = float(params.get("stop_loss_pct", 8.0))
    max_hold_days   = int(params.get("max_hold_days", 0) or 0)
    take_profit_pct = float(params.get("take_profit_pct", 15.0))
    pmax_dd_pct     = float(params.get("pmax_drawdown_pct", 15.0))
    trigger_pct     = float(params.get("profit_trigger_pct") or params.get("cost_trigger_pct") or 20.0)
    retention_pct   = float(params.get("profit_retention_pct", 0.5))
    floor_pct       = float(params.get("cost_floor_pct", 0.0))

    for i in range(entry_i + 1, n):
        c    = closes[i]
        ret  = float((c / entry_price - 1) * 100)
        hold = i - entry_i

        if c > peak:
            peak = c
        dd_from_peak     = float((c / peak - 1) * 100)
        trough_from_peak = min(trough_from_peak, dd_from_peak)

        if max_hold_days > 0 and hold >= max_hold_days:
            return i, "时间止损", round(ret, 4), round(-trough_from_peak, 4)
        if ret <= -(stop_loss_pct - EPS):
            return i, "止损", round(ret, 4), round(-trough_from_peak, 4)

        if exit_mode == "simple":
            if ret >= take_profit_pct - EPS:
                return i, "止盈", round(ret, 4), round(-trough_from_peak, 4)
        elif exit_mode == "pmax_drawdown":
            if dd_from_peak <= -(pmax_dd_pct - EPS):
                return i, "止损", round(ret, 4), round(-trough_from_peak, 4)
        elif exit_mode == "profit_retention":
            peak_ret = float((peak / entry_price - 1) * 100)
            if not activated and peak_ret >= trigger_pct - EPS:
                activated = True
            if activated and ret <= peak_ret * retention_pct + EPS:
                return i, ("止盈" if ret > 0 else "止损"), round(ret, 4), round(-trough_from_peak, 4)
        elif exit_mode == "cost_protection":
            if not activated and ret >= trigger_pct - EPS:
                activated = True
            if activated and ret <= floor_pct + EPS:
                return i, ("止盈" if ret > 0 else "止损"), round(ret, 4), round(-trough_from_peak, 4)
        elif exit_mode == "ma_cross":
            # 价格跌破 MA 时出场；MA 数组在外部按全价格序列预计算
            if ma_exit is not None and i < len(ma_exit) and not np.isnan(ma_exit[i]):
                if c < float(ma_exit[i]):
                    return i, ("止盈" if ret > 0 else "止损"), round(ret, 4), round(-trough_from_peak, 4)

    final_ret = float((closes[-1] / entry_price - 1) * 100)
    return n - 1, "持有中", round(final_ret, 4), round(-trough_from_peak, 4)


# ═══════════════════════════════════════════════════════════════
# 3b. 单笔交易模拟 — numpy 向量化版（用于网格搜索快速路径）
# ═══════════════════════════════════════════════════════════════

def _sim_exit_vec(closes: np.ndarray, entry_i: int, exit_mode: str, params: dict,
                  ma_exit: np.ndarray = None):
    """
    向量化版本，比 Python 循环快 15-30x。
    返回 (exit_i, reason, pct)
    ma_exit: 预计算的 MA 数组（与 closes 等长），仅 ma_cross 模式使用。
    """
    EPS = 1e-9
    n = len(closes)
    if entry_i >= n - 1:
        return n - 1, "持有中", 0.0

    prices = closes[entry_i:]     # view，不复制
    m      = len(prices)
    entry  = float(prices[0])

    stop_loss_pct   = float(params.get("stop_loss_pct", 8.0))
    max_hold_days   = int(params.get("max_hold_days", 0) or 0)
    take_profit_pct = float(params.get("take_profit_pct", 15.0))
    pmax_dd_pct     = float(params.get("pmax_drawdown_pct", 15.0))
    trigger_pct     = float(params.get("profit_trigger_pct") or params.get("cost_trigger_pct") or 20.0)
    retention_pct   = float(params.get("profit_retention_pct", 0.5))
    floor_pct       = float(params.get("cost_floor_pct", 0.0))

    rets      = (prices / entry - 1.0) * 100.0
    peaks     = np.maximum.accumulate(prices)
    peak_rets = (peaks / entry - 1.0) * 100.0
    dd_peak   = (prices / peaks - 1.0) * 100.0

    sl_mask = rets <= -(stop_loss_pct - EPS)

    if exit_mode == "simple":
        tp_mask = rets >= take_profit_pct - EPS
    elif exit_mode == "pmax_drawdown":
        tp_mask = dd_peak <= -(pmax_dd_pct - EPS)
    elif exit_mode == "profit_retention":
        activated = peak_rets >= trigger_pct - EPS
        tp_mask   = activated & (rets <= peak_rets * retention_pct + EPS)
    elif exit_mode == "cost_protection":
        activated = np.maximum.accumulate(rets) >= trigger_pct - EPS
        tp_mask   = activated & (rets <= floor_pct + EPS)
    elif exit_mode == "ma_cross":
        if ma_exit is not None:
            ma_slice = ma_exit[entry_i:entry_i + m]
            valid    = ~np.isnan(ma_slice)
            tp_mask  = valid & (prices < ma_slice)
        else:
            tp_mask = np.zeros(m, dtype=bool)
    else:
        tp_mask = np.zeros(m, dtype=bool)

    if max_hold_days > 0:
        th_mask = np.arange(m) >= max_hold_days
    else:
        th_mask = np.zeros(m, dtype=bool)

    any_exit    = sl_mask | tp_mask | th_mask
    any_exit[0] = False   # 入场当天不退出

    idxs = np.where(any_exit)[0]
    if len(idxs) == 0:
        i = m - 1
        return entry_i + i, "持有中", round(float(rets[i]), 4)

    i   = int(idxs[0])
    ret = round(float(rets[i]), 4)

    if th_mask[i]:
        reason = "时间止损"
    elif sl_mask[i]:
        reason = "止损"
    else:
        reason = ("止盈" if ret > 0 else "止损")   # MA 穿越：盈利出=止盈，亏损出=止损

    return entry_i + i, reason, ret


# ═══════════════════════════════════════════════════════════════
# 4a. 完整 cohort 模拟（建 equity 曲线，用于最优组合详情）
# ═══════════════════════════════════════════════════════════════

def _run_cohort(dates, closes, start_i: int, end_i: int,
                exit_mode: str, params: dict, reentry_cooldown: int):
    """完整版：返回 (trades_list, equity_curve)"""
    n   = end_i + 1
    nav = 1.0
    equity, trades = [], []
    cooldown_until = start_i

    for j in range(start_i):
        equity.append((dates[j], round(nav, 6)))

    # 预计算 MA 数组
    ma_entry_period = int(params.get("ma_entry_period", 0))
    ma_exit_period  = int(params.get("ma_period", 60)) if exit_mode == "ma_cross" else 0
    ma_entry = _compute_ma(closes[:n], ma_entry_period) if ma_entry_period > 0 else None
    ma_exit  = _compute_ma(closes[:n], ma_exit_period)  if ma_exit_period  > 0 else None

    j = start_i
    while j < n:
        if j >= cooldown_until and _can_enter(closes, j, params, ma_entry):
            entry_price = closes[j]
            exit_i, reason, pct, max_dd = _sim_exit(closes[:n], j, exit_mode, params, ma_exit)
            for k in range(j, exit_i + 1):
                equity.append((dates[k], round(float(nav * closes[k] / entry_price), 6)))
            trades.append({
                "buy_date":     dates[j],
                "buy_price":    round(float(entry_price), 4),
                "sell_date":    dates[exit_i] if reason != "持有中" else None,
                "sell_price":   round(float(closes[exit_i]), 4),
                "pct":          round(float(pct), 4),
                "sell_reason":  reason,
                "max_drawdown": round(float(max_dd), 4),
            })
            nav *= 1.0 + pct / 100.0
            cooldown_until = exit_i + 1 + reentry_cooldown
            j = exit_i + 1
        else:
            equity.append((dates[j], round(nav, 6)))
            j += 1

    while len(equity) < n:
        equity.append((dates[len(equity)], round(nav, 6)))

    return trades, equity


# ═══════════════════════════════════════════════════════════════
# 4b. 快速 cohort 模拟（无 equity 曲线，用于网格搜索评分）
# ═══════════════════════════════════════════════════════════════

def _can_enter(closes: np.ndarray, j: int, params: dict, ma_entry: np.ndarray = None) -> bool:
    """
    检查 j 日是否满足入场条件（所有条件须同时满足）：
    1. 回撤入场：reentry_pullback_pct > 0 时，close 需从近N日高点回落该比例
    2. MA 入场过滤：ma_entry_period > 0 时，close > MA(N)（趋势过滤，避免在熊市中买入）
    """
    # 条件1：回撤入场
    pullback_pct = float(params.get("reentry_pullback_pct", 0.0))
    if pullback_pct > 0:
        lookback  = int(params.get("reentry_lookback", 60))
        lb_start  = max(0, j - lookback)
        recent_hi = float(np.max(closes[lb_start:j + 1]))
        if (recent_hi - float(closes[j])) / recent_hi * 100.0 < pullback_pct:
            return False

    # 条件2：MA 趋势过滤
    if ma_entry is not None and j < len(ma_entry):
        ma_val = ma_entry[j]
        if not np.isnan(ma_val) and float(closes[j]) < float(ma_val):
            return False

    return True


def _run_cohort_fast(closes: np.ndarray, start_i: int, end_i: int,
                     exit_mode: str, params: dict, reentry_cooldown: int):
    """
    轻量版：不建逐日 equity 曲线，但对每笔交易的价格切片做 numpy 向量化 max_drawdown 计算。
    数学上与完整版完全等价，比完整版快 8-12x。
    返回 (simple_trades, final_nav, exact_max_drawdown_pct)
    """
    n              = end_i + 1
    nav            = 1.0
    peak_nav       = 1.0
    max_dd         = 0.0
    trades         = []
    cooldown_until = start_i
    j              = start_i

    # 预计算 MA 数组（仅在需要时）
    ma_entry_period = int(params.get("ma_entry_period", 0))
    ma_exit_period  = int(params.get("ma_period", 60)) if exit_mode == "ma_cross" else 0
    ma_entry = _compute_ma(closes[:n], ma_entry_period) if ma_entry_period > 0 else None
    ma_exit  = _compute_ma(closes[:n], ma_exit_period)  if ma_exit_period  > 0 else None

    while j < n:
        if j >= cooldown_until and _can_enter(closes, j, params, ma_entry):
            exit_i, reason, pct = _sim_exit_vec(closes[:n], j, exit_mode, params, ma_exit)
            nav_entry    = nav
            entry_price  = float(closes[j])

            # ── 精确计算持仓期内的组合最大回撤 ──────────────
            # portfolio_navs[t] = nav_entry * closes[j+t] / entry_price
            # 与完整路径的 equity curve 数学完全等价，只是不逐日存储
            prices_slice   = closes[j:exit_i + 1]
            portfolio_navs = nav_entry * prices_slice / entry_price
            # running_peak 含入场前的峰值，和完整路径中 _max_drawdown_from_curve 一致
            running_peak   = np.maximum(peak_nav, np.maximum.accumulate(portfolio_navs))
            dd_arr         = (running_peak - portfolio_navs) / running_peak * 100.0
            trade_max_dd   = float(np.max(dd_arr))
            if trade_max_dd > max_dd:
                max_dd = trade_max_dd

            # 更新组合峰值（取 running_peak 末值，包含持仓期最高点）
            peak_nav = float(running_peak[-1])
            nav      = float(portfolio_navs[-1])   # = nav_entry * (1 + pct/100)

            trades.append({"pct": pct, "sell_reason": reason})
            cooldown_until = exit_i + 1 + reentry_cooldown
            j = exit_i + 1
        else:
            j += 1

    return trades, nav, max_dd


# ═══════════════════════════════════════════════════════════════
# 5. 统计计算
# ═══════════════════════════════════════════════════════════════

def _max_drawdown_from_curve(navs) -> float:
    """numpy 加速版：比 Python 循环快 ~50x。"""
    arr  = np.asarray(navs, dtype=float)
    peak = np.maximum.accumulate(arr)
    dd   = (peak - arr) / np.where(peak > 0, peak, 1.0) * 100.0
    return round(float(np.max(dd)), 2)


def _whipsaw_count(trades, closes, dates, date_idx: dict, window: int) -> int:
    """
    Whipsaw：止损出场后，价格在 window 个交易日内反弹超过【入场价】的次数。
    比较基准用入场价（buy_price）而非卖出价（sell_price）：
      - 以卖出价为基准：哪怕涨 0.1% 就算 Whipsaw，噪声极大（常年 100%）
      - 以入场价为基准：说明持有不动本可盈利，止损是真正的"冤枉单"
    """
    count = 0
    for t in trades:
        if t.get("sell_reason") != "止损":
            continue
        sell_d = t.get("sell_date")
        if not sell_d:
            continue
        si = date_idx.get(sell_d)
        if si is None:
            continue
        entry_price = t["buy_price"]   # 以入场价为回弹判断基准
        for k in range(si + 1, min(si + 1 + window, len(closes))):
            if closes[k] > entry_price:
                count += 1
                break
    return count


def _distribution(vals: list) -> dict:
    if not vals:
        return {"p10": 0, "p25": 0, "p50": 0, "p75": 0, "p90": 0}
    arr = sorted(vals)
    def pct(p):
        idx = (len(arr) - 1) * p / 100
        lo, hi = int(idx), min(int(idx) + 1, len(arr) - 1)
        return round(arr[lo] + (arr[hi] - arr[lo]) * (idx - lo), 2)
    return {"p10": pct(10), "p25": pct(25), "p50": pct(50), "p75": pct(75), "p90": pct(90)}


def _annualized_return(final_nav: float, n_days: int) -> float:
    """年化收益率（%），基于交易日数折算，252交易日/年。"""
    if n_days <= 0 or final_nav <= 0:
        return 0.0
    return round((final_nav ** (252.0 / n_days) - 1.0) * 100.0, 2)


def _profit_factor(completed_trades: list) -> float:
    """盈亏比 = 所有盈利之和 / |所有亏损之和|。>1.5合格，>2.0优秀。"""
    gains  = sum(t["pct"] for t in completed_trades if t["pct"] > 0)
    losses = sum(abs(t["pct"]) for t in completed_trades if t["pct"] <= 0)
    return round(gains / losses, 2) if losses > 0.001 else float("inf")


def _max_consecutive_losses(completed_trades: list) -> int:
    """最大连续亏损次数。"""
    max_streak = cur = 0
    for t in completed_trades:
        if t["pct"] <= 0:
            cur += 1
            max_streak = max(max_streak, cur)
        else:
            cur = 0
    return max_streak


def _dd_recovery_days(equity_navs: list) -> int:
    """最大回撤的恢复期（从回撤最低点到重新创新高的交易日数）。"""
    arr = np.asarray(equity_navs, dtype=float)
    # 找最大回撤区间
    peak_val = arr[0]; peak_i = 0
    max_dd_val = 0.0; max_dd_start = 0; max_dd_trough_i = 0
    for i, v in enumerate(arr):
        if v >= peak_val:
            peak_val = v; peak_i = i
        dd = (peak_val - v) / peak_val * 100.0
        if dd > max_dd_val:
            max_dd_val = dd
            max_dd_start = peak_i
            max_dd_trough_i = i
    # 从最低点往后找恢复到前高的第一天
    recovery_price = arr[max_dd_start]
    for i in range(max_dd_trough_i, len(arr)):
        if arr[i] >= recovery_price:
            return i - max_dd_trough_i
    return len(arr) - max_dd_trough_i  # 未恢复，返回剩余天数


def _sortino_ratio(equity_navs: list, n_days: int) -> float:
    """Sortino = 年化收益 / 下行年化标准差（只惩罚下行波动）。"""
    arr        = np.asarray(equity_navs, dtype=float)
    daily_rets = np.diff(arr) / arr[:-1]
    down_rets  = daily_rets[daily_rets < 0]
    if len(down_rets) < 2:
        return 0.0
    downside_std_ann = float(np.std(down_rets)) * np.sqrt(252)
    ann_ret          = _annualized_return(float(arr[-1]), n_days) / 100.0
    return round(ann_ret / downside_std_ann, 2) if downside_std_ann > 0.001 else 0.0


def _cohort_stats_fast(trades, final_nav: float, max_dd: float,
                        bh_total_return: float, bh_max_dd: float, n_days: int):
    """
    网格搜索用：计算评分所需指标 + 年化收益 + Profit Factor。
    不做任何 O(n) 字符串查找。
    """
    completed    = [t for t in trades if t["sell_reason"] != "持有中"]
    total_return = round((final_nav - 1.0) * 100.0, 2)
    ann_return   = _annualized_return(final_nav, n_days)
    capture_rate = total_return / bh_total_return if abs(bh_total_return) > 0.01 else 0.0
    dd_reduction = round((bh_max_dd - max_dd) / bh_max_dd * 100.0, 1) if bh_max_dd > 0.01 else 0.0
    pf           = _profit_factor(completed)
    return {
        "total_return":     total_return,
        "ann_return":       ann_return,
        "max_drawdown":     round(max_dd, 2),
        "capture_rate":     round(capture_rate, 4),
        "dd_reduction_pct": dd_reduction,
        "profit_factor":    pf if pf != float("inf") else 99.9,
        "whipsaw_rate_pct": 0.0,
        "time_in_market_pct": 0,
        "completed_trades": len(completed),
        "win_rate": round(sum(1 for t in completed if t["pct"] > 0) / max(len(completed), 1) * 100.0, 1),
    }


def _cohort_stats_full(trades, equity_navs, bh_total_return, bh_max_dd,
                        whipsaw_window, closes, date_idx):
    """完整版：供最优组合详情页使用，含所有扩展指标。"""
    completed    = [t for t in trades if t["sell_reason"] != "持有中"]
    n_days       = len(equity_navs)
    total_return = round((equity_navs[-1] - 1.0) * 100.0, 2)
    ann_return   = _annualized_return(float(equity_navs[-1]), n_days)
    max_dd       = _max_drawdown_from_curve(equity_navs)
    capture_rate = total_return / bh_total_return if abs(bh_total_return) > 0.01 else 0.0
    dd_reduction = round((bh_max_dd - max_dd) / bh_max_dd * 100.0, 1) if bh_max_dd > 0.01 else 0.0

    stop_loss_count = sum(1 for t in completed if t["sell_reason"] == "止损")
    ws_count        = _whipsaw_count(trades, closes, list(date_idx.keys()), date_idx, whipsaw_window)
    whipsaw_rate    = round(ws_count / stop_loss_count * 100.0, 1) if stop_loss_count > 0 else 0.0

    pf            = _profit_factor(completed)
    max_consec    = _max_consecutive_losses(completed)
    recovery_days = _dd_recovery_days(equity_navs)
    sortino       = _sortino_ratio(equity_navs, n_days)

    wins   = [t["pct"] for t in completed if t["pct"] > 0]
    losses = [t["pct"] for t in completed if t["pct"] <= 0]

    return {
        "total_return":     total_return,
        "ann_return":       ann_return,
        "max_drawdown":     max_dd,
        "capture_rate":     round(capture_rate, 4),
        "dd_reduction_pct": dd_reduction,
        "profit_factor":    pf if pf != float("inf") else 99.9,
        "max_consec_loss":  max_consec,
        "recovery_days":    recovery_days,
        "sortino":          sortino,
        "whipsaw_rate_pct": whipsaw_rate,
        "avg_win":          round(sum(wins) / len(wins), 2) if wins else 0.0,
        "avg_loss":         round(sum(losses) / len(losses), 2) if losses else 0.0,
        "time_in_market_pct": 0,
        "completed_trades": len(completed),
        "win_rate": round(len(wins) / max(len(completed), 1) * 100.0, 1),
    }


def _score(stat: dict, objective: str) -> float:
    """
    排序目标得分。Calmar 改用年化收益（而非总收益）：
    - 避免测试区间长短影响得分
    - 年化收益 / 最大回撤 = 标准 Calmar Ratio
    """
    ann = stat.get("ann_return", stat["total_return"])   # 兼容旧代码
    dd  = stat["max_drawdown"] or 0.001
    cap = stat["capture_rate"]
    ddr = stat["dd_reduction_pct"]
    if objective == "calmar":
        return round(ann / dd, 4) if dd > 0 else 0.0
    elif objective == "total_return":
        return round(stat["total_return"], 4)
    elif objective == "capture":
        return round(cap, 4)
    elif objective == "dd_reduction":
        return round(ddr, 4)
    return round(ann / dd, 4)


# ═══════════════════════════════════════════════════════════════
# 6. 主入口
# ═══════════════════════════════════════════════════════════════

def run_grid_search(db, code: str, exit_mode: str, grid: dict,
                    objective: str, entry_freq: int, whipsaw_window: int,
                    max_combos: int, top_n: int,
                    train_end: Optional[str], oos_top_n: int,
                    reentry_lookback: int = 60):

    # ── 加载数据 ───────────────────────────────────────────
    all_data = _load_prices(db, code)
    if len(all_data) < 20:
        return {"ok": False, "message": f"数据不足（仅 {len(all_data)} 条）"}

    all_dates  = [d for d, _ in all_data]
    all_closes = np.array([c for _, c in all_data], dtype=float)

    # 样本内 / 样本外分割
    if train_end:
        is_end_i = next((i for i, d in enumerate(all_dates) if d > train_end), len(all_dates)) - 1
        is_end_i = max(is_end_i, 10)
    else:
        is_end_i = len(all_dates) - 1

    is_dates  = all_dates[:is_end_i + 1]
    is_closes = all_closes[:is_end_i + 1]

    has_oos    = bool(train_end and is_end_i < len(all_dates) - 10)
    oos_dates  = all_dates[is_end_i + 1:] if has_oos else []
    oos_closes = all_closes[is_end_i + 1:] if has_oos else np.array([])

    # ── B&H 基准 ───────────────────────────────────────────
    def _bh_return(c):
        return round(float((c[-1] / c[0] - 1) * 100), 2) if len(c) >= 2 else 0.0

    def _bh_curve(dates, closes):
        base = closes[0]
        return [[d, round(float(c) / float(base), 6)] for d, c in zip(dates, closes)]

    bh_return_is = _bh_return(is_closes)
    bh_dd_is     = _max_drawdown_from_curve(is_closes / is_closes[0])

    # ── 预计算 date_idx ─────────────────────────────────────
    date_idx_all = {d: i for i, d in enumerate(all_dates)}
    date_idx_is  = {d: i for i, d in enumerate(is_dates)}

    # ── 展开网格 ───────────────────────────────────────────
    combos, swept_params = _expand_grid(exit_mode, grid, max_combos)
    n_combos = len(combos)

    N_COHORTS     = entry_freq
    cohort_starts = [min(k * N_COHORTS, len(is_dates) - 1) for k in range(N_COHORTS)]

    # ── 网格搜索（快速路径）────────────────────────────────
    results = []
    for params in combos:
        params_full           = dict(params)
        params_full["exit_mode"]        = exit_mode
        params_full["reentry_lookback"] = reentry_lookback
        reentry               = int(params_full.get("reentry_cooldown", 20))

        stats_list = []
        for start_i in cohort_starts:
            trades, final_nav, max_dd = _run_cohort_fast(
                is_closes, start_i, is_end_i, exit_mode, params_full, reentry
            )
            n_days = is_end_i - start_i + 1
            stats_list.append(_cohort_stats_fast(trades, final_nav, max_dd,
                                                  bh_return_is, bh_dd_is, n_days))

        if not stats_list:
            continue

        # 取各指标中位数
        def _med(key):
            vals = sorted(s[key] for s in stats_list)
            return vals[len(vals) // 2]

        rep = {k: _med(k) for k in stats_list[0]}
        sc  = _score(rep, objective)
        results.append({
            "params":           params_full,
            "score":            round(sc, 4),
            "total_return_pct": round(rep["total_return"], 2),
            "ann_return_pct":   round(rep["ann_return"], 2),
            "max_drawdown":     round(rep["max_drawdown"], 2),
            "capture_rate":     round(rep["capture_rate"], 4),
            "dd_reduction_pct": round(rep["dd_reduction_pct"], 1),
            "profit_factor":    round(rep["profit_factor"], 2),
            "whipsaw_rate_pct": 0.0,
            "time_in_market_pct": 0,
        })

    if not results:
        return {"ok": False, "message": "所有参数组合均无有效交易，请扩大参数范围"}

    results.sort(key=lambda x: x["score"], reverse=True)
    top  = results[:top_n]
    best = top[0]
    best_params = dict(best["params"])
    best_params.setdefault("reentry_lookback", reentry_lookback)

    # ── 最优组合：完整路径（equity 曲线 + 详细 trades + whipsaw）──
    reentry_best  = int(best_params.get("reentry_cooldown", 20))
    best_trades_is, best_equity_is = _run_cohort(
        is_dates, is_closes, 0, is_end_i, exit_mode, best_params, reentry_best
    )
    best_navs_is = [v for _, v in best_equity_is]

    # 用完整 stats 补充 whipsaw 给 top[0]
    best_stat_full = _cohort_stats_full(
        best_trades_is, best_navs_is, bh_return_is, bh_dd_is,
        whipsaw_window, is_closes, date_idx_is
    )
    top[0]["whipsaw_rate_pct"] = best_stat_full["whipsaw_rate_pct"]
    best["whipsaw_rate_pct"]   = best_stat_full["whipsaw_rate_pct"]

    all_trade_pcts = [t["pct"] for t in best_trades_is if t["sell_reason"] != "持有中"]

    # ── OOS 详情 ───────────────────────────────────────────
    oos_trade_pcts = []
    best_trades    = best_trades_is

    if has_oos and len(oos_closes) > 0:
        last_nav = best_navs_is[-1] if best_navs_is else 1.0
        oos_trades_raw, oos_equity_raw = _run_cohort(
            oos_dates, oos_closes, 0, len(oos_dates) - 1,
            exit_mode, best_params, reentry_best
        )
        oos_navs_scaled = [last_nav * v for _, v in oos_equity_raw]
        full_curve      = best_equity_is + list(zip(oos_dates, [round(v, 6) for v in oos_navs_scaled]))
        oos_trade_pcts  = [t["pct"] for t in oos_trades_raw if t["sell_reason"] != "持有中"]
        best_trades     = best_trades_is + oos_trades_raw
    else:
        full_curve = best_equity_is

    full_bh = _bh_curve(all_dates[:len(full_curve)], all_closes[:len(full_curve)])

    # ── 样本外评分验证 ─────────────────────────────────────
    oos_results = []
    if has_oos and len(oos_closes) > 0:
        bh_return_oos = _bh_return(oos_closes)
        bh_dd_oos     = _max_drawdown_from_curve(oos_closes / oos_closes[0])
        for r in top[:oos_top_n]:
            p  = r["params"]
            rc = int(p.get("reentry_cooldown", 20))
            oos_ts, oos_nav, oos_dd = _run_cohort_fast(
                oos_closes, 0, len(oos_closes) - 1, exit_mode, p, rc
            )
            oos_stat  = _cohort_stats_fast(oos_ts, oos_nav, oos_dd, bh_return_oos, bh_dd_oos, len(oos_closes))
            is_score  = r["score"]
            oos_score = _score(oos_stat, objective)
            keep = round(oos_score / is_score * 100.0, 1) if abs(is_score) > 0.001 else None
            oos_results.append({
                "params":               {k: v for k, v in p.items() if k in swept_params},
                "is_total_return_pct":  r["total_return_pct"],
                "is_max_drawdown":      r["max_drawdown"],
                "oos_total_return_pct": round(oos_stat["total_return"], 2),
                "oos_max_drawdown":     round(oos_stat["max_drawdown"], 2),
                "oos_capture_rate":     round(oos_stat["capture_rate"], 4),
                "score_keep_pct":       keep,
            })

    # ── 热力图 ─────────────────────────────────────────────
    heatmap = None
    if len(swept_params) == 2:
        xk, yk = swept_params[0], swept_params[1]
        x_vals = sorted({r["params"].get(xk) for r in results})
        y_vals = sorted({r["params"].get(yk) for r in results})
        xi     = {v: i for i, v in enumerate(x_vals)}
        yi     = {v: i for i, v in enumerate(y_vals)}
        cells_map = {}
        for r in results:
            key = (xi[r["params"].get(xk)], yi[r["params"].get(yk)])
            if key not in cells_map or r["score"] > cells_map[key]:
                cells_map[key] = r["score"]
        heatmap = {
            "x_param": xk, "y_param": yk,
            "x_vals": x_vals, "y_vals": y_vals,
            "cells": [[xv, yv, round(sc, 4)] for (xv, yv), sc in cells_map.items()],
        }

    # ── 期间信息 ───────────────────────────────────────────
    train_period = {"start": is_dates[0], "end": is_dates[-1], "days": len(is_dates)}
    test_period  = None
    oos_bh_return = None
    if has_oos and len(oos_dates) > 0:
        test_period   = {"start": oos_dates[0], "end": oos_dates[-1], "days": len(oos_dates)}
        oos_bh_return = round(_bh_return(oos_closes), 2)

    # top 列表只保留 swept 参数
    top_display = []
    for r in top:
        entry = {k: v for k, v in r.items() if k != "params"}
        entry["params"] = {k: v for k, v in r["params"].items() if k in swept_params}
        top_display.append(entry)

    return {
        "ok":          True,
        "exit_mode":   exit_mode,
        "total_combos": n_combos,
        "sweep_params": swept_params,
        "best": {
            "params":             {k: v for k, v in best_params.items() if k in swept_params},
            "total_return_pct":   best["total_return_pct"],
            "ann_return_pct":     best["ann_return_pct"],
            "max_drawdown":       best["max_drawdown"],
            "capture_rate":       best["capture_rate"],
            "dd_reduction_pct":   best["dd_reduction_pct"],
            "profit_factor":      best["profit_factor"],
            "whipsaw_rate_pct":   best["whipsaw_rate_pct"],
            # 以下来自 full 路径（最优组合精确计算）
            "max_consec_loss":    best_stat_full.get("max_consec_loss", 0),
            "recovery_days":      best_stat_full.get("recovery_days", 0),
            "sortino":            best_stat_full.get("sortino", 0),
            "avg_win":            best_stat_full.get("avg_win", 0),
            "avg_loss":           best_stat_full.get("avg_loss", 0),
        },
        "benchmark_total_return_pct": round(bh_return_is, 2),
        "top":          top_display,
        "price_series": [[d, round(float(c), 4)] for d, c in zip(all_dates, all_closes)],
        "best_trades":  best_trades,
        "best_equity_curve": [[d, v] for d, v in full_curve],
        "best_bh_curve":     full_bh,
        "best_trade_distribution":    _distribution(all_trade_pcts),
        "train_period": train_period,
        "test_period":  test_period,
        "oos":          oos_results if oos_results else None,
        "oos_benchmark_total_return_pct": oos_bh_return,
        "best_is_trade_distribution":  _distribution(all_trade_pcts) if has_oos else None,
        "best_oos_trade_distribution": _distribution(oos_trade_pcts) if has_oos else None,
        "heatmap": heatmap,
    }
