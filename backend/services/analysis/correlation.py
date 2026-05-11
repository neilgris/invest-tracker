
"""
相关性分析模块
==============
- 两两皮尔逊相关系数
- 滚动窗口相关性
- 交叉相关函数（CCF）领先滞后
- Granger 因果检验
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Optional
from datetime import date

from services.analysis.data_fetcher import get_cached_data


# ══════════════════════════════════════════════════════
# 皮尔逊相关系数
# ══════════════════════════════════════════════════════

def pearson_correlation(
    code_a: str,
    code_b: str,
    start_date: date = None,
    end_date: date = None,
    field: str = "pct_change",
) -> dict:
    """
    计算两个标的的皮尔逊相关系数。
    field: 用哪个字段计算（pct_change / close / volume）
    返回 {correlation, p_value, n, code_a, code_b}
    """
    df_a = get_cached_data(code_a, start_date, end_date, ["date", field])
    df_b = get_cached_data(code_b, start_date, end_date, ["date", field])

    if df_a.empty or df_b.empty:
        return {"ok": False, "message": "无缓存数据"}

    # 按日期对齐
    merged = pd.merge(df_a, df_b, on="date", suffixes=("_a", "_b"))
    if len(merged) < 10:
        return {"ok": False, "message": f"有效数据点不足({len(merged)}), 至少10个"}

    a = merged[f"{field}_a"].dropna().values
    b = merged[f"{field}_b"].dropna().values
    # 再对齐一次（dropna 后长度可能不同，取交集）
    min_len = min(len(a), len(b))
    a, b = a[:min_len], b[:min_len]

    r, p = stats.pearsonr(a, b)
    return {
        "ok": True,
        "correlation": round(float(r), 4),
        "p_value": round(float(p), 6),
        "n": min_len,
        "code_a": code_a,
        "code_b": code_b,
        "field": field,
    }


def correlation_matrix(
    codes: list[str],
    start_date: date = None,
    end_date: date = None,
    field: str = "pct_change",
) -> dict:
    """
    多标的的相关系数矩阵。
    返回 {codes, matrix: [[r, ...], ...]}
    """
    dfs = {}
    for code in codes:
        df = get_cached_data(code, start_date, end_date, ["date", field])
        if df.empty:
            continue
        df = df.rename(columns={field: code})
        dfs[code] = df

    if len(dfs) < 2:
        return {"ok": False, "message": "有效标的不足2个"}

    # 合并所有 DataFrame
    merged = None
    for code, df in dfs.items():
        if merged is None:
            merged = df
        else:
            merged = pd.merge(merged, df, on="date", how="inner")

    if len(merged) < 10:
        return {"ok": False, "message": f"有效数据点不足({len(merged)})"}

    # 计算相关矩阵
    valid_codes = [c for c in codes if c in merged.columns]
    corr = merged[valid_codes].corr()

    matrix = []
    for i, ca in enumerate(valid_codes):
        row = []
        for j, cb in enumerate(valid_codes):
            val = corr.iloc[i, j]
            row.append(round(float(val), 4) if not pd.isna(val) else None)
        matrix.append(row)

    return {
        "ok": True,
        "codes": valid_codes,
        "matrix": matrix,
        "n": len(merged),
    }


# ══════════════════════════════════════════════════════
# 滚动窗口相关性
# ══════════════════════════════════════════════════════

def rolling_correlation(
    code_a: str,
    code_b: str,
    window: int = 60,
    start_date: date = None,
    end_date: date = None,
    field: str = "pct_change",
) -> dict:
    """
    滚动窗口相关性（默认60日滚动）。
    返回 {dates: [...], values: [...], window}
    """
    df_a = get_cached_data(code_a, start_date, end_date, ["date", field])
    df_b = get_cached_data(code_b, start_date, end_date, ["date", field])

    if df_a.empty or df_b.empty:
        return {"ok": False, "message": "无缓存数据"}

    merged = pd.merge(df_a, df_b, on="date", suffixes=("_a", "_b"))
    if len(merged) < window:
        return {"ok": False, "message": f"数据量不足（{len(merged)} < window={window}）"}

    a = merged[f"{field}_a"]
    b = merged[f"{field}_b"]

    rolling_r = a.rolling(window).corr(b)

    # 去掉前 window-1 个 NaN
    valid = rolling_r.dropna()
    dates = merged["date"].iloc[window - 1:].tolist()
    values = [round(float(v), 4) if not pd.isna(v) else None for v in valid]

    return {
        "ok": True,
        "window": window,
        "dates": [str(d) for d in dates[:len(values)]],
        "values": values,
        "current": values[-1] if values else None,
    }


# ══════════════════════════════════════════════════════
# 交叉相关函数（CCF）领先滞后
# ══════════════════════════════════════════════════════

def cross_correlation(
    code_a: str,
    code_b: str,
    max_lag: int = 20,
    start_date: date = None,
    end_date: date = None,
    field: str = "pct_change",
) -> dict:
    """
    交叉相关函数：计算 A 领先/滞后 B 各 max_lag 期的相关系数。
    lag > 0 表示 A 领先 B；lag < 0 表示 A 滞后 B。
    返回 {lags: [...], values: [...], best_lag, best_corr}
    """
    df_a = get_cached_data(code_a, start_date, end_date, ["date", field])
    df_b = get_cached_data(code_b, start_date, end_date, ["date", field])

    if df_a.empty or df_b.empty:
        return {"ok": False, "message": "无缓存数据"}

    merged = pd.merge(df_a, df_b, on="date", suffixes=("_a", "_b"))
    if len(merged) < max_lag * 2:
        return {"ok": False, "message": f"数据量不足（需至少 {max_lag * 2} 个点）"}

    a = merged[f"{field}_a"].values
    b = merged[f"{field}_b"].values

    # 标准化
    a = (a - np.nanmean(a)) / (np.nanstd(a) + 1e-10)
    b = (b - np.nanmean(b)) / (np.nanstd(b) + 1e-10)

    lags = list(range(-max_lag, max_lag + 1))
    values = []
    for lag in lags:
        if lag >= 0:
            r = np.nanmean(a[:len(a) - lag] * b[lag:]) if lag < len(a) else 0.0
        else:
            r = np.nanmean(a[-lag:] * b[:len(b) + lag]) if -lag < len(b) else 0.0
        values.append(round(float(r), 4))

    # 找最大绝对值
    abs_vals = [abs(v) for v in values]
    best_idx = abs_vals.index(max(abs_vals))
    best_lag = lags[best_idx]
    best_corr = values[best_idx]

    return {
        "ok": True,
        "lags": lags,
        "values": values,
        "best_lag": best_lag,
        "best_corr": best_corr,
        "interpretation": f"{code_a} {'领先' if best_lag > 0 else '滞后' if best_lag < 0 else '同步'} {code_b} {abs(best_lag)} 期",
    }


# ══════════════════════════════════════════════════════
# Granger 因果检验
# ══════════════════════════════════════════════════════

def granger_causality(
    code_a: str,
    code_b: str,
    max_lag: int = 5,
    start_date: date = None,
    end_date: date = None,
    field: str = "pct_change",
) -> dict:
    """
    Granger 因果检验：A 的历史值是否有助于预测 B。
    检验多个滞后阶数（1 ~ max_lag），返回各阶的 F 统计量和 p 值。
    需要 statsmodels。
    """
    try:
        from statsmodels.tsa.stattools import grangercausalitytests
    except ImportError:
        return {"ok": False, "message": "需要安装 statsmodels: pip install statsmodels"}

    df_a = get_cached_data(code_a, start_date, end_date, ["date", field])
    df_b = get_cached_data(code_b, start_date, end_date, ["date", field])

    if df_a.empty or df_b.empty:
        return {"ok": False, "message": "无缓存数据"}

    merged = pd.merge(df_a, df_b, on="date", suffixes=("_a", "_b"))
    if len(merged) < max_lag * 3:
        return {"ok": False, "message": f"数据量不足（需至少 {max_lag * 3} 个点）"}

    # grangercausalitytests 需要 [B, A] 格式（检验 A 是否 Granger 导致 B）
    data = merged[[f"{field}_b", f"{field}_a"]].dropna().values

    try:
        result = grangercausalitytests(data, maxlag=max_lag, verbose=False)
    except Exception as e:
        return {"ok": False, "message": f"Granger 检验失败: {e}"}

    lags_result = []
    for lag in range(1, max_lag + 1):
        if lag in result:
            f_test = result[lag][0]["ssr_ftest"]
            lags_result.append({
                "lag": lag,
                "f_statistic": round(float(f_test[0]), 4),
                "p_value": round(float(f_test[1]), 6),
                "significant": float(f_test[1]) < 0.05,
            })

    # 找最佳滞后阶（最小 p 值）
    best = min(lags_result, key=lambda x: x["p_value"]) if lags_result else None

    return {
        "ok": True,
        "direction": f"{code_a} -> {code_b}",
        "lags": lags_result,
        "best_lag": best,
        "is_granger": best["significant"] if best else False,
    }
