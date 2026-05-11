
"""
分析报告生成模块
================
- 快速诊断报告（单标的）
- 两两关系报告
- 多标的对比报告
"""

import pandas as pd
from datetime import date

from services.analysis.data_fetcher import get_cached_data, get_cache_status
from services.analysis.correlation import pearson_correlation, cross_correlation
from services.analysis.pattern import seasonality_monthly, momentum_reversal, mean_reversion


def quick_report(code: str, start_date: date = None, end_date: date = None) -> dict:
    """
    单标的快速诊断报告：
    - 基本统计（总收益、年化、波动率、最大回撤）
    - 月度季节效应
    - 均值回归信号
    - 动量/反转特征
    """
    df = get_cached_data(code, start_date, end_date, ["date", "close", "pct_change", "volume"])
    if df.empty:
        return {"ok": False, "message": "无缓存数据"}

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # ── 基本统计 ─────────────────────────────────────
    total_days = len(df)
    pct = df["pct_change"].dropna()
    total_return = (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100 if df["close"].iloc[0] > 0 else 0
    years = total_days / 252
    annualized = ((1 + total_return / 100) ** (1 / max(years, 0.01)) - 1) * 100 if years > 0 else 0
    volatility = float(pct.std() * (252 ** 0.5)) if len(pct) > 1 else 0

    # 最大回撤
    cummax = df["close"].cummax()
    drawdown = (df["close"] - cummax) / cummax
    max_drawdown = float(drawdown.min()) * 100

    # Sharpe（无风险利率取 2%）
    avg_daily_ret = float(pct.mean())
    sharpe = (avg_daily_ret * 252 - 2) / (float(pct.std()) * (252 ** 0.5)) if float(pct.std()) > 0 else 0

    stats_basic = {
        "start_date": str(df["date"].iloc[0]),
        "end_date": str(df["date"].iloc[-1]),
        "total_days": total_days,
        "total_return_pct": round(total_return, 2),
        "annualized_return_pct": round(annualized, 2),
        "annualized_volatility_pct": round(volatility, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "sharpe_ratio": round(sharpe, 2),
        "avg_daily_pct": round(float(pct.mean()), 4),
        "avg_volume": round(float(df["volume"].mean()), 0) if "volume" in df.columns and df["volume"].notna().any() else None,
    }

    # ── 季节效应 ─────────────────────────────────────
    season = seasonality_monthly(code, start_date, end_date)

    # ── 均值回归 ─────────────────────────────────────
    mr = mean_reversion(code, 60, start_date, end_date)

    # ── 动量反转 ─────────────────────────────────────
    mom = momentum_reversal(code, 20, 5, start_date, end_date)

    return {
        "ok": True,
        "code": code,
        "basic": stats_basic,
        "seasonality": season,
        "mean_reversion": mr,
        "momentum": mom,
    }


def pair_report(
    code_a: str,
    code_b: str,
    start_date: date = None,
    end_date: date = None,
) -> dict:
    """两两关系报告：相关性 + CCF + 各自基本统计"""
    corr = pearson_correlation(code_a, code_b, start_date, end_date)
    ccf = cross_correlation(code_a, code_b, 20, start_date, end_date)
    rep_a = quick_report(code_a, start_date, end_date)
    rep_b = quick_report(code_b, start_date, end_date)

    return {
        "ok": True,
        "pair": f"{code_a} vs {code_b}",
        "correlation": corr,
        "cross_correlation": ccf,
        "report_a": rep_a,
        "report_b": rep_b,
    }
