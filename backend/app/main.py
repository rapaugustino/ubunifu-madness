from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import teams, predictions, rankings, compare, bracket, chat, espn


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Ubunifu Madness API",
    description="AI-Powered March Madness Predictions",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(teams.router, prefix="/api")
app.include_router(predictions.router, prefix="/api")
app.include_router(rankings.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(bracket.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(espn.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
