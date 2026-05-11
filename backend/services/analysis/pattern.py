
"""
特征规律挖掘模块
================
- 季节效应（月度/周几涨跌统计）
- 动量反转（N日动量因子 + 反转信号）
- 均值回归（偏离度 + 半衰期）
- 层次聚类（基于相关系数矩阵）
"""

import numpy as np
import pandas as pd
from scipy import stats
from datetime import date
from typing import Optional

from services.analysis.data_fetcher import get_cached_data


# ══════════════════════════════════════════════════════
# 季节效应
# ══════════════════════════════════════════════════════

def seasonality_monthly(
    code: str,
    start_date: date = None,
    end_date: date = None,
) -> dict:
    """月度季节效应：统计各月平均涨跌幅、胜率"""
    df = get_cached_data(code, start_date, end_date, ["date", "pct_change"])
    if df.empty:
        return {"ok": False, "message": "无缓存数据"}

    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.month
    df = df.dropna(subset=["pct_change"])

    result = []
    for m in range(1, 13):
        sub = df[df["month"] == m]
        if sub.empty:
            result.append({"month": m, "avg": None, "win_rate": None, "count": 0})
            continue
        avg = round(float(sub["pct_change"].mean()), 4)
        win_rate = round(float((sub["pct_change"] > 0).mean()), 4)
        result.append({
            "month": m,
            "avg_pct": avg,
            "win_rate": win_rate,
            "count": len(sub),
        })

    return {"ok": True, "code": code, "monthly": result}


def seasonality_weekday(
    code: str,
    start_date: date = None,
    end_date: date = None,
) -> dict:
    """周几效应：统计周一~周五平均涨跌幅、胜率"""
    df = get_cached_data(code, start_date, end_date, ["date", "pct_change"])
    if df.empty:
        return {"ok": False, "message": "无缓存数据"}

    df["date"] = pd.to_datetime(df["date"])
    df["weekday"] = df["date"].dt.weekday  # 0=Mon
    df = df.dropna(subset=["pct_change"])

    names = ["周一", "周二", "周三", "周四", "周五"]
    result = []
    for wd in range(5):
        sub = df[df["weekday"] == wd]
        if sub.empty:
            result.append({"weekday": wd, "name": names[wd], "avg_pct": None, "win_rate": None, "count": 0})
            continue
        result.append({
            "weekday": wd,
            "name": names[wd],
            "avg_pct": round(float(sub["pct_change"].mean()), 4),
            "win_rate": round(float((sub["pct_change"] > 0).mean()), 4),
            "count": len(sub),
        })

    return {"ok": True, "code": code, "weekday": result}


# ══════════════════════════════════════════════════════
# 动量反转
# ══════════════════════════════════════════════════════

def momentum_reversal(
    code: str,
    lookback: int = 20,
    hold: int = 5,
    start_date: date = None,
    end_date: date = None,
) -> dict:
    """
    动量/反转分析：
    - 过去 lookback 日累计涨跌幅排序分组
    - 统计各组后续 hold 日的平均收益
    - 正相关=动量效应，负相关=反转效应
    """
    df = get_cached_data(code, start_date, end_date, ["date", "close", "pct_change"])
    if df.empty or len(df) < lookback + hold:
        return {"ok": False, "message": f"数据不足（需至少 {lookback + hold} 个点）"}

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["past_ret"] = df["pct_change"].rolling(lookback).sum()
    df["future_ret"] = df["pct_change"].shift(-hold).rolling(hold).sum()

    df = df.dropna(subset=["past_ret", "future_ret"])
    if len(df) < 20:
        return {"ok": False, "message": "有效数据点不足"}

    # 按 past_ret 分5组
    df["group"] = pd.qcut(df["past_ret"], 5, labels=["最弱", "弱", "中", "强", "最强"], duplicates="drop")
    summary = df.groupby("group", observed=True)["future_ret"].agg(["mean", "count"])
    summary["win_rate"] = df.groupby("group", observed=True)["future_ret"].apply(lambda x: (x > 0).mean())

    groups = []
    for name, row in summary.iterrows():
        groups.append({
            "group": str(name),
            "avg_future_ret": round(float(row["mean"]), 4),
            "win_rate": round(float(row["win_rate"]), 4),
            "count": int(row["count"]),
        })

    # 整体相关性（past vs future）
    r, p = stats.pearsonr(df["past_ret"].values, df["future_ret"].values)

    return {
        "ok": True,
        "code": code,
        "lookback": lookback,
        "hold": hold,
        "groups": groups,
        "correlation": round(float(r), 4),
        "p_value": round(float(p), 6),
        "effect": "动量效应" if r > 0 else "反转效应",
    }


# ══════════════════════════════════════════════════════
# 均值回归
# ══════════════════════════════════════════════════════

def mean_reversion(
    code: str,
    window: int = 60,
    start_date: date = None,
    end_date: date = None,
) -> dict:
    """
    均值回归分析：
    - 计算价格偏离 MA 的 Z-score
    - 当 |Z| > 2 时标记为超买/超卖
    - 统计超买/超卖后 N 日回归概率
    """
    df = get_cached_data(code, start_date, end_date, ["date", "close"])
    if df.empty or len(df) < window:
        return {"ok": False, "message": f"数据不足（需至少 {window} 个点）"}

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["ma"] = df["close"].rolling(window).mean()
    df["std"] = df["close"].rolling(window).std()
    df["zscore"] = (df["close"] - df["ma"]) / df["std"]
    df = df.dropna(subset=["zscore"])

    # 标记超买超卖
    df["overbought"] = df["zscore"] > 2.0
    df["oversold"] = df["zscore"] < -2.0

    # 超买后5日/10日/20日收益
    for n in [5, 10, 20]:
        df[f"ret_{n}d"] = df["close"].shift(-n) / df["close"] - 1

    ob = df[df["overbought"]]
    os_ = df[df["oversold"]]

    ob_stats = {}
    os_stats = {}
    for n in [5, 10, 20]:
        col = f"ret_{n}d"
        if not ob.empty:
            ob_stats[f"{n}d"] = {
                "avg_ret": round(float(ob[col].mean()) * 100, 4) if not ob[col].empty else None,
                "revert_rate": round(float((ob[col] < 0).mean()) * 100, 2) if not ob[col].empty else None,
            }
        if not os_.empty:
            os_stats[f"{n}d"] = {
                "avg_ret": round(float(os_[col].mean()) * 100, 4) if not os_[col].empty else None,
                "revert_rate": round(float((os_[col] > 0).mean()) * 100, 2) if not os_[col].empty else None,
            }

    return {
        "ok": True,
        "code": code,
        "window": window,
        "current_zscore": round(float(df["zscore"].iloc[-1]), 4),
        "overbought_count": int(ob.shape[0]),
        "oversold_count": int(os_.shape[0]),
        "overbought_stats": ob_stats,
        "oversold_stats": os_stats,
        "latest_dates": {
            "date": str(df["date"].iloc[-1]),
            "close": float(df["close"].iloc[-1]),
            "zscore": round(float(df["zscore"].iloc[-1]), 4),
            "signal": "超买" if df["zscore"].iloc[-1] > 2 else "超卖" if df["zscore"].iloc[-1] < -2 else "正常",
        },
    }


# ══════════════════════════════════════════════════════
# 层次聚类
# ══════════════════════════════════════════════════════

def hierarchical_clustering(
    codes: list[str],
    start_date: date = None,
    end_date: date = None,
    field: str = "pct_change",
    n_clusters: int = 4,
) -> dict:
    """
    基于相关系数矩阵的层次聚类。
    将标的按走势相似度分组。
    需要 scipy。
    """
    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import squareform

    # 获取相关系数矩阵
    dfs = {}
    for code in codes:
        df = get_cached_data(code, start_date, end_date, ["date", field])
        if df.empty:
            continue
        df = df.rename(columns={field: code})
        dfs[code] = df

    if len(dfs) < 3:
        return {"ok": False, "message": "有效标的不足3个"}

    merged = None
    for code, df in dfs.items():
        if merged is None:
            merged = df
        else:
            merged = pd.merge(merged, df, on="date", how="inner")

    if len(merged) < 20:
        return {"ok": False, "message": f"数据点不足({len(merged)})"}

    valid_codes = [c for c in codes if c in merged.columns]
    corr = merged[valid_codes].corr().fillna(0)

    # 距离矩阵 = 1 - |相关系数|
    dist = 1 - corr.abs()
    np.fill_diagonal(dist.values, 0)
    # 保证对称
    dist = (dist + dist.T) / 2

    # 转换为压缩距离矩阵
    condensed = squareform(dist.values, checks=False)

    # 层次聚类
    Z = linkage(condensed, method="average")
    labels = fcluster(Z, t=n_clusters, criterion="maxclust")

    clusters = {}
    for code, label in zip(valid_codes, labels):
        label = int(label)
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(code)

    return {
        "ok": True,
        "n_clusters": n_clusters,
        "clusters": clusters,
        "codes_count": len(valid_codes),
    }
