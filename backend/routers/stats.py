from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from services.stats import get_monthly_stats, get_yearly_stats, get_monthly_position_details, get_yearly_position_details

router = APIRouter(prefix="/api/stats", tags=["收益统计"])


@router.get("/monthly")
def monthly_stats(year: int = Query(default=None), db: Session = Depends(get_db)):
    return get_monthly_stats(db, year)


@router.get("/yearly")
def yearly_stats(db: Session = Depends(get_db)):
    return get_yearly_stats(db)


@router.get("/monthly/{year}/{month}/positions")
def monthly_position_details(year: int, month: int, db: Session = Depends(get_db)):
    """获取某月各持仓的收益明细"""
    return get_monthly_position_details(db, year, month)


@router.get("/yearly/{year}/positions")
def yearly_position_details(year: int, db: Session = Depends(get_db)):
    """获取某年度各持仓的收益明细"""
    return get_yearly_position_details(db, year)
