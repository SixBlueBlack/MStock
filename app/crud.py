from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from app.models import User, Balance, Order
import secrets

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_user(db, username: str):
    try:
        # Генерация токена
        token = secrets.token_urlsafe(32)

        # Создание пользователя
        user = User(username=username, token=token)
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Создание начального баланса
        balance = Balance(
            user_id=user.id,
            instrument="RUB",
            amount=100000.00
        )
        db.add(balance)
        await db.commit()

        return user

    except IntegrityError:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise RuntimeError(f"Error creating user: {str(e)}")


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
