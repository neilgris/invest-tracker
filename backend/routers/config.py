from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import StopLossConfig, ProfitLevelConfig
from schemas import (
    StopLossConfigOut, StopLossConfigUpdate, StopLossConfigReset,
    ProfitLevelConfigOut, ProfitLevelConfigUpdate
)
from datetime import datetime

router = APIRouter(prefix="/api/config", tags=["config"])

# 默认止盈/损线配置 - 与利润等级关联 (通过 profit_level_key)
# F档(利润): F1.3/F1.2/F1.1/F2/F3
# L档(亏损): L1/L2/L3/L4 (L3/L4不设止盈线)
DEFAULT_STOP_LOSS_CONFIGS = [
    # F1.3 极厚利润 - Pmax回撤
    {
        "profit_level_key": "thick_profit_3",
        "half_position_ratio": 0.78,
        "clear_position_ratio": 0.65,
        "calculation_mode": "pmax_drawdown",
        "profit_retention_half": None,
        "profit_retention_clear": None
    },
    # F1.2 中厚利润 - Pmax回撤
    {
        "profit_level_key": "thick_profit_2",
        "half_position_ratio": 0.82,
        "clear_position_ratio": 0.70,
        "calculation_mode": "pmax_drawdown",
        "profit_retention_half": None,
        "profit_retention_clear": None
    },
    # F1.1 浅厚利润 - Profit_max保留
    {
        "profit_level_key": "thick_profit_1",
        "half_position_ratio": None,
        "clear_position_ratio": None,
        "calculation_mode": "profit_retention",
        "profit_retention_half": 0.50,
        "profit_retention_clear": 0.30
    },
    # F2 中利润 - Profit_max保留
    {
        "profit_level_key": "medium_profit",
        "half_position_ratio": None,
        "clear_position_ratio": None,
        "calculation_mode": "profit_retention",
        "profit_retention_half": 0.70,
        "profit_retention_clear": 0.50
    },
    # F3 薄利润 / L2 薄亏损观察 - 成本保护
    {
        "profit_level_key": "thin_profit",
        "half_position_ratio": 0.97,
        "clear_position_ratio": 0.92,
        "calculation_mode": "cost_protection",
        "profit_retention_half": None,
        "profit_retention_clear": None
    },
    # L1 新建仓宽容 - 独立成本保护配置（更宽松的止损线）
    {
        "profit_level_key": "thin_loss_new",
        "half_position_ratio": 0.85,
        "clear_position_ratio": 0.75,
        "calculation_mode": "cost_protection",
        "profit_retention_half": None,
        "profit_retention_clear": None
    },
    # L3 中亏损决策 - 成本保护（跌破20%减半仓，跌破30%清仓）
    {
        "profit_level_key": "medium_loss",
        "half_position_ratio": 0.80,
        "clear_position_ratio": 0.70,
        "calculation_mode": "cost_protection",
        "profit_retention_half": None,
        "profit_retention_clear": None
    },
]

# 默认利润等级配置
# 规则：按 sort_order 顺序匹配，value >= pnl_threshold_min 且 value < pnl_threshold_max (max为null表示无上限)
# 持仓天数规则：hold_days_min <= hold_days < hold_days_max (None表示无限制)
DEFAULT_PROFIT_LEVEL_CONFIGS = [
    # 利润档位 (使用 PnL_peak 判断)
    {"level_name": "极厚利润", "level_key": "thick_profit_3", "level_code": "F1.3", "pnl_threshold": 200.0, "pnl_threshold_max": None, "use_peak_pnl": 1, "sort_order": 1, "display_color": "success", "hold_days_min": None, "hold_days_max": None},
    {"level_name": "中厚利润", "level_key": "thick_profit_2", "level_code": "F1.2", "pnl_threshold": 100.0, "pnl_threshold_max": 200.0, "use_peak_pnl": 1, "sort_order": 2, "display_color": "success", "hold_days_min": None, "hold_days_max": None},
    {"level_name": "浅厚利润", "level_key": "thick_profit_1", "level_code": "F1.1", "pnl_threshold": 50.0, "pnl_threshold_max": 100.0, "use_peak_pnl": 1, "sort_order": 3, "display_color": "success", "hold_days_min": None, "hold_days_max": None},
    {"level_name": "中利润", "level_key": "medium_profit", "level_code": "F2", "pnl_threshold": 25.0, "pnl_threshold_max": 50.0, "use_peak_pnl": 1, "sort_order": 4, "display_color": "success", "hold_days_min": None, "hold_days_max": None},
    {"level_name": "薄利润", "level_key": "thin_profit", "level_code": "F3", "pnl_threshold": 0.0, "pnl_threshold_max": 25.0, "use_peak_pnl": 0, "sort_order": 5, "display_color": "warning", "hold_days_min": None, "hold_days_max": None},
    # 亏损档位 (使用 PnL_now 判断，L1/L2/L3/L4 需额外判断 hold_days)
    # L1: hold_days < 60 (新建仓宽容)
    {"level_name": "新建仓宽容", "level_key": "thin_loss_new", "level_code": "L1", "pnl_threshold": -10.0, "pnl_threshold_max": 0.0, "use_peak_pnl": 0, "sort_order": 6, "display_color": "warning", "hold_days_min": None, "hold_days_max": 60},
    # L2/L3/L4: hold_days >= 60
    {"level_name": "薄亏损观察", "level_key": "thin_loss_watch", "level_code": "L2", "pnl_threshold": -10.0, "pnl_threshold_max": 0.0, "use_peak_pnl": 0, "sort_order": 7, "display_color": "warning", "hold_days_min": 60, "hold_days_max": None},
    {"level_name": "中亏损决策", "level_key": "medium_loss", "level_code": "L3", "pnl_threshold": -30.0, "pnl_threshold_max": -10.0, "use_peak_pnl": 0, "sort_order": 8, "display_color": "danger", "hold_days_min": 60, "hold_days_max": None},
    {"level_name": "厚亏损清仓", "level_key": "thick_loss", "level_code": "L4", "pnl_threshold": -100.0, "pnl_threshold_max": -30.0, "use_peak_pnl": 0, "sort_order": 9, "display_color": "danger", "hold_days_min": 60, "hold_days_max": None},
]


def init_stop_loss_configs(db: Session):
    """初始化默认止盈线配置"""
    existing = db.query(StopLossConfig).first()
    if not existing:
        for config in DEFAULT_STOP_LOSS_CONFIGS:
            db.add(StopLossConfig(**config))
        db.commit()


def init_profit_level_configs(db: Session):
    """初始化默认利润等级配置"""
    existing = db.query(ProfitLevelConfig).first()
    if not existing:
        for config in DEFAULT_PROFIT_LEVEL_CONFIGS:
            db.add(ProfitLevelConfig(**config))
        db.commit()


# ==================== 止盈线配置 API ====================

@router.get("/stop-loss", response_model=List[StopLossConfigOut])
def get_stop_loss_configs(db: Session = Depends(get_db)):
    """获取所有止盈线配置（关联利润等级信息）"""
    init_stop_loss_configs(db)
    init_profit_level_configs(db)
    
    # 查询所有止盈线配置
    stop_loss_configs = db.query(StopLossConfig).all()
    
    # 查询所有利润等级配置，建立映射
    profit_levels = db.query(ProfitLevelConfig).all()
    level_map = {pl.level_key: pl for pl in profit_levels}
    
    # 组装结果，关联利润等级信息
    result = []
    for config in stop_loss_configs:
        level = level_map.get(config.profit_level_key)
        result.append({
            "id": config.id,
            "profit_level_key": config.profit_level_key,
            "level_name": level.level_name if level else None,
            "level_code": level.level_code if level else None,
            "pnl_min": level.pnl_threshold if level else None,
            "pnl_max": level.pnl_threshold_max if level else None,
            "half_position_ratio": config.half_position_ratio,
            "clear_position_ratio": config.clear_position_ratio,
            "calculation_mode": config.calculation_mode,
            "profit_retention_half": config.profit_retention_half,
            "profit_retention_clear": config.profit_retention_clear,
            "updated_at": config.updated_at
        })
    
    # 按利润等级排序
    result.sort(key=lambda x: x.get("pnl_min") or 0, reverse=True)
    return result


@router.put("/stop-loss/{config_id}", response_model=StopLossConfigOut)
def update_stop_loss_config(
    config_id: int,
    config_update: StopLossConfigUpdate,
    db: Session = Depends(get_db)
):
    """更新止盈线配置"""
    config = db.query(StopLossConfig).filter(StopLossConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    config.half_position_ratio = config_update.half_position_ratio
    config.clear_position_ratio = config_update.clear_position_ratio
    config.calculation_mode = config_update.calculation_mode
    config.profit_retention_half = config_update.profit_retention_half
    config.profit_retention_clear = config_update.profit_retention_clear
    config.updated_at = datetime.now()
    
    db.commit()
    db.refresh(config)
    
    # 获取关联的利润等级信息
    level = db.query(ProfitLevelConfig).filter(
        ProfitLevelConfig.level_key == config.profit_level_key
    ).first()
    
    return {
        "id": config.id,
        "profit_level_key": config.profit_level_key,
        "level_name": level.level_name if level else None,
        "level_code": level.level_code if level else None,
        "pnl_min": level.pnl_threshold if level else None,
        "pnl_max": level.pnl_threshold_max if level else None,
        "half_position_ratio": config.half_position_ratio,
        "clear_position_ratio": config.clear_position_ratio,
        "calculation_mode": config.calculation_mode,
        "profit_retention_half": config.profit_retention_half,
        "profit_retention_clear": config.profit_retention_clear,
        "updated_at": config.updated_at
    }


@router.post("/stop-loss/reset")
def reset_stop_loss_configs(reset: StopLossConfigReset, db: Session = Depends(get_db)):
    """重置为默认配置"""
    if not reset.confirm:
        raise HTTPException(status_code=400, detail="请确认重置操作")
    
    db.query(StopLossConfig).delete()
    db.commit()
    
    for config in DEFAULT_STOP_LOSS_CONFIGS:
        db.add(StopLossConfig(**config))
    db.commit()
    
    return {"message": "配置已重置为默认值"}


@router.get("/stop-loss/calculate")
def calculate_stop_loss_prices(
    pnl_peak: float,
    pnl_now: float,
    hold_days: int,
    avg_cost: float,
    pmax: float,
    db: Session = Depends(get_db)
):
    """
    根据当前利润情况计算止盈线价格
    
    流程: 先判断利润等级 -> 再查询对应止盈策略 -> 计算止盈线价格
    
    参数:
    - pnl_peak: 历史峰值浮盈率(%)
    - pnl_now: 当前浮盈率(%)
    - hold_days: 持仓天数
    - avg_cost: 平均成本价
    - pmax: 持仓后最高净值
    """
    init_stop_loss_configs(db)
    init_profit_level_configs(db)
    
    if avg_cost <= 0 or pmax <= 0:
        return {
            "has_stop_loss": False,
            "profit_level": None,
            "half_position_price": 0,
            "clear_position_price": 0
        }
    
    # 第一步：判断利润等级
    profit_level = _evaluate_profit_level(db, pnl_peak, pnl_now, hold_days)
    if not profit_level:
        return {
            "has_stop_loss": False,
            "profit_level": None,
            "half_position_price": 0,
            "clear_position_price": 0
        }
    
    level_key = profit_level["level_key"]
    
    # L3/L4 不设止盈线
    if level_key in ["medium_loss", "thick_loss"]:
        return {
            "has_stop_loss": False,
            "profit_level": profit_level,
            "half_position_price": 0,
            "clear_position_price": 0,
            "reason": "亏损档位不设止盈线"
        }
    
    # 第二步：查询对应止盈策略
    # L1/L2 共用 thin_profit 的配置
    lookup_key = "thin_profit" if level_key in ["thin_loss_new", "thin_loss_watch"] else level_key
    
    stop_loss_config = db.query(StopLossConfig).filter(
        StopLossConfig.profit_level_key == lookup_key
    ).first()
    
    if not stop_loss_config:
        return {
            "has_stop_loss": False,
            "profit_level": profit_level,
            "half_position_price": 0,
            "clear_position_price": 0
        }
    
    # 第三步：计算止盈线价格
    profit_max = pmax - avg_cost
    
    if stop_loss_config.calculation_mode == "profit_retention":
        # 基于 Profit_max 保留比例 (F1.1, F2)
        half_position_price = avg_cost + profit_max * (stop_loss_config.profit_retention_half or 0.5)
        clear_position_price = avg_cost + profit_max * (stop_loss_config.profit_retention_clear or 0.3)
    elif stop_loss_config.calculation_mode == "cost_protection":
        # F3/L1/L2 薄利润/亏损观察：成本保护，基于 avg_cost
        half_position_price = avg_cost * (stop_loss_config.half_position_ratio or 0.97)
        clear_position_price = avg_cost * (stop_loss_config.clear_position_ratio or 0.92)
    else:  # pmax_drawdown
        # F1.3/F1.2 厚利润：基于 Pmax 回撤
        half_position_price = pmax * (stop_loss_config.half_position_ratio or 1.0)
        clear_position_price = pmax * (stop_loss_config.clear_position_ratio or 1.0)
    
    return {
        "has_stop_loss": True,
        "profit_level": profit_level,
        "half_position_price": round(half_position_price, 3),
        "clear_position_price": round(clear_position_price, 3),
        "stop_loss_config": {
            "calculation_mode": stop_loss_config.calculation_mode,
            "profit_retention_half": stop_loss_config.profit_retention_half,
            "profit_retention_clear": stop_loss_config.profit_retention_clear,
            "half_position_ratio": stop_loss_config.half_position_ratio,
            "clear_position_ratio": stop_loss_config.clear_position_ratio
        }
    }


def _evaluate_profit_level(db: Session, pnl_peak: float, pnl_now: float, hold_days: int):
    """
    评估利润等级（内部函数）
    
    规则:
    - F档(利润): 使用 PnL_peak 判断
    - L档(亏损): 使用 PnL_now 判断，L1/L2 需额外判断 hold_days
    """
    configs = db.query(ProfitLevelConfig).order_by(ProfitLevelConfig.sort_order).all()
    
    for config in configs:
        # 检查是否在阈值范围内
        threshold_min = config.pnl_threshold
        threshold_max = config.pnl_threshold_max
        
        if config.use_peak_pnl:
            # F档: 使用 PnL_peak
            value = pnl_peak
        else:
            # L档: 使用 PnL_now
            value = pnl_now
        
        # 范围匹配: min <= value < max (max为None表示无上限)
        in_range = (value >= threshold_min) and (threshold_max is None or value < threshold_max)
        
        if in_range:
            # 持仓天数判断: hold_days_min <= hold_days < hold_days_max
            # None 表示无限制
            if config.hold_days_min is not None and hold_days < config.hold_days_min:
                continue  # 不满足最小天数要求
            if config.hold_days_max is not None and hold_days >= config.hold_days_max:
                continue  # 超过最大天数限制
            
            return {
                "level_key": config.level_key,
                "level_name": config.level_name,
                "level_code": config.level_code,
                "display_color": config.display_color
            }
    
    return None


# ==================== 利润等级配置 API ====================

@router.get("/profit-levels", response_model=List[ProfitLevelConfigOut])
def get_profit_level_configs(db: Session = Depends(get_db)):
    """获取所有利润等级配置"""
    init_profit_level_configs(db)
    configs = db.query(ProfitLevelConfig).order_by(ProfitLevelConfig.sort_order).all()
    return configs


@router.put("/profit-levels/{config_id}", response_model=ProfitLevelConfigOut)
def update_profit_level_config(
    config_id: int,
    config_update: ProfitLevelConfigUpdate,
    db: Session = Depends(get_db)
):
    """更新利润等级配置"""
    config = db.query(ProfitLevelConfig).filter(ProfitLevelConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    config.level_name = config_update.level_name
    config.level_code = config_update.level_code
    config.pnl_threshold = config_update.pnl_threshold
    config.pnl_threshold_max = config_update.pnl_threshold_max
    config.use_peak_pnl = config_update.use_peak_pnl
    config.display_color = config_update.display_color
    config.hold_days_min = config_update.hold_days_min
    config.hold_days_max = config_update.hold_days_max
    config.updated_at = datetime.now()
    
    db.commit()
    db.refresh(config)
    return config


@router.post("/profit-levels/reset")
def reset_profit_level_configs(db: Session = Depends(get_db)):
    """重置利润等级为默认配置"""
    db.query(ProfitLevelConfig).delete()
    db.commit()
    
    for config in DEFAULT_PROFIT_LEVEL_CONFIGS:
        db.add(ProfitLevelConfig(**config))
    db.commit()
    
    return {"message": "利润等级配置已重置为默认值"}


@router.get("/profit-levels/evaluate")
def evaluate_profit_level(
    pnl_peak: float,
    pnl_now: float,
    db: Session = Depends(get_db)
):
    """
    根据pnl_peak和pnl_now评估当前利润等级
    
    参数:
    - pnl_peak: 历史峰值浮盈率(%)
    - pnl_now: 当前浮盈率(%)
    
    返回:
    - 匹配的利润等级配置
    """
    init_profit_level_configs(db)
    
    configs = db.query(ProfitLevelConfig).order_by(ProfitLevelConfig.sort_order).all()
    
    for config in configs:
        threshold = config.pnl_threshold
        if config.use_peak_pnl:
            if pnl_peak >= threshold:
                return {
                    "level_key": config.level_key,
                    "level_name": config.level_name,
                    "display_color": config.display_color,
                    "pnl_threshold": threshold,
                    "matched_value": pnl_peak
                }
        else:
            if pnl_now >= threshold:
                return {
                    "level_key": config.level_key,
                    "level_name": config.level_name,
                    "display_color": config.display_color,
                    "pnl_threshold": threshold,
                    "matched_value": pnl_now
                }
    
    # 默认返回最后一个（厚亏损）
    last_config = configs[-1] if configs else None
    if last_config:
        return {
            "level_key": last_config.level_key,
            "level_name": last_config.level_name,
            "display_color": last_config.display_color,
            "pnl_threshold": last_config.pnl_threshold,
            "matched_value": pnl_now if not last_config.use_peak_pnl else pnl_peak
        }
    
    return {"level_key": "unknown", "level_name": "未知", "display_color": "info", "pnl_threshold": 0, "matched_value": 0}
