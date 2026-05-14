#!/usr/bin/env python3
"""
测试 L2 申万行业指数列表获取
直接运行: python3 test_l2_sw.py
"""

import sys
sys.path.insert(0, '/Users/neilgris/Documents/python/qclaw/invest-tracker/backend')

import akshare as ak
import time


def get_sw_industry_list():
    """获取申万一级行业列表"""
    try:
        print("正在获取申万一级行业列表...")
        df = ak.sw_index_first_info()
        if df is None or df.empty:
            print("返回数据为空")
            return None
        
        if "行业代码" in df.columns and "行业名称" in df.columns:
            result = df[["行业代码", "行业名称"]].copy()
            result.columns = ["code", "name"]
            return result
        
        print(f"列名不匹配，实际列: {list(df.columns)}")
        return None
        
    except Exception as e:
        print(f"获取失败: {str(e)[:100]}")
        return None


def get_sw_hist(symbol):
    """获取申万行业历史行情"""
    try:
        print(f"正在获取 {symbol} 历史行情...")
        symbol_clean = symbol.replace('.SI', '')
        df = ak.index_hist_sw(symbol=symbol_clean, period='day')
        if df is None or df.empty:
            print("返回数据为空")
            return None
        
        print(f"获取成功，共 {len(df)} 条数据")
        print("\n前5条:")
        print(df.head().to_string())
        return df
        
    except Exception as e:
        print(f"获取失败: {str(e)[:100]}")
        return None


def main():
    print("=" * 50)
    print("L2 申万行业指数测试")
    print("=" * 50)
    print()
    
    # 1. 获取列表
    df = get_sw_industry_list()
    
    if df is None:
        print("\n✗ 获取行业列表失败")
        return 1
    
    print(f"\n✓ 成功获取 {len(df)} 个申万一级行业")
    print("\n完整列表:")
    print("-" * 40)
    for idx, row in df.iterrows():
        print(f"  {idx + 1:2d}. {row['code']} - {row['name']}")
    
    # 2. 测试获取历史行情
    print("\n" + "=" * 50)
    print("测试历史行情获取")
    print("=" * 50)
    
    test_code = df.iloc[0]['code']
    test_name = df.iloc[0]['name']
    print(f"\n测试标的: {test_code} ({test_name})")
    
    hist_df = get_sw_hist(test_code)
    
    if hist_df is not None:
        print(f"\n✓ 历史行情获取成功")
    else:
        print(f"\n✗ 历史行情获取失败")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
