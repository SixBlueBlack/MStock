from sqlalchemy import Column, Integer, String, Numeric, Enum, ForeignKey, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base
from sqlalchemy import MetaData
import enum

metadata = MetaData()


class OrderType(str, enum.Enum):
    LIMIT = "limit"
    MARKET = "market"


class OrderSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    FILLED = "filled"


def define_all_models(base):
    class User(base):
        __tablename__ = "users"
        __table_args__ = {'extend_existing': True}

        id = Column(Integer, primary_key=True)
        username = Column(String(50), unique=True)
        token = Column(String(100), unique=True)
        is_admin = Column(Boolean, default=False)

    class Balance(base):
        __tablename__ = "balances"
        __table_args__ = {'extend_existing': True}

        user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
        instrument = Column(String(10), primary_key=True)
        amount = Column(Numeric(20, 2), default=0)

    class Instrument(base):
        __tablename__ = "instruments"
        __table_args__ = {'extend_existing': True}

        symbol = Column(String(10), primary_key=True)
        name = Column(String(100))
        is_active = Column(Boolean, default=True)

    class Order(base):
        __tablename__ = "orders"
        __table_args__ = {'extend_existing': True}

        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey("users.id"))
        instrument_symbol = Column(String(10), ForeignKey("instruments.symbol"))
        type = Column(Enum(OrderType))
        side = Column(Enum(OrderSide))
        price = Column(Numeric(20, 2))
        quantity = Column(Numeric(20, 2))
        status = Column(Enum(OrderStatus), default=OrderStatus.ACTIVE)
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    class Trade(base):
        __tablename__ = "trades"
        __table_args__ = {'extend_existing': True}

        id = Column(Integer, primary_key=True)
        buyer_order_id = Column(Integer, ForeignKey("orders.id"))
        seller_order_id = Column(Integer, ForeignKey("orders.id"))
        instrument_symbol = Column(String(10))
        price = Column(Numeric(20, 2))
        quantity = Column(Numeric(20, 2))
        executed_at = Column(DateTime(timezone=True), server_default=func.now())

    return User, Balance, Instrument, Order, Trade


User, Balance, Instrument, Order, Trade = define_all_models(Base)
__all__ = [
    'OrderType',
    'OrderSide',
    'OrderStatus',
    'User',
    'Balance',
    'Instrument',
    'Order',
    'Trade'
]
