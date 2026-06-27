from fastapi import APIRouter
from .auth import router as auth_router
from .query import router as query_router
# from .health import router as health_router

router = APIRouter()

router.include_router(auth_router, prefix="/v1")
router.include_router(query_router, prefix="/v1")
# router.include_router(health_router, prefix="/v1")