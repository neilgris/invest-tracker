from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models import Trade
from schemas import TradeCreate, TradeUpdate, TradeOut
from services.tracker import create_trade, update_trade, delete_trade

router = APIRouter(prefix="/api/trades", tags=["交易管理"])


@router.post("", response_model=TradeOut)
def add_trade(trade: TradeCreate, db: Session = Depends(get_db)):
    return create_trade(db, trade)


@router.get("", response_model=list[TradeOut])
def list_trades(
    code: Optional[str] = None,
    direction: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(Trade)
    if code:
        q = q.filter(Trade.code == code)
    if direction:
        q = q.filter(Trade.direction == direction)
    if start_date:
        q = q.filter(Trade.trade_date >= start_date)
    if end_date:
        q = q.filter(Trade.trade_date <= end_date)
    return q.order_by(Trade.trade_date.desc()).offset(skip).limit(limit).all()


@router.put("/{trade_id}", response_model=TradeOut)
def edit_trade(trade_id: int, trade: TradeUpdate, db: Session = Depends(get_db)):
    result = update_trade(db, trade_id, trade)
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="交易记录不存在")
    return result


@router.delete("/{trade_id}")
def remove_trade(trade_id: int, db: Session = Depends(get_db)):
    ok = delete_trade(db, trade_id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="交易记录不存在")
    return {"ok": True}
