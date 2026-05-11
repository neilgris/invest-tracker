from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Position, DailySnapshot, Trade, BaselineConfig
from schemas import PositionOut, OverviewOut, BaselineConfigCreate, BaselineConfigOut, TradeMarker, PositionCategoryUpdate, PositionLinkedCodeUpdate
from services.stats import get_overview
from services.market import get_hist_prices
from datetime import date, timedelta
import math

router = APIRouter(prefix="/api/positions", tags=["持仓管理"])


def enrich_position(pos: Position, db: Session, today_snaps: dict = None) -> dict:
    """计算持仓的衍生字段"""
    mv = pos.quantity * pos.current_price if pos.current_price else pos.total_cost
    total_pnl = mv - pos.total_cost
    total_pnl_pct = (total_pnl / pos.total_cost * 100) if pos.total_cost > 0 else 0

    # 当日盈亏 - 从预加载的快照字典获取
    if today_snaps is not None:
        snap = today_snaps.get(pos.code)
    else:
        today = date.today()
        snap = db.query(DailySnapshot).filter(
            DailySnapshot.code == pos.code,
            DailySnapshot.date == today
        ).first()
    daily_pnl = snap.daily_pnl if snap and snap.daily_pnl else 0
    daily_pnl_pct = (daily_pnl / pos.total_cost * 100) if pos.total_cost > 0 else 0

    # 关联ETF信息
    linked_info = None
    if pos.linked_code:
        linked_pos = db.query(Position).filter(Position.code == pos.linked_code).first()
        if linked_pos:
            linked_mv = linked_pos.quantity * linked_pos.current_price if linked_pos.current_price else 0
            linked_info = {
                "code": linked_pos.code,
                "name": linked_pos.name,
                "short_name": linked_pos.short_name,
                "current_price": round(linked_pos.current_price, 4) if linked_pos.current_price else 0,
                "market_value": round(linked_mv, 2),
            }
        else:
            # 不在持仓中，从搜索API获取名称
            from services.market import _search_code
            search_result = _search_code(pos.linked_code)
            linked_info = {
                "code": pos.linked_code,
                "name": search_result.get("name", ""),
                "short_name": search_result.get("short_name", ""),
                "current_price": 0,
                "market_value": 0,
            }

    return {
        "id": pos.id,
        "code": pos.code,
        "name": pos.name,
        "short_name": pos.short_name,
        "category": pos.category,
        "linked_code": pos.linked_code,
        "linked_info": linked_info,
        "total_cost": round(pos.total_cost, 2),
        "quantity": pos.quantity,
        "avg_cost": round(pos.avg_cost, 4),
        "current_price": round(pos.current_price, 4) if pos.current_price else 0,
        "market_value": round(mv, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "daily_pnl": round(daily_pnl, 2),
        "daily_pnl_pct": round(daily_pnl_pct, 2),
        "updated_at": pos.updated_at,
    }


@router.get("", response_model=list[PositionOut])
def list_positions(db: Session = Depends(get_db)):
    positions = db.query(Position).all()
    if not positions:
        return []

    # 预加载所有今日快照，避免N+1查询
    today = date.today()
    codes = [p.code for p in positions]
    snaps = db.query(DailySnapshot).filter(
        DailySnapshot.code.in_(codes),
        DailySnapshot.date == today
    ).all()
    today_snaps = {s.code: s for s in snaps}

    return [enrich_position(p, db, today_snaps) for p in positions]


@router.get("/overview", response_model=OverviewOut)
def overview(db: Session = Depends(get_db)):
    return get_overview(db)


@router.get("/closed-positions")
def get_closed_positions(db: Session = Depends(get_db)):
    """获取已清仓标的的历史收益"""
    from sqlalchemy import distinct
    
    # 获取所有有过交易记录的代码
    traded_codes = db.query(distinct(Trade.code)).all()
    traded_codes = [c[0] for c in traded_codes]
    
    # 获取当前持仓代码
    current_codes = db.query(Position.code).all()
    current_codes = [c[0] for c in current_codes]
    
    # 已清仓 = 有过交易但不在当前持仓中
    closed_codes = set(traded_codes) - set(current_codes)
    
    result = []
    for code in closed_codes:
        trades = db.query(Trade).filter(Trade.code == code).order_by(Trade.trade_date).all()
        if not trades:
            continue
            
        name = trades[0].name
        
        # 计算总买入、总卖出、总分红
        total_buy = 0
        total_sell = 0
        total_dividend = 0
        
        for t in trades:
            if t.direction == "buy":
                total_buy += t.amount
            elif t.direction == "sell":
                total_sell += (t.amount - t.fee)
            elif t.direction == "dividend":
                total_dividend += (t.quantity or 0)
        
        # 清仓收益 = 卖出总金额 - 买入总金额 + 分红金额
        total_pnl = total_sell - total_buy + total_dividend
        pnl_pct = (total_pnl / total_buy * 100) if total_buy > 0 else 0
        
        # 获取第一笔和最后一笔交易日期
        first_trade = trades[0].trade_date
        last_trade = trades[-1].trade_date
        
        result.append({
            "code": code,
            "name": name,
            "total_buy": round(total_buy, 2),
            "total_sell": round(total_sell, 2),
            "total_dividend": round(total_dividend, 2),
            "total_pnl": round(total_pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "first_trade": first_trade.strftime("%Y-%m-%d"),
            "last_trade": last_trade.strftime("%Y-%m-%d"),
            "trade_count": len(trades),
        })
    
    # 按盈亏额降序排列
    return sorted(result, key=lambda x: x["total_pnl"], reverse=True)


@router.get("/{code}")
def get_position_detail(code: str, db: Session = Depends(get_db)):
    pos = db.query(Position).filter(Position.code == code).first()
    if not pos:
        raise HTTPException(status_code=404, detail="持仓不存在")
    return enrich_position(pos, db)


def _aggregate_weekly(snaps: list) -> list[dict]:
    """将日线数据聚合为周线：按ISO周分组"""
    from itertools import groupby

    if not snaps:
        return []
    result = []
    for key, group in groupby(snaps, key=lambda s: s.date.isocalendar()[:2]):
        items = list(group)
        result.append({
            "date": items[-1].date.strftime("%Y-%m-%d"),  # 用周五日期
            "open": items[0].open,
            "close": items[-1].close,
            "high": max(s.high or s.close for s in items),
            "low": min(s.low or s.close for s in items),
        })
    return result


def _aggregate_monthly(snaps: list) -> list[dict]:
    """将日线数据聚合为月线：按年月分组"""
    from itertools import groupby

    if not snaps:
        return []
    result = []
    for key, group in groupby(snaps, key=lambda s: (s.date.year, s.date.month)):
        items = list(group)
        result.append({
            "date": items[-1].date.strftime("%Y-%m-%d"),  # 用月末日期
            "open": items[0].open,
            "close": items[-1].close,
            "high": max(s.high or s.close for s in items),
            "low": min(s.low or s.close for s in items),
        })
    return result


@router.get("/{code}/chart")
def get_position_chart(code: str, period: str = Query("daily", regex="^(daily|weekly|monthly)$"), db: Session = Depends(get_db)):
    """获取持仓走势图数据 + 买卖标记，从本地 daily_snapshots 读取"""
    pos = db.query(Position).filter(Position.code == code).first()
    if not pos:
        raise HTTPException(status_code=404, detail="持仓不存在")

    # 从本地 DB 读取所有快照
    snaps = db.query(DailySnapshot).filter(
        DailySnapshot.code == code
    ).order_by(DailySnapshot.date).all()

    if not snaps:
        # 本地无数据，尝试从 API 拉取一次
        first_trade = db.query(Trade).filter(Trade.code == code).order_by(Trade.trade_date).first()
        if not first_trade:
            return {"prices": [], "markers": []}
        start_date = (first_trade.trade_date - timedelta(days=30)).strftime("%Y%m%d")
        end_date = (date.today() + timedelta(days=1)).strftime("%Y%m%d")
        raw = get_hist_prices(code, start_date, end_date)
        prices = [{"date": p["date"], "open": p.get("open"), "close": p["close"], "high": p.get("high"), "low": p.get("low")} for p in raw]
    else:
        # 按 period 聚合
        if period == "weekly":
            prices = _aggregate_weekly(snaps)
        elif period == "monthly":
            prices = _aggregate_monthly(snaps)
        else:
            prices = [{
                "date": s.date.strftime("%Y-%m-%d"),
                "open": s.open,
                "close": s.close,
                "high": s.high,
                "low": s.low,
            } for s in snaps]

    # 买卖标记
    trades = db.query(Trade).filter(Trade.code == code).all()
    markers = []
    for t in trades:
        markers.append({
            "date": t.trade_date.strftime("%Y-%m-%d"),
            "price": t.price,
            "direction": t.direction,
            "amount": t.amount,
        })

    return {"prices": prices, "markers": markers}


@router.get("/{code}/baseline")
def get_baseline_comparison(code: str, baseline_code: str = Query("000300"), period: str = Query("daily", regex="^(daily|weekly|monthly)$"), db: Session = Depends(get_db)):
    """ETF与基线对比，从本地 DB 读取"""
    pos = db.query(Position).filter(Position.code == code).first()
    if not pos:
        return {"etf": [], "baseline": []}

    # ETF 数据从本地 snapshots
    etf_snaps = db.query(DailySnapshot).filter(
        DailySnapshot.code == code
    ).order_by(DailySnapshot.date).all()

    # 基线数据：先查本地，没有再从 API 拉
    base_snaps = db.query(DailySnapshot).filter(
        DailySnapshot.code == baseline_code
    ).order_by(DailySnapshot.date).all()

    if not base_snaps:
        # 基线不在本地，从 API 拉取
        first_trade = db.query(Trade).filter(Trade.code == code).order_by(Trade.trade_date).first()
        if first_trade:
            start_date = (first_trade.trade_date - timedelta(days=30)).strftime("%Y%m%d")
            end_date = (date.today() + timedelta(days=1)).strftime("%Y%m%d")
            raw = get_hist_prices(baseline_code, start_date, end_date)
            baseline_data = raw
        else:
            baseline_data = []
    else:
        # 按 period 聚合基线
        if period == "weekly":
            baseline_data = _aggregate_weekly(base_snaps)
        elif period == "monthly":
            baseline_data = _aggregate_monthly(base_snaps)
        else:
            baseline_data = [{"date": s.date.strftime("%Y-%m-%d"), "close": s.close} for s in base_snaps]

    # 聚合 ETF 数据
    if not etf_snaps:
        etf_data = []
    elif period == "weekly":
        etf_data = _aggregate_weekly(etf_snaps)
    elif period == "monthly":
        etf_data = _aggregate_monthly(etf_snaps)
    else:
        etf_data = [{"date": s.date.strftime("%Y-%m-%d"), "close": s.close} for s in etf_snaps]

    # 归一化：以第一天为基准100
    def normalize(data):
        if not data:
            return []
        base = data[0]["close"]
        if not base:
            return []
        return [{"date": d["date"], "value": round(d["close"] / base * 100, 2)} for d in data]

    return {
        "etf": normalize(etf_data),
        "baseline": normalize(baseline_data),
    }


# --- 基线配置 ---
@router.post("/baseline-config", response_model=BaselineConfigOut)
def add_baseline_config(cfg: BaselineConfigCreate, db: Session = Depends(get_db)):
    existing = db.query(BaselineConfig).filter(BaselineConfig.etf_code == cfg.etf_code).first()
    if existing:
        existing.baseline_code = cfg.baseline_code
        existing.baseline_name = cfg.baseline_name
        db.commit()
        db.refresh(existing)
        return existing
    obj = BaselineConfig(**cfg.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/baseline-config/{etf_code}", response_model=list[BaselineConfigOut])
def get_baseline_config(etf_code: str, db: Session = Depends(get_db)):
    return db.query(BaselineConfig).filter(BaselineConfig.etf_code == etf_code).all()


# --- 持仓分类 ---
@router.patch("/{code}/category", response_model=PositionOut)
def update_position_category(code: str, update: PositionCategoryUpdate, db: Session = Depends(get_db)):
    """更新持仓分类标签"""
    pos = db.query(Position).filter(Position.code == code).first()
    if not pos:
        raise HTTPException(status_code=404, detail="持仓不存在")
    
    # 验证分类值是否合法
    valid_categories = ["主线成长", "主动混合", "现金防御", "对冲压舱", "固收缓冲", "宽基", "主题"]
    if update.category and update.category not in valid_categories:
        raise HTTPException(status_code=400, detail=f"无效的分类，可选值: {', '.join(valid_categories)}")
    
    pos.category = update.category
    db.commit()
    db.refresh(pos)
    return enrich_position(pos, db)


@router.patch("/{code}/linked-code", response_model=PositionOut)
def update_position_linked_code(code: str, update: PositionLinkedCodeUpdate, db: Session = Depends(get_db)):
    """更新持仓关联场内ETF代码"""
    pos = db.query(Position).filter(Position.code == code).first()
    if not pos:
        raise HTTPException(status_code=404, detail="持仓不存在")
    
    # 验证关联代码是否存在
    if update.linked_code:
        from services.market import _search_code
        result = _search_code(update.linked_code)
        if not result.get("name"):
            raise HTTPException(status_code=400, detail=f"找不到代码 {update.linked_code} 对应的标的")
    
    pos.linked_code = update.linked_code
    db.commit()
    db.refresh(pos)
    return enrich_position(pos, db)


@router.get("/{code}/suggest-linked")
def suggest_linked_etf(code: str, db: Session = Depends(get_db)):
    """为场外基金推荐关联的场内ETF"""
    pos = db.query(Position).filter(Position.code == code).first()
    if not pos:
        raise HTTPException(status_code=404, detail="持仓不存在")
    
    try:
        import akshare as ak
        df = ak.fund_etf_category_sina(symbol="ETF基金")
        df['code'] = df['代码'].str[2:]
        df['name'] = df['名称']
    except Exception as e:
        return {"suggestions": [], "error": str(e)}
    
    fund_companies = [
        "华安", "嘉实", "华夏", "易方达", "南方", "广发", "天弘", "工银瑞信",
        "银华", "鹏华", "博时", "国泰", "富国", "汇添富", "招商", "景顺长城",
        "大成", "中银", "长盛", "诺安", "融通", "万家", "浦银安盛",
        "建信", "交银施罗德", "兴证全球", "中欧", "泓德", "睿远", "东方",
        "兴业", "长城", "平安", "海富通", "上投摩根", "泰康", "华宝", "华泰柏瑞",
        "前海开源", "西部利得", "东财", "摩根",
    ]
    
    otc_name = pos.name
    company = None
    for fc in sorted(fund_companies, key=len, reverse=True):
        if otc_name.startswith(fc):
            company = fc
            break
    
    if not company:
        return {"suggestions": []}
    
    # 提取指数关键词
    name_body = otc_name[len(company):]
    for suffix in ['发起式联接A', '发起式联接C', '发起联接A', '发起联接C',
                   '联接基金A', '联接基金C', '联接A', '联接C', '联接E']:
        if name_body.endswith(suffix):
            name_body = name_body[:-len(suffix)]
            break
    if name_body.endswith('ETF'):
        name_body = name_body[:-3]
    
    # 在同基金公司的ETF中匹配
    company_etfs = df[df['name'].str.endswith(company, na=False)]
    
    results = []
    for _, row in company_etfs.iterrows():
        etf_name_body = row['name'][:-len(company)]
        if etf_name_body.endswith('ETF'):
            etf_name_body = etf_name_body[:-3]
        
        otc_tokens = set()
        for i in range(len(name_body) - 1):
            otc_tokens.add(name_body[i:i+2])
        
        etf_tokens = set()
        for i in range(len(etf_name_body) - 1):
            etf_tokens.add(etf_name_body[i:i+2])
        
        overlap = otc_tokens & etf_tokens
        score = len(overlap) / max(len(otc_tokens), 1)
        
        if score >= 0.25:
            results.append({
                "code": row['code'],
                "name": row['name'],
                "score": round(score, 2),
            })
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return {"suggestions": results[:5]}


@router.get("/categories/stats")
def get_category_stats(db: Session = Depends(get_db)):
    """按分类统计持仓"""
    positions = db.query(Position).all()
    
    stats = {}
    for pos in positions:
        cat = pos.category or "未分类"
        mv = pos.quantity * pos.current_price if pos.current_price else pos.total_cost
        
        if cat not in stats:
            stats[cat] = {"count": 0, "market_value": 0, "total_cost": 0}
        stats[cat]["count"] += 1
        stats[cat]["market_value"] += mv
        stats[cat]["total_cost"] += pos.total_cost
    
    # 计算每个分类的盈亏
    result = []
    for cat, data in stats.items():
        pnl = data["market_value"] - data["total_cost"]
        pnl_pct = (pnl / data["total_cost"] * 100) if data["total_cost"] > 0 else 0
        result.append({
            "category": cat,
            "count": data["count"],
            "market_value": round(data["market_value"], 2),
            "total_cost": round(data["total_cost"], 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })
    
    return sorted(result, key=lambda x: x["pnl_pct"], reverse=True)
