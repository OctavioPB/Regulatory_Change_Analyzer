import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware.rate_limit import IngestRateLimitMiddleware
from src.api.routers import alerts, audit, contracts, cross_mapping, dashboard, documents, export, health, heatmap, ingestion, tasks, trends
from src.config import settings
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
app.add_middleware(
    IngestRateLimitMiddleware,
    max_requests=settings.ingest_rate_limit,
    window_seconds=60,
)

app.include_router(health.router)
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(contracts.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(ingestion.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(cross_mapping.router, prefix="/api/v1")
app.include_router(trends.router, prefix="/api/v1")
app.include_router(heatmap.router, prefix="/api/v1")


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    logger.info("API started")
