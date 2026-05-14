#!/usr/bin/env python3
"""测试东方财富行业板块接口"""
import akshare as ak
import time

# 1. 获取行业板块列表
print("=" * 50)
print("1. 获取东方财富行业板块列表")
print("=" * 50)

try:
    df_list = ak.stock_board_industry_name_em()
    print(f"获取成功，共 {len(df_list)} 个板块")
    print(df_list.head(10))
    print("\n列名:", df_list.columns.tolist())
except Exception as e:
    print(f"获取失败: {e}")
    exit(1)

# 2. 获取第一个板块的历史行情（测试全量数据）
print("\n" + "=" * 50)
print("2. 获取单个板块历史行情（全量）")
print("=" * 50)

first_board = df_list.iloc[0]["板块名称"]
print(f"测试板块: {first_board}")

try:
    # 东方财富接口：start_date/end_date 格式 YYYYMMDD，传空字符串或不传可能获取全量
    df_hist = ak.stock_board_industry_hist_em(symbol=first_board, period="日k",
                                               start_date="19900101",
                                               end_date="20261231")
    print(f"获取成功，共 {len(df_hist)} 条数据")
    print(df_hist.head())
    print("\n列名:", df_hist.columns.tolist())
    if len(df_hist) > 0:
        print(f"\n日期范围: {df_hist['日期'].min()} ~ {df_hist['日期'].max()}")
except Exception as e:
    print(f"获取失败: {e}")
    exit(1)

print("\n测试完成")
