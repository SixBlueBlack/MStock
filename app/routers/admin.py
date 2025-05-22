from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, and_, update
from app.models import User, Instrument, Balance
from app.dependencies import get_current_user, check_admin
from app.database import get_db
from pydantic import BaseModel
from app.schemas import InstrumentCreate, InstrumentResponse

router = APIRouter()


class BalanceUpdate(BaseModel):
    user_id: int
    instrument: str
    amount: float


@router.delete("/users/{user_id}")
async def delete_user(user_id: int,
                      db=Depends(get_db),
                      admin=Depends(check_admin)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    await db.commit()
    return {"status": "deleted"}


@router.post("/balance")
async def update_balance(
        update: BalanceUpdate,
        db=Depends(get_db),
        admin=Depends(check_admin)
):
    result = await db.execute(
        select(Balance).where(and_(
            Balance.user_id == update.user_id,
            Balance.instrument == update.instrument
        ))
    )
    balance = result.scalar_one_or_none()

    amount = Decimal(update.amount)

    if balance:
        balance.amount += amount
    else:
        balance = Balance(
            user_id=update.user_id,
            instrument=update.instrument,
            amount=amount
        )
        db.add(balance)

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Balance update error: {str(e)}"
        )

    return balance


@router.post("/instrument", response_model=InstrumentResponse)
async def create_instrument(
        instrument_data: InstrumentCreate,
        db=Depends(get_db),
        user=Depends(get_current_user)
):
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    existing = await db.execute(
        select(Instrument).where(Instrument.symbol == instrument_data.symbol)
    )
    if existing.scalar():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Instrument with this symbol already exists"
        )

    instrument = Instrument(**instrument_data.dict())
    db.add(instrument)
    await db.commit()
    await db.refresh(instrument)
    return instrument


@router.delete("/instrument/{symbol}")
async def delete_instrument(
        symbol: str,
        db=Depends(get_db),
        user=Depends(get_current_user)
):
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    result = await db.execute(
        select(Instrument).where(Instrument.symbol == symbol)
    )
    instrument = result.scalar()

    if not instrument:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instrument not found"
        )

    await db.execute(
        update(Instrument)
        .where(Instrument.symbol == symbol)
        .values(is_active=False)
    )
    await db.commit()

    return {"message": "Instrument delisted successfully"}
