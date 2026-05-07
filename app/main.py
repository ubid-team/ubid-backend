from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_chat,
    routes_compat,
    routes_dashboard,
    routes_data,
    routes_health,
    routes_resolution,
    routes_ubid,
)
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.data.repository import DataRepository
from app.services.chat_service import ChatService
from app.services.dashboard_service import DashboardService
from app.services.entity_resolution import EntityResolutionService
from app.services.llm_service import LLMService
from app.services.recommendation_service import RecommendationService
from app.services.risk_service import RiskService
from app.services.ubid_service import UBIDService


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    repository = DataRepository(settings)
    repository.load()

    entity_resolution_service = EntityResolutionService(repository, settings)
    risk_service = RiskService(repository)
    recommendation_service = RecommendationService(repository)
    dashboard_service = DashboardService(repository, risk_service)
    llm_service = LLMService(settings)
    ubid_service = UBIDService(repository, entity_resolution_service)
    chat_service = ChatService(
        repository=repository,
        resolution_service=entity_resolution_service,
        recommendation_service=recommendation_service,
        dashboard_service=dashboard_service,
        llm_service=llm_service,
    )

    app.state.repository = repository
    app.state.entity_resolution_service = entity_resolution_service
    app.state.risk_service = risk_service
    app.state.recommendation_service = recommendation_service
    app.state.dashboard_service = dashboard_service
    app.state.llm_service = llm_service
    app.state.ubid_service = ubid_service
    app.state.chat_service = chat_service
    yield


app = FastAPI(
    title="UBID Backend MVP",
    version="0.1.0",
    description="Unified Business Identity Resolution backend for Karnataka.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.all_cors_origins,
    allow_origin_regex=(
        r"https?://("
        r"localhost(:\d+)?"
        r"|127\.0\.0\.1(:\d+)?"
        r"|([\w-]+\.)*vercel\.app"
        r"|([\w-]+\.)*pages\.dev"
        r"|([\w-]+\.)*workers\.dev"
        r"|([\w-]+\.)*onrender\.com"
        r")"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(routes_health.router)
app.include_router(routes_data.router)
app.include_router(routes_resolution.router)
app.include_router(routes_ubid.router)
app.include_router(routes_dashboard.router)
app.include_router(routes_chat.router)
app.include_router(routes_compat.router)
