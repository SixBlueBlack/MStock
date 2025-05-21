from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from app.models import (
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    Trade,
    Instrument,
    Balance
)
from app.schemas import OrderCreate, OrderResponse, OrderBookResponse
from app.dependencies import get_current_user
from app.database import get_db

router = APIRouter()


async def match_orders(db, order: Order):
    opposite_side = OrderSide.SELL if order.side == OrderSide.BUY else OrderSide.BUY
    price_condition = Order.price <= order.price if order.side == OrderSide.BUY else Order.price >= order.price

    query = (
        select(Order)
        .where(Order.instrument_symbol == order.instrument_symbol)
        .where(Order.side == opposite_side)
        .where(Order.status == OrderStatus.ACTIVE)
        .where(price_condition)
        .order_by(Order.price.asc() if order.side == OrderSide.BUY else Order.price.desc())
    )

    result = await db.execute(query)
    matching_orders = result.scalars().all()

    for matched_order in matching_orders:
        qty = min(order.quantity, matched_order.quantity)
        price = matched_order.price if order.type == OrderType.MARKET else order.price

        trade = Trade(
            buyer_order_id=order.id if order.side == OrderSide.BUY else matched_order.id,
            seller_order_id=matched_order.id if order.side == OrderSide.BUY else order.id,
            instrument_symbol=order.instrument_symbol,
            price=price,
            quantity=qty,
        )
        db.add(trade)

        order.quantity -= qty
        matched_order.quantity -= qty

        if order.quantity <= 0:
            order.status = OrderStatus.FILLED
        if matched_order.quantity <= 0:
            matched_order.status = OrderStatus.FILLED

        await db.commit()

        if order.status == OrderStatus.FILLED:
            break


@router.post("/orders", response_model=OrderResponse)
async def create_order(order_data: OrderCreate,
                       user=Depends(get_current_user),
                       db=Depends(get_db)):
    result = await db.execute(
        select(Instrument).where(Instrument.symbol == order_data.instrument)
    )
    instrument = result.scalar_one_or_none()
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")

    balance_instrument = "RUB" if order_data.side == "buy" else order_data.instrument
    result = await db.execute(
        select(Balance).where(and_(
            Balance.user_id == user.id,
            Balance.instrument == balance_instrument
        ))
    )
    balance = result.scalar_one_or_none()

    required_amount = Decimal(order_data.quantity) * (
        Decimal(order_data.price)
        if order_data.type == OrderType.LIMIT
        else Decimal(1)
    )

    if balance is None or balance.amount < required_amount:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    order = Order(
        user_id=user.id,
        instrument_symbol=order_data.instrument,
        type=order_data.type,
        side=order_data.side,
        price=Decimal(order_data.price) if order_data.price else None,
        quantity=Decimal(order_data.quantity),
        status=OrderStatus.ACTIVE
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    await match_orders(db, order)

    return order


@router.get("/orders", response_model=list[OrderResponse])
async def get_orders(user=Depends(get_current_user),
                     db=Depends(get_db)):
    result = await db.execute(
        select(Order).where(Order.user_id == user.id)
    )
    return result.scalars().all()


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int,
                    user=Depends(get_current_user),
                    db=Depends(get_db)):
    result = await db.execute(
        select(Order).where(and_(
            Order.id == order_id,
            Order.user_id == user.id
        ))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: int,
                       user=Depends(get_current_user),
                       db=Depends(get_db)):
    result = await db.execute(
        select(Order).where(and_(
            Order.id == order_id,
            Order.user_id == user.id,
            Order.status == OrderStatus.ACTIVE
        ))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not cancellable")

    order.status = OrderStatus.CANCELED
    await db.commit()
    return {"status": "canceled"}


@router.get("/orderbook/{instrument}", response_model=OrderBookResponse)
async def get_orderbook(instrument: str, db=Depends(get_db)):
    result = await db.execute(
        select(Order).where(and_(
            Order.instrument_symbol == instrument,
            Order.status == OrderStatus.ACTIVE
        ))
    )
    orders = result.scalars().all()

    bids = {}
    asks = {}

    for order in orders:
        if order.side == OrderSide.BUY:
            bids[order.price] = bids.get(order.price, 0) + order.quantity
        else:
            asks[order.price] = asks.get(order.price, 0) + order.quantity

    sorted_bids = sorted(bids.items(), key=lambda x: -x[0])
    sorted_asks = sorted(asks.items(), key=lambda x: x[0])

    return OrderBookResponse(
        bids=sorted_bids,
        asks=sorted_asks
    )
