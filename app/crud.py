from sqlalchemy import select
from models import User, Balance, Order


async def create_user(db, username: str):
    token = "generated_token"
    user = User(username=username, token=token)
    db.add(user)
    await db.commit()
    return user


async def get_user_by_token(db, token: str):
    result = await db.execute(select(User).where(User.token == token))
    return result.scalar_one_or_none()


async def get_balance(db, user_id: int, instrument: str):
    result = await db.execute(
        select(Balance)
        .where(Balance.user_id == user_id)
        .where(Balance.instrument == instrument)
    )
    return result.scalar_one_or_none()


async def create_order(db, user_id: int, order_data):
    order = Order(user_id=user_id, **order_data.dict())
    db.add(order)
    await db.commit()
    return order
