"""
回测历史记录 API
================
保存/查询/删除每次参数寻优的最优结果。
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from database import get_db
from models import BacktestRecord

router = APIRouter(prefix="/api/backtest-records", tags=["回测历史记录"])


# ── 请求模型 ──────────────────────────────────────────

class SaveRecordRequest(BaseModel):
    code: str
    asset_name: Optional[str] = None
    exit_mode: str
    objective: str = "calmar"
    best_params: dict
    sweep_params: list = []
    # 区间
    train_start: Optional[str] = None
    train_end: Optional[str] = None
    train_days: Optional[int] = None
    oos_start: Optional[str] = None
    oos_end: Optional[str] = None
    # 指标
    ann_return_pct: Optional[float] = None
    max_drawdown: Optional[float] = None
    calmar: Optional[float] = None
    profit_factor: Optional[float] = None
    sortino: Optional[float] = None
    win_rate: Optional[float] = None
    whipsaw_rate_pct: Optional[float] = None
    max_consec_loss: Optional[int] = None
    recovery_days: Optional[int] = None
    avg_win: Optional[float] = None
    avg_loss: Optional[float] = None
    total_combos: Optional[int] = None
    bh_return: Optional[float] = None
    notes: Optional[str] = None


def _to_dict(r: BacktestRecord) -> dict:
    return {
        "id":              r.id,
        "code":            r.code,
        "asset_name":      r.asset_name,
        "exit_mode":       r.exit_mode,
        "objective":       r.objective,
        "best_params":     json.loads(r.best_params) if r.best_params else {},
        "sweep_params":    json.loads(r.sweep_params) if r.sweep_params else [],
        "train_start":     r.train_start,
        "train_end":       r.train_end,
        "train_days":      r.train_days,
        "oos_start":       r.oos_start,
        "oos_end":         r.oos_end,
        "ann_return_pct":  r.ann_return_pct,
        "max_drawdown":    r.max_drawdown,
        "calmar":          r.calmar,
        "profit_factor":   r.profit_factor,
        "sortino":         r.sortino,
        "win_rate":        r.win_rate,
        "whipsaw_rate_pct": r.whipsaw_rate_pct,
        "max_consec_loss": r.max_consec_loss,
        "recovery_days":   r.recovery_days,
        "avg_win":         r.avg_win,
        "avg_loss":        r.avg_loss,
        "total_combos":    r.total_combos,
        "bh_return":       r.bh_return,
        "notes":           r.notes,
        "created_at":      r.created_at.isoformat() if r.created_at else None,
    }


# ── 路由 ──────────────────────────────────────────────

@router.post("")
def save_record(req: SaveRecordRequest, db: Session = Depends(get_db)):
    """保存一次寻优的最优结果"""
    r = BacktestRecord(
        code=req.code,
        asset_name=req.asset_name,
        exit_mode=req.exit_mode,
        objective=req.objective,
        best_params=json.dumps(req.best_params, ensure_ascii=False),
        sweep_params=json.dumps(req.sweep_params, ensure_ascii=False),
        train_start=req.train_start,
        train_end=req.train_end,
        train_days=req.train_days,
        oos_start=req.oos_start,
        oos_end=req.oos_end,
        ann_return_pct=req.ann_return_pct,
        max_drawdown=req.max_drawdown,
        calmar=req.calmar,
        profit_factor=req.profit_factor,
        sortino=req.sortino,
        win_rate=req.win_rate,
        whipsaw_rate_pct=req.whipsaw_rate_pct,
        max_consec_loss=req.max_consec_loss,
        recovery_days=req.recovery_days,
        avg_win=req.avg_win,
        avg_loss=req.avg_loss,
        total_combos=req.total_combos,
        bh_return=req.bh_return,
        notes=req.notes,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"ok": True, "id": r.id, "record": _to_dict(r)}


@router.get("")
def list_records(code: Optional[str] = None, db: Session = Depends(get_db)):
    """查询历史记录，可按 code 筛选，按时间倒序"""
    q = db.query(BacktestRecord)
    if code:
        q = q.filter(BacktestRecord.code == code)
    rows = q.order_by(BacktestRecord.created_at.desc()).all()
    return [_to_dict(r) for r in rows]


@router.get("/codes")
def list_codes(db: Session = Depends(get_db)):
    """获取所有有记录的标的代码列表（去重）"""
    from sqlalchemy import distinct
    rows = db.query(distinct(BacktestRecord.code), BacktestRecord.asset_name).all()
    seen = {}
    for code, name in rows:
        if code not in seen:
            seen[code] = name
    return [{"code": c, "name": n} for c, n in seen.items()]


@router.patch("/{record_id}/notes")
def update_notes(record_id: int, body: dict, db: Session = Depends(get_db)):
    """更新备注"""
    r = db.query(BacktestRecord).filter(BacktestRecord.id == record_id).first()
    if not r:
        raise HTTPException(404, "记录不存在")
    r.notes = body.get("notes", "")
    db.commit()
    return {"ok": True}


@router.delete("/{record_id}")
def delete_record(record_id: int, db: Session = Depends(get_db)):
    """删除一条记录"""
    r = db.query(BacktestRecord).filter(BacktestRecord.id == record_id).first()
    if not r:
        raise HTTPException(404, "记录不存在")
    db.delete(r)
    db.commit()
    return {"ok": True}
