from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class UserCreate(BaseModel):
    username: str


class UserResponse(UserCreate):
    token: str


class BalanceResponse(BaseModel):
    instrument: str
    amount: float


class OrderCreate(BaseModel):
    type: str = Field(..., pattern="^(limit|market)$")
    instrument: str
    side: str = Field(..., pattern="^(buy|sell)$")
    quantity: float
    price: Optional[float] = None


class OrderResponse(OrderCreate):
    id: int
    status: str
    created_at: datetime


class OrderBookResponse(BaseModel):
    bids: List[tuple[float, float]]
    asks: List[tuple[float, float]]


class Candle(BaseModel):
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: datetime


class TradeHistory(BaseModel):
    id: int
    price: float
    quantity: float
    executed_at: datetime
    instrument: str


class InstrumentResponse(BaseModel):
    symbol: str
    name: str
    is_active: bool
