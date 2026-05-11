from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from services.market import fetch_and_save_daily, fetch_and_save_history, detect_and_record_dividends

router = APIRouter(prefix="/api/quotes", tags=["行情同步"])


@router.get("/validate/{code}")
def validate_code(code: str):
    """校验股票/ETF代码，返回名称和短名（不拉价格，秒级响应）"""
    from services.market import _search_code, get_stock_name
    result = _search_code(code)
    if result:
        return {"valid": True, "code": code, "name": result["name"], "short_name": result.get("short_name", result["name"])}
    # fallback
    name = get_stock_name(code)
    valid = bool(name)
    return {"valid": valid, "code": code, "name": name, "short_name": name}


@router.get("/fund-info/{code}")
def get_fund_info(code: str, date: str = None):
    """获取联接基金信息（名称、短名、指定日期净值）
    date: YYYY-MM-DD 格式，不传则返回最新净值
    """
    from services.market import _search_code, _is_fund_code, get_fund_nav_on_date, _get_fund_nav
    
    # 校验是否为联接基金/开放式基金
    if not _is_fund_code(code):
        return {"valid": False, "message": "该代码不是联接基金或开放式基金"}
    
    # 获取名称
    result = _search_code(code)
    if not result:
        return {"valid": False, "message": "未找到该基金"}
    
    # 获取净值
    if date:
        nav = get_fund_nav_on_date(code, date)
    else:
        nav = _get_fund_nav(code)
    
    if nav is None:
        return {"valid": False, "message": f"未找到{'该日期' if date else '最新'}净值"}
    
    return {
        "valid": True,
        "code": code,
        "name": result["name"],
        "short_name": result.get("short_name", result["name"]),
        "is_fund": True,
        "date": date,
        "nav": nav
    }


@router.post("/sync")
def sync_quotes(db: Session = Depends(get_db)):
    """手动触发行情同步：当日行情 + 历史数据补齐"""
    try:
        fetch_and_save_daily()
        fetch_and_save_history()
        return {"ok": True, "message": "行情同步完成（含历史数据）"}
    except Exception as e:
        return {"ok": False, "message": f"同步失败: {str(e)}"}


@router.get("/dividends")
def get_dividends(code: str = None):
    """检测持仓分红记录（首笔买入后的分红，已记录的不会重复返回）
    返回待确认的分红列表，前端确认后调用 POST /dividends/confirm 记录
    """
    try:
        results = detect_and_record_dividends(code)
        return {"ok": True, "dividends": results}
    except Exception as e:
        return {"ok": False, "message": f"检测分红失败: {str(e)}"}


@router.post("/dividends/confirm")
def confirm_dividends(dividends: list[dict]):
    """确认分红再投资，将分红记录写入交易表
    请求体: [{code, name, short_name, date, dividend_per_unit, quantity, dividend_amount, price, reinvest_qty}, ...]
    """
    from database import SessionLocal
    from models import Trade
    from services.tracker import recalc_position
    from services.market import recalc_snapshots_pnl
    from datetime import datetime as dt, date as date_type

    db = SessionLocal()
    try:
        created = []
        for div in dividends:
            # 日期格式适配：字符串转 date 对象
            raw_date = div["date"]
            if isinstance(raw_date, str):
                trade_date = dt.strptime(raw_date, "%Y-%m-%d").date()
            elif isinstance(raw_date, date_type):
                trade_date = raw_date
            else:
                trade_date = date_type.today()

            trade = Trade(
                code=div["code"],
                name=div["name"],
                short_name=div.get("short_name", div["name"]),
                direction="dividend",
                price=div["price"],
                amount=div["dividend_amount"],
                quantity=div["reinvest_qty"],
                trade_date=trade_date,
                fee=0.0,
            )
            db.add(trade)
            created.append(div)

        db.commit()

        # 重算受影响的持仓和快照
        codes = list(set(d["code"] for d in dividends))
        for c in codes:
            recalc_position(db, c)
            recalc_snapshots_pnl(c)

        db.commit()

        return {"ok": True, "created": len(created)}
    except Exception as e:
        db.rollback()
        return {"ok": False, "message": f"确认分红失败: {str(e)}"}
    finally:
        db.close()
