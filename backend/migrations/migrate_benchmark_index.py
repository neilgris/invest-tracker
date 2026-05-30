#!/usr/bin/env python3
"""
迁移脚本：将 benchmark_index 从 asset_meta 表移到 positions 表

变更内容：
1. positions 表新增 benchmark_index 字段
2. 将 asset_meta 中的 benchmark_index 数据迁移到 positions 表
3. 删除 asset_meta 表的 benchmark_index 字段
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine, SessionLocal
from sqlalchemy import text, Column, String
from sqlalchemy.orm import sessionmaker


def migrate():
    db = SessionLocal()
    
    try:
        # 1. 检查 positions 表是否已有 benchmark_index 字段
        result = db.execute(text("PRAGMA table_info(positions)"))
        columns = [row[1] for row in result]
        
        if 'benchmark_index' not in columns:
            print("添加 benchmark_index 字段到 positions 表...")
            db.execute(text("ALTER TABLE positions ADD COLUMN benchmark_index VARCHAR(10)"))
            db.commit()
            print("✓ 字段添加成功")
        else:
            print("positions 表已有 benchmark_index 字段，跳过添加")
        
        # 2. 迁移数据：将 asset_meta 中的 benchmark_index 移到 positions
        print("\n迁移数据...")
        result = db.execute(text("""
            SELECT am.code, am.benchmark_index 
            FROM asset_meta am
            WHERE am.asset_type = 'etf' 
            AND am.benchmark_index IS NOT NULL
        """))
        
        mappings = [(row[0], row[1]) for row in result]
        print(f"找到 {len(mappings)} 条ETF-指数映射")
        
        migrated = 0
        for etf_code, index_code in mappings:
            # 更新 positions 表
            result = db.execute(text("""
                UPDATE positions 
                SET benchmark_index = :index_code
                WHERE code = :etf_code
            """), {"index_code": index_code, "etf_code": etf_code})
            
            if result.rowcount > 0:
                migrated += 1
                print(f"  {etf_code} -> {index_code} (已更新持仓)")
            else:
                print(f"  {etf_code} -> {index_code} (无对应持仓)")
        
        db.commit()
        print(f"\n✓ 数据迁移完成，{migrated} 条持仓记录已更新")
        
        # 3. 删除 asset_meta 表的 benchmark_index 字段
        # SQLite 不支持直接删除字段，需要重建表
        print("\n重建 asset_meta 表（删除 benchmark_index 字段）...")
        
        # 获取现有数据
        result = db.execute(text("""
            SELECT code, name, asset_type, category, source, list_date, is_cached, updated_at
            FROM asset_meta
        """))
        
        asset_data = []
        for row in result:
            asset_data.append({
                'code': row[0],
                'name': row[1],
                'asset_type': row[2],
                'category': row[3],
                'source': row[4],
                'list_date': row[5],
                'is_cached': row[6],
                'updated_at': row[7]
            })
        
        # 删除旧表
        db.execute(text("DROP TABLE asset_meta"))
        
        # 创建新表（不含 benchmark_index）
        db.execute(text("""
            CREATE TABLE asset_meta (
                code VARCHAR(10) PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                asset_type VARCHAR(20) NOT NULL,
                category VARCHAR(30),
                source VARCHAR(20),
                list_date DATE,
                is_cached INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # 恢复数据
        for asset in asset_data:
            db.execute(text("""
                INSERT INTO asset_meta (code, name, asset_type, category, source, list_date, is_cached, updated_at)
                VALUES (:code, :name, :asset_type, :category, :source, :list_date, :is_cached, :updated_at)
            """), asset)
        
        db.commit()
        print(f"✓ 表重建完成，{len(asset_data)} 条记录已恢复")
        
        print("\n=== 迁移完成 ===")
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ 迁移失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
