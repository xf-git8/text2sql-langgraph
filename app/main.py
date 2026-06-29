import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings import settings
from app.api import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description=settings.DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# 跨域配置（生产环境建议将 allow_origins 限制为具体的前端域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 第一层只挂载全局 API 前缀 /api
# 版本前缀 /v1 交给下层 app/api/__init__.py 管理 注册路由
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    """API 根路由健康检查"""
    return {
        "message": "LangGraph Text-to-SQL Agent API",
        "version": settings.PROJECT_VERSION,
        "docs": "/docs"
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
