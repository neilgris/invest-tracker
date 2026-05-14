from sqlalchemy.orm import Session
from models import Trade, Position, DailySnapshot
from schemas import TradeCreate, TradeUpdate
from datetime import datetime
import time


def _calc_quantity(amount: float, price: float, fee: float) -> float:
    """计算数量：(总金额 - 手续费) / 价格，保留2位小数"""
    net = amount - (fee or 0)
    if price <= 0 or net <= 0:
        return 0.0
    return round(net / price, 2)


def recalc_position(db: Session, code: str):
    """根据交易记录重新计算持仓
    
    核心逻辑：
    - amount 是总交易金额（含手续费）
    - quantity = (amount - fee) / price
    - 买入：total_cost += amount（实际花了多少钱），quantity 增加
    - 卖出：按当前成本单价减少成本，保持单价不变（FIFO逻辑）
    - 分红再投资：total_cost 不变（分红是收益再投资，不增加成本），quantity 增加
    """
    trades = db.query(Trade).filter(Trade.code == code).order_by(Trade.trade_date).all()
    if not trades:
        pos = db.query(Position).filter(Position.code == code).first()
        if pos:
            db.delete(pos)
        return

    total_cost = 0.0
    total_quantity = 0.0
    name = trades[0].name

    for t in trades:
        qty = t.quantity if t.quantity else _calc_quantity(t.amount, t.price, t.fee or 0)

        if t.direction == "buy":
            # 买入：花了 amount（含手续费），得到 qty 份
            total_cost += t.amount
            total_quantity += qty
        elif t.direction == "sell":
            # 卖出：按当前成本单价减少成本，保持单价不变
            # 当前成本单价 = total_cost / total_quantity
            if total_quantity > 0:
                avg_cost_before = total_cost / total_quantity
                cost_to_reduce = qty * avg_cost_before
                total_cost -= cost_to_reduce
            total_quantity -= qty
        elif t.direction == "dividend":
            # 分红再投资：增加 qty 份，但不增加成本
            # amount 记录的是分红的现金金额（用于参考），不影响成本计算
            total_quantity += qty

    # 如果数量归零或以下，清空持仓
    if total_quantity <= 0:
        pos = db.query(Position).filter(Position.code == code).first()
        if pos:
            db.delete(pos)
        return

    avg_cost = total_cost / total_quantity if total_quantity > 0 else 0

    pos = db.query(Position).filter(Position.code == code).first()
    if pos:
        pos.name = name
        pos.total_cost = total_cost
        pos.quantity = total_quantity
        pos.avg_cost = avg_cost
        pos.updated_at = datetime.now()
    else:
        pos = Position(
            code=code,
            name=name,
            total_cost=total_cost,
            quantity=total_quantity,
            avg_cost=avg_cost,
            current_price=0.0,
        )
        db.add(pos)


def create_trade(db: Session, trade: TradeCreate) -> Trade:
    # 检查是否为新持仓（创建交易前）
    from models import Position
    existing_pos = db.query(Position).filter(Position.code == trade.code).first()
    is_new_position = existing_pos is None

    # 自动推算quantity: (amount - fee) / price
    if trade.quantity is None:
        trade.quantity = _calc_quantity(trade.amount, trade.price, trade.fee or 0)

    db_trade = Trade(**trade.model_dump())
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)

    recalc_position(db, trade.code)
    db.commit()

    # 如果是新持仓，异步同步历史行情数据
    if is_new_position:
        print(f"检测到新持仓 {trade.code}，启动历史数据同步...")
        import threading
        from services.market import sync_single_position_history
        # 使用后台线程避免阻塞用户
        def sync_in_background():
            time.sleep(0.5)  # 稍等确保事务提交
            sync_single_position_history(trade.code)
        threading.Thread(target=sync_in_background, daemon=True).start()
    else:
        # 重算该代码的快照收益
        from services.market import recalc_snapshots_pnl
        recalc_snapshots_pnl(trade.code)

    return db_trade


def update_trade(db: Session, trade_id: int, trade_update: TradeUpdate) -> Trade | None:
    db_trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not db_trade:
        return None

    update_data = trade_update.model_dump(exclude_unset=True)

    # 检查是否需要重新计算 quantity
    # 如果 price/amount/fee 任一变了，且用户没有显式传 quantity，则自动重算
    price_changed = 'price' in update_data
    amount_changed = 'amount' in update_data
    fee_changed = 'fee' in update_data
    quantity_provided = 'quantity' in update_data

    if (price_changed or amount_changed or fee_changed) and not quantity_provided:
        # 使用更新后的值（如果没传就用原值）
        new_price = update_data.get('price', db_trade.price)
        new_amount = update_data.get('amount', db_trade.amount)
        new_fee = update_data.get('fee', db_trade.fee)
        update_data['quantity'] = _calc_quantity(new_amount, new_price, new_fee or 0)

    for key, value in update_data.items():
        setattr(db_trade, key, value)

    db.commit()
    db.refresh(db_trade)

    # 重新计算持仓
    recalc_position(db, db_trade.code)
    db.commit()

    # 重算该代码的快照收益
    from services.market import recalc_snapshots_pnl
    recalc_snapshots_pnl(db_trade.code)

    return db_trade


def delete_trade(db: Session, trade_id: int) -> bool:
    db_trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not db_trade:
        return False

    code = db_trade.code
    db.delete(db_trade)
    db.commit()

    recalc_position(db, code)
    db.commit()

    # 重算该代码的快照收益
    from services.market import recalc_snapshots_pnl
    recalc_snapshots_pnl(code)

    return True
