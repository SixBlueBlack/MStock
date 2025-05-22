from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, String, Integer, Enum as SqlEnum, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from app.database import Base, engine
from app.schemas import UserRole, Direction, OrderStatus


class User(Base):
    __tablename__ = "users"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(50), nullable=False)
    role = Column(SqlEnum(UserRole), default=UserRole.USER)
    api_key = Column(String(36), unique=True, index=True)
    balances = relationship("Balance", back_populates="user")


class Instrument(Base):
    __tablename__ = "instruments"
    ticker = Column(String(10), primary_key=True)
    name = Column(String(50))


class Order(Base):
    __tablename__ = "orders"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    direction = Column(SqlEnum(Direction))
    ticker = Column(String(10))
    qty = Column(Integer)
    price = Column(Integer)
    status = Column(SqlEnum(OrderStatus), default=OrderStatus.NEW)
    order_type = Column(String(10))
    created_at = Column(DateTime, default=datetime.utcnow)
    filled = Column(Integer, default=0)
    user = relationship("User")


class Balance(Base):
    __tablename__ = "balances"
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    ticker = Column(String(10), primary_key=True)
    amount = Column(Integer, default=0)
    user = relationship("User", back_populates="balances")


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    ticker = Column(String(10))
    amount = Column(Integer)
    price = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)

