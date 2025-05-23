from typing import Union, List
from uuid import uuid4

from fastapi import Depends, HTTPException, APIRouter
from pydantic import UUID4
from sqlalchemy import and_, text, select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.dependencies import get_admin_user, get_db, get_current_user, match_order

from app.models import User, Balance, Instrument, Order, Transaction
from app.schemas import UserResponse, BalanceOperation, InstrumentSchema, OrderStatus, LimitOrderBody, MarketOrderBody, \
    CreateOrderResponse, TransactionSchema, L2OrderBook, Level, UserRole, NewUser

router = APIRouter()


@router.post("/public/register", response_model=UserResponse)
async def register(user: NewUser, db: AsyncSession = Depends(get_db)):
    api_key = str(uuid4())
    db_user = User(
        id=uuid4(),
        name=user.name,
        api_key=api_key,
        role=UserRole.USER
    )
    db.add(db_user)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Registration failed")
    await db.refresh(db_user)

    return {
        "id": str(db_user.id),
        "name": db_user.name,
        "role": db_user.role.value,
        "api_key": db_user.api_key
    }


@router.get("/api/v1/public/instrument", response_model=List[InstrumentSchema])
def list_instruments(db: Session = Depends(get_db)):
    return db.query(Instrument).all()


@router.get("/api/v1/public/orderbook/{ticker}", response_model=L2OrderBook)
def get_orderbook(ticker: str, limit: int = 10, db: Session = Depends(get_db)):
    bids = db.execute(text("""
        SELECT price, SUM(qty - filled) as qty 
        FROM orders 
        WHERE ticker = :ticker AND direction = 'BUY' AND status IN ('NEW', 'PARTIALLY_EXECUTED')
        GROUP BY price 
        ORDER BY price DESC 
        LIMIT :limit
    """), {"ticker": ticker, "limit": limit}).fetchall()

    asks = db.execute(text("""
        SELECT price, SUM(qty - filled) as qty 
        FROM orders 
        WHERE ticker = :ticker AND direction = 'SELL' AND status IN ('NEW', 'PARTIALLY_EXECUTED')
        GROUP BY price 
        ORDER BY price ASC 
        LIMIT :limit
    """), {"ticker": ticker, "limit": limit}).fetchall()

    return L2OrderBook(
        bid_levels=[Level(price=price, qty=qty) for price, qty in bids],
        ask_levels=[Level(price=price, qty=qty) for price, qty in asks]
    )


@router.get("/api/v1/public/transactions/{ticker}", response_model=List[TransactionSchema])
def get_transactions(ticker: str, limit: int = 10, db: Session = Depends(get_db)):
    return db.query(Transaction).filter(
        Transaction.ticker == ticker
    ).order_by(Transaction.timestamp.desc()).limit(limit).all()


@router.get("/api/v1/balance", response_model=dict)
def get_balances(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    balances = db.query(Balance).filter(Balance.user_id == user.id).all()
    return {b.ticker: b.amount for b in balances}


@router.post("/api/v1/order", response_model=CreateOrderResponse)
def create_order(
        order: Union[LimitOrderBody, MarketOrderBody],
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    instrument = db.query(Instrument).get(order.ticker)
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")

    db_order = Order(
        user_id=user.id,
        direction=order.direction,
        ticker=order.ticker,
        qty=order.qty,
        price=order.price if isinstance(order, LimitOrderBody) else None,
        order_type='limit' if isinstance(order, LimitOrderBody) else 'market'
    )

    db.add(db_order)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Order creation failed")

    match_order(db, db_order)

    return CreateOrderResponse(order_id=db_order.id)


@router.get("/api/v1/order", response_model=List[Union[LimitOrderBody, MarketOrderBody]])
def list_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Order).filter(Order.user_id == user.id).all()


@router.get("/api/v1/order/{order_id}", response_model=Union[LimitOrderBody, MarketOrderBody])
def get_order(order_id: UUID4, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(and_(
        Order.id == order_id,
        Order.user_id == user.id
    )).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.delete("/api/v1/order/{order_id}", response_model=dict)
def cancel_order(order_id: UUID4, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(and_(
        Order.id == order_id,
        Order.user_id == user.id
    )).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status not in [OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]:
        raise HTTPException(status_code=400, detail="Cannot cancel executed order")

    order.status = OrderStatus.CANCELLED
    db.commit()
    return {"success": True}


@router.post("/api/v1/admin/instrument")
async def add_instrument(
        instrument: InstrumentSchema,
        db: AsyncSession = Depends(get_db)
):
    try:
        exists = await db.execute(
            select(Instrument).filter(Instrument.ticker == instrument.ticker))
        if exists.scalar():
            raise HTTPException(status_code=400, detail="Instrument already exists")

        db_instrument = Instrument(
            ticker=instrument.ticker,
            name=instrument.name
        )
        db.add(db_instrument)
        await db.commit()
        return {"success": True}
    except IntegrityError:
        raise HTTPException(
            status_code=400,
            detail="Instrument already exists"
        )


@router.delete("/api/v1/admin/instrument/{ticker}", response_model=dict)
def delete_instrument(ticker: str, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    instrument = db.query(Instrument).get(ticker)
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")

    db.delete(instrument)
    db.commit()
    return {"success": True}


@router.post("/api/v1/admin/balance/deposit", response_model=dict)
def deposit(data: BalanceOperation, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    balance = db.query(Balance).filter(and_(
        Balance.user_id == data.user_id,
        Balance.ticker == data.ticker
    )).first()

    if not balance:
        balance = Balance(
            user_id=data.user_id,
            ticker=data.ticker,
            amount=data.amount
        )
    else:
        balance.amount += data.amount

    db.add(balance)
    db.commit()
    return {"success": True}


@router.post("/api/v1/admin/balance/withdraw", response_model=dict)
def withdraw(data: BalanceOperation, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    balance = db.query(Balance).filter(and_(
        Balance.user_id == data.user_id,
        Balance.ticker == data.ticker
    )).first()

    if not balance or balance.amount < data.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    balance.amount -= data.amount
    db.add(balance)
    db.commit()
    return {"success": True}


@router.delete("/api/v1/admin/user/{user_id}", response_model=UserResponse)
def delete_user(user_id: UUID4, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return user
