from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.categories import router as categories_router
from app.api.v1.tags import router as tags_router
from app.api.v1.articles import router as articles_router
from app.api.v1.comments import router as comments_router
from app.api.v1.ai_assistant import router as ai_router
from app.api.v1.statistics import router as stats_router
from app.api.v1.favorites import router as favorites_router
from app.api.v1.notifications import router as notifications_router

api_v1_router = APIRouter(prefix="/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(categories_router)
api_v1_router.include_router(tags_router)
api_v1_router.include_router(articles_router)
api_v1_router.include_router(comments_router)
api_v1_router.include_router(ai_router)
api_v1_router.include_router(stats_router)
api_v1_router.include_router(favorites_router)
api_v1_router.include_router(notifications_router)
