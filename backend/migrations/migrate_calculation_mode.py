#!/usr/bin/env python3
"""
数据库迁移脚本：将 stop_loss_config 表的 use_profit_based 字段改为 calculation_mode

迁移策略：
- use_profit_based=0 且 profit_level_key='thin_profit' -> calculation_mode='cost_protection'
- use_profit_based=0 且 profit_level_key!='thin_profit' -> calculation_mode='pmax_drawdown'
- use_profit_based=1 -> calculation_mode='profit_retention'
"""

import sqlite3
import os

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'invest_tracker.db')

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查是否存在 use_profit_based 字段
    cursor.execute("PRAGMA table_info(stop_loss_config)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'calculation_mode' in columns:
        print("calculation_mode 字段已存在，跳过迁移")
        conn.close()
        return
    
    if 'use_profit_based' not in columns:
        print("use_profit_based 字段不存在，直接添加 calculation_mode 字段")
        cursor.execute("ALTER TABLE stop_loss_config ADD COLUMN calculation_mode VARCHAR(20) DEFAULT 'pmax_drawdown'")
        conn.commit()
        conn.close()
        return
    
    print("开始迁移...")
    
    # 1. 创建新表
    cursor.execute('''
        CREATE TABLE stop_loss_config_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profit_level_key VARCHAR(20) NOT NULL UNIQUE,
            half_position_ratio FLOAT,
            clear_position_ratio FLOAT,
            calculation_mode VARCHAR(20) DEFAULT 'pmax_drawdown',
            profit_retention_half FLOAT,
            profit_retention_clear FLOAT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. 查询现有数据
    cursor.execute('''
        SELECT id, profit_level_key, half_position_ratio, clear_position_ratio, 
               use_profit_based, profit_retention_half, profit_retention_clear, updated_at
        FROM stop_loss_config
    ''')
    rows = cursor.fetchall()
    
    # 3. 迁移数据，转换计算方式
    for row in rows:
        id_, profit_level_key, half_position_ratio, clear_position_ratio, \
        use_profit_based, profit_retention_half, profit_retention_clear, updated_at = row
        
        # 确定 calculation_mode
        if use_profit_based == 1:
            calculation_mode = 'profit_retention'
        elif profit_level_key == 'thin_profit':
            calculation_mode = 'cost_protection'
        else:
            calculation_mode = 'pmax_drawdown'
        
        cursor.execute('''
            INSERT INTO stop_loss_config_new 
            (id, profit_level_key, half_position_ratio, clear_position_ratio, 
             calculation_mode, profit_retention_half, profit_retention_clear, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (id_, profit_level_key, half_position_ratio, clear_position_ratio,
              calculation_mode, profit_retention_half, profit_retention_clear, updated_at))
        
        print(f"  迁移: {profit_level_key} -> {calculation_mode}")
    
    # 4. 删除旧表，重命名新表
    cursor.execute("DROP TABLE stop_loss_config")
    cursor.execute("ALTER TABLE stop_loss_config_new RENAME TO stop_loss_config")
    
    # 5. 创建索引
    cursor.execute("CREATE INDEX idx_stop_loss_config_profit_level_key ON stop_loss_config(profit_level_key)")
    
    conn.commit()
    conn.close()
    print("迁移完成！")

if __name__ == '__main__':
    migrate()
