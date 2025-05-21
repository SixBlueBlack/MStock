from fastapi import APIRouter, Depends
from app.schemas import UserCreate, UserResponse
from app.crud import create_user
from app.database import get_db
import secrets

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate, db=Depends(get_db)):
    # Генерация безопасного токена
    token = secrets.token_urlsafe(32)
    return await create_user(db, user_data.username, token)
