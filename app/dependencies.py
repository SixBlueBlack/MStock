from fastapi.security import APIKeyHeader
from fastapi import Depends, HTTPException, status
from app.crud import get_user_by_token
from app.database import get_db

security = APIKeyHeader(name="Authorization")


async def get_current_user(
        token: str = Depends(security),
        db=Depends(get_db)
):
    if not token.startswith("TOKEN "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme"
        )
    token_value = token[6:]
    user = await get_user_by_token(db, token_value)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    return user


async def check_admin(user=Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return user
