from fastapi.security import APIKeyHeader
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.database import engine
from app.models import User, Order, Balance, Transaction
from app.schemas import UserRole, Direction, OrderStatus

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

security = APIKeyHeader(name="Authorization")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
        authorization: str = Header(None),
        db: Session = Depends(get_db)
) -> User:
    if not authorization or not authorization.startswith("TOKEN "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    api_key = authorization.split(" ")[1]
    user = db.query(User).filter(User.api_key == api_key).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return user


def match_order(db: Session, order: Order):
    try:
        opposite_direction = Direction.SELL if order.direction == Direction.BUY else Direction.BUY
        base_currency, quote_currency = ('RUB', order.ticker) if order.direction == Direction.BUY else (
            order.ticker, 'RUB')

        query = db.query(Order).filter(
            Order.ticker == order.ticker,
            Order.direction == opposite_direction,
            Order.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED])
        )

        if order.order_type == 'limit':
            if order.direction == Direction.BUY:
                query = query.filter(Order.price <= order.price)
            else:
                query = query.filter(Order.price >= order.price)

        matching_orders = query.order_by(
            Order.price.asc() if order.direction == Direction.BUY else Order.price.desc()
        ).all()

        remaining_qty = order.qty - order.filled

        for matching_order in matching_orders:
            if remaining_qty <= 0:
                break

            matchable_qty = min(
                remaining_qty,
                matching_order.qty - matching_order.filled
            )

            execution_price = matching_order.price if order.order_type == 'market' else order.price
            total_amount = matchable_qty * execution_price

            with db.begin_nested():
                buyer = order.user if order.direction == Direction.BUY else matching_order.user
                seller = matching_order.user if order.direction == Direction.BUY else order.user

                buyer_balance = db.query(Balance).filter(
                    Balance.user_id == buyer.id,
                    Balance.ticker == base_currency
                ).first()

                if not buyer_balance:
                    buyer_balance = Balance(user_id=buyer.id, ticker=base_currency, amount=0)
                    db.add(buyer_balance)

                buyer_balance.amount += matchable_qty if order.direction == Direction.BUY else total_amount

                seller_balance = db.query(Balance).filter(
                    Balance.user_id == seller.id,
                    Balance.ticker == quote_currency
                ).first()

                if not seller_balance:
                    seller_balance = Balance(user_id=seller.id, ticker=quote_currency, amount=0)
                    db.add(seller_balance)

                seller_balance.amount += total_amount if order.direction == Direction.BUY else matchable_qty

                order.filled += matchable_qty
                matching_order.filled += matchable_qty

                order.status = OrderStatus.EXECUTED if order.filled >= order.qty else OrderStatus.PARTIALLY_EXECUTED
                matching_order.status = OrderStatus.EXECUTED if matching_order.filled >= matching_order.qty else OrderStatus.PARTIALLY_EXECUTED

                transaction = Transaction(
                    ticker=order.ticker,
                    amount=matchable_qty,
                    price=execution_price
                )
                db.add(transaction)

                remaining_qty -= matchable_qty

        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")
