from urllib.request import Request

from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.responses import JSONResponse

from app.database import engine, Base
from app.endpoints import router as api_router
import logging
from fastapi.security import HTTPBearer

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

security_scheme = HTTPBearer(
    bearerFormat="TOKEN",
    description="Enter your API key in format: TOKEN <your_api_key>"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger = logging.getLogger("uvicorn.access")
    logger.info("Application startup complete")

    yield

    logger.info("Application shutdown")
    await engine.dispose()


app = FastAPI(
    title="Stock Exchange API",
    version="0.1.0",
    lifespan=lifespan,
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    security=[security_scheme]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def global_exception_handler(request: Request, call_next):
    try:
        response = await call_next(request)
        response.headers.update({
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Allow-Origin": "*"
        })
        return response

    except Exception as exc:
        logger.error(f"Unhandled exception: {exc}", exc_info=True)

        error_content = {
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
                "details": "Internal server error occurred"
            }
        }

        return JSONResponse(
            status_code=500,
            content=jsonable_encoder(error_content),
            headers={
                "Access-Control-Allow-Headers": "Authorization, Content-Type",
                "Access-Control-Allow-Origin": "*"
            }
        )


app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
