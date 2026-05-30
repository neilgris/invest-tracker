#!/usr/bin/env python3
"""
清理 asset_meta 表：
1. 添加缺失的指数记录
2. 删除 ETF 记录（持仓信息不应存在于此表）
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from datetime import datetime

# 需要添加的指数信息
INDEX_DATA = [
    {'code': '931994', 'name': '中证电网设备主题指数', 'category': '行业主题'},
    {'code': 'H30590', 'name': '中证机器人指数', 'category': '行业主题'},
    {'code': '932365', 'name': '中证全指现金流指数', 'category': '策略'},
    {'code': '000859', 'name': '中证国企一带一路指数', 'category': '主题'},
    {'code': '932596', 'name': '中证港股通高股息投资指数', 'category': '策略'},
    {'code': '931152', 'name': '中证创新药产业指数', 'category': '行业主题'},
    {'code': '931079', 'name': '中证5G通信主题指数', 'category': '行业主题'},
    {'code': '931247', 'name': '中证信创指数', 'category': '行业主题'},
    {'code': '000819', 'name': '中证有色金属指数', 'category': '行业'},
]


def migrate():
    db = SessionLocal()
    
    try:
        from models import AssetMeta
        from sqlalchemy import text
        
        # 1. 添加缺失的指数记录
        print("添加缺失的指数记录...")
        added = 0
        for idx in INDEX_DATA:
            exists = db.query(AssetMeta).filter(AssetMeta.code == idx['code']).first()
            if not exists:
                asset = AssetMeta(
                    code=idx['code'],
                    name=idx['name'],
                    asset_type='index',
                    category=idx['category'],
                    source='csi',
                    is_cached=0,
                    updated_at=datetime.now()
                )
                db.add(asset)
                added += 1
                print(f"  + {idx['code']}: {idx['name']}")
        
        db.commit()
        print(f"✓ 已添加 {added} 条指数记录\n")
        
        # 2. 删除 ETF 记录
        print("删除 ETF 记录...")
        result = db.execute(text("DELETE FROM asset_meta WHERE asset_type = 'etf'"))
        db.commit()
        print(f"✓ 已删除 {result.rowcount} 条 ETF 记录\n")
        
        # 3. 验证结果
        print("验证结果:")
        idx_count = db.query(AssetMeta).filter(AssetMeta.asset_type == 'index').count()
        etf_count = db.query(AssetMeta).filter(AssetMeta.asset_type == 'etf').count()
        print(f"  指数记录: {idx_count}")
        print(f"  ETF记录: {etf_count}")
        
        print("\n=== 清理完成 ===")
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ 失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
