from datetime import datetime
from typing import List, Annotated
from enum import Enum

from pydantic import BaseModel, UUID4, conint, Field, StringConstraints, ConfigDict, field_validator


class UserRole(Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class Direction(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    NEW = "NEW"
    EXECUTED = "EXECUTED"
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"
    CANCELLED = "CANCELLED"


class NewUser(BaseModel):
    name: str = Field(..., min_length=3)


class UserResponse(BaseModel):
    id: str
    name: str
    role: str
    api_key: str

    class Config:
        from_attributes = True


TickerType = Annotated[
    str,
    StringConstraints(
        pattern=r'^[A-Z]{2,10}$',
        to_upper=True,
        strip_whitespace=True
    )
]


class InstrumentSchema(BaseModel):
    name: str
    ticker: TickerType

    @field_validator('ticker')
    def validate_ticker(cls, v):
        if not v.isupper() or len(v) < 2 or len(v) > 10:
            raise ValueError("Ticker must be 2-10 uppercase letters")
        return v


class Level(BaseModel):
    price: int
    qty: int


class L2OrderBook(BaseModel):
    bid_levels: List[Level]
    ask_levels: List[Level]


class TransactionSchema(BaseModel):
    ticker: str
    amount: int
    price: int
    timestamp: datetime

    model_config = ConfigDict(
        from_attributes=True,
        protected_namespaces=())


class LimitOrderBody(BaseModel):
    direction: Direction
    ticker: str
    qty: conint(ge=1)
    price: conint(gt=0)


class MarketOrderBody(BaseModel):
    direction: Direction
    ticker: str
    qty: conint(ge=1)


class CreateOrderResponse(BaseModel):
    success: bool = Field(default=True)
    order_id: UUID4


class BalanceOperation(BaseModel):
    user_id: UUID4
    ticker: str
    amount: conint(gt=0)
