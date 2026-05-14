#!/usr/bin/env python3
"""
测试 L2 行业板块列表获取
直接运行: python3 test_l2_list.py
"""

import sys
sys.path.insert(0, '/Users/neilgris/Documents/python/qclaw/invest-tracker/backend')

import akshare as ak
import time


def get_l2_industry_list():
    """获取 L2 行业板块列表（带重试）"""

    
    try:
        
        df = ak.stock_board_industry_name_em()
        if df is None or df.empty:
            print("返回数据为空")
            return None
        
        if "板块名称" in df.columns:
            result = df[["板块名称"]].copy()
            result.columns = ["name"]
            result["code"] = result["name"]
            return result[["code", "name"]]
        
        print(f"列名不匹配，实际列: {list(df.columns)}")
        return None
        
    except Exception as e:
        print(f"获取失败: {str(e)[:100]}")
        return None
    
    return None


def main():
    print("=" * 50)
    print("L2 行业板块列表获取测试")
    print("=" * 50)
    print()
    
    df = get_l2_industry_list()
    
    if df is not None:
        print(f"\n✓ 成功获取 {len(df)} 个行业板块")
        print("\n前 20 个板块:")
        print("-" * 40)
        for idx, row in df.head(20).iterrows():
            print(f"  {idx + 1}. {row['name']}")
        
        if len(df) > 20:
            print(f"  ... 还有 {len(df) - 20} 个板块")
        
        print("\n完整列表:")
        print(df.to_string(index=False))
    else:
        print("\n✗ 获取失败")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
