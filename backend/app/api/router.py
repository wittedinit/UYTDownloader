from fastapi import APIRouter

from app.api.jobs import router as jobs_router
from app.api.probe import router as probe_router
from app.api.sources import router as sources_router
from app.api.subscriptions import router as subscriptions_router

api_router = APIRouter()
api_router.include_router(probe_router)
api_router.include_router(sources_router)
api_router.include_router(jobs_router)
api_router.include_router(subscriptions_router)
