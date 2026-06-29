# 汇总注册路由
from fastapi import APIRouter

# 导入各个模块的 router
from .routes.auth import router as auth_router
from .routes.query import router as query_router

# 创建一个路由对象
api_router = APIRouter()
# 注册各个模块的 router
api_router.include_router(auth_router, prefix="", tags=["认证模块"])
api_router.include_router(query_router, prefix="", tags=["查询模块"])
