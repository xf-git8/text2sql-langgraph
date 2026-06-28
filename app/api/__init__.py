# 汇总注册路由
from fastapi import APIRouter
from .routes.auth import router as auth_router
from .routes.query import router as query_router


router = APIRouter()
# 注册子路由
router.include_router(auth_router)
router.include_router(query_router)
