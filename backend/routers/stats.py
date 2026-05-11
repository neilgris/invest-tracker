from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from services.stats import get_monthly_stats, get_yearly_stats

router = APIRouter(prefix="/api/stats", tags=["收益统计"])


@router.get("/monthly")
def monthly_stats(year: int = Query(default=None), db: Session = Depends(get_db)):
    return get_monthly_stats(db, year)


@router.get("/yearly")
def yearly_stats(db: Session = Depends(get_db)):
    return get_yearly_stats(db)
