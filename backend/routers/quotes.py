from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db
from services.market import fetch_and_save_daily, fetch_and_save_history, detect_and_record_dividends
from datetime import datetime
import threading
import time

router = APIRouter(prefix="/api/quotes", tags=["行情同步"])

# 内存存储同步任务进度
_sync_tasks = {}
_sync_lock = threading.Lock()


def _run_sync_with_progress(task_id: str):
    """后台执行同步任务，更新进度"""
    from database import SessionLocal
    from models import Position, DailySnapshot, Trade, SyncLog
    from sqlalchemy import func
    from services.market import get_hist_prices, _save_snapshots, recalc_snapshots_pnl
    from datetime import date, timedelta
    import time as time_module
    
    db = SessionLocal()
    total_saved = 0
    
    try:
        positions = db.query(Position).all()
        total = len(positions)
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        with _sync_lock:
            _sync_tasks[task_id] = {
                "status": "running",
                "total": total,
                "completed": 0,
                "current": "",
                "message": "开始同步...",
                "saved": 0,
                "started_at": datetime.now().isoformat()
            }
        
        for idx, pos in enumerate(positions):
            # 更新进度
            with _sync_lock:
                _sync_tasks[task_id].update({
                    "completed": idx,
                    "current": f"{pos.code}({pos.short_name or pos.name})",
                    "message": f"正在同步 {pos.code}..."
                })
            
            time_module.sleep(0.5)  # 限速
            
            try:
                # 每个持仓的历史起点
                pos_earliest = db.query(func.min(Trade.trade_date)).filter(Trade.code == pos.code).scalar()
                pos_start = today - timedelta(days=365 * 5)
                if pos_earliest and pos_earliest < pos_start:
                    pos_start = pos_earliest

                # 查已有数据范围
                first_snap = db.query(DailySnapshot).filter(
                    DailySnapshot.code == pos.code
                ).order_by(DailySnapshot.date).first()

                last_snap = db.query(DailySnapshot).filter(
                    DailySnapshot.code == pos.code
                ).order_by(DailySnapshot.date.desc()).first()

                gaps = []
                if not first_snap:
                    gaps.append((pos_start.strftime("%Y%m%d"), yesterday.strftime("%Y%m%d"), "全量"))
                else:
                    if first_snap.date > pos_start:
                        gaps.append((pos_start.strftime("%Y%m%d"), first_snap.date.strftime("%Y%m%d"), "补历史"))
                    if last_snap.date < yesterday:
                        gaps.append(((last_snap.date + timedelta(days=1)).strftime("%Y%m%d"), yesterday.strftime("%Y%m%d"), "增量"))

                pos_saved = 0
                for start_date, end_date, mode in gaps:
                    prices = get_hist_prices(pos.code, start_date, end_date)
                    if prices:
                        saved = _save_snapshots(db, pos.code, prices)
                        pos_saved += saved
                        total_saved += saved

                # 更新当前价格
                if pos_saved > 0:
                    latest = db.query(DailySnapshot).filter(
                        DailySnapshot.code == pos.code
                    ).order_by(DailySnapshot.date.desc()).first()
                    if latest:
                        pos.current_price = latest.close
                        pos.updated_at = datetime.now()
                
                with _sync_lock:
                    _sync_tasks[task_id]["saved"] = total_saved
                    
            except Exception as e:
                print(f"同步 {pos.code} 失败: {e}")
                continue
        
        db.commit()
        
        # 记录同步日志
        sync_log = SyncLog(sync_type="history", synced_at=datetime.now(), record_count=total_saved)
        db.add(sync_log)
        db.commit()
        
        # 重算 pnl
        with _sync_lock:
            _sync_tasks[task_id]["message"] = "正在计算收益..."
        recalc_snapshots_pnl()
        
        with _sync_lock:
            _sync_tasks[task_id].update({
                "status": "completed",
                "completed": total,
                "message": f"同步完成，共 {total_saved} 条数据",
                "finished_at": datetime.now().isoformat()
            })
            
    except Exception as e:
        with _sync_lock:
            _sync_tasks[task_id].update({
                "status": "failed",
                "message": f"同步失败: {str(e)}",
                "finished_at": datetime.now().isoformat()
            })
    finally:
        db.close()
        # 清理旧任务（保留最近10个）
        with _sync_lock:
            if len(_sync_tasks) > 10:
                oldest = sorted(_sync_tasks.items(), key=lambda x: x[1].get("started_at", ""))[:len(_sync_tasks)-10]
                for k, _ in oldest:
                    del _sync_tasks[k]


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
def sync_quotes(background_tasks: BackgroundTasks):
    """手动触发行情同步：后台执行，返回任务ID用于查询进度"""
    import uuid
    task_id = str(uuid.uuid4())[:8]
    background_tasks.add_task(_run_sync_with_progress, task_id)
    return {"ok": True, "task_id": task_id, "message": "同步任务已启动"}


@router.get("/sync-progress/{task_id}")
def get_sync_progress(task_id: str):
    """获取同步任务进度"""
    with _sync_lock:
        task = _sync_tasks.get(task_id)
    
    if not task:
        return {"ok": False, "message": "任务不存在或已过期"}
    
    return {"ok": True, "progress": task}


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


@router.get("/last-sync")
def get_last_sync(db: Session = Depends(get_db)):
    """获取上次行情同步时间"""
    from models import SyncLog
    from sqlalchemy import desc
    
    last_sync = db.query(SyncLog).order_by(desc(SyncLog.synced_at)).first()
    
    if not last_sync:
        return {"last_sync": None, "sync_type": None, "record_count": 0}
    
    return {
        "last_sync": last_sync.synced_at.isoformat() if last_sync.synced_at else None,
        "sync_type": last_sync.sync_type,
        "record_count": last_sync.record_count
    }
