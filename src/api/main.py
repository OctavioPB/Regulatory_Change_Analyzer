import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import alerts, contracts, dashboard, documents, health, ingestion
from src.database import init_db

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Regulatory Change Analyzer",
    description="Automated monitoring and impact analysis of regulatory changes",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production via settings
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(contracts.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(ingestion.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    logger.info("API started")
