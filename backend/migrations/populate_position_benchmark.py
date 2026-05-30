#!/usr/bin/env python3
"""
填充 positions 表的 benchmark_index 字段

逻辑：
1. 联接基金 -> 通过 linked_code 找到ETF -> ETF关联指数
2. 直接持有的ETF -> 直接关联指数
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal

# ETF -> 指数映射（从之前的asset_meta迁移数据）
ETF_INDEX_MAP = {
    '159326': '931994',   # 电网设备
    '159530': 'H30590',   # 机器人
    '159695': '931079',   # 通信
    '515150': '000859',   # 国企一带一路
    '517380': '931152',   # 创新药
    '159652': '000819',   # 有色金属
    '513530': '932596',   # 港股通红利
    '159201': '932365',   # 现金流
    '562030': '931247',   # 信创
    # 直接ETF持仓的映射
    '512660': None,       # 军工ETF - 需要确定指数
    '159715': None,       # 电池ETF - 需要确定指数
    '159995': None,       # 芯片ETF - 需要确定指数
}

# 联接基金直接映射到指数（避免通过ETF中转）
FUND_INDEX_MAP = {
    '025856': '931994',   # 联接基金 -> 电网设备指数
    '020972': 'H30590',   # 联接基金 -> 机器人指数
    '023917': '932365',   # 联接基金 -> 现金流指数
    '007786': '000859',   # 联接基金 -> 国企一带一路指数
    '018387': '932596',   # 联接基金 -> 港股通红利指数
    '014564': '931152',   # 联接基金 -> 创新药指数
    '019071': '931079',   # 联接基金 -> 通信指数
    '024050': '931247',   # 联接基金 -> 信创指数
    '019164': '000819',   # 联接基金 -> 有色金属指数
}


def populate():
    db = SessionLocal()
    
    try:
        from models import Position
        
        positions = db.query(Position).all()
        updated = 0
        
        for pos in positions:
            index_code = None
            
            # 1. 如果是联接基金，优先使用直接映射
            if pos.code in FUND_INDEX_MAP:
                index_code = FUND_INDEX_MAP[pos.code]
            # 2. 如果有linked_code，通过ETF映射
            elif pos.linked_code and pos.linked_code in ETF_INDEX_MAP:
                index_code = ETF_INDEX_MAP[pos.linked_code]
            # 3. 如果本身就是ETF
            elif pos.code in ETF_INDEX_MAP:
                index_code = ETF_INDEX_MAP[pos.code]
            
            if index_code:
                pos.benchmark_index = index_code
                updated += 1
                print(f"  {pos.code} -> {index_code}")
            else:
                print(f"  {pos.code} -> 无映射")
        
        db.commit()
        print(f"\n✓ 已更新 {updated} 条持仓记录")
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ 失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    populate()
