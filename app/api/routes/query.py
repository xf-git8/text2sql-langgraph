# app/api/routes/query.py
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# 导入服务层
from app.api.query import query_service
# 导入认证依赖函数（注意：导入的是函数，不是方法调用）
from app.api.auth import get_current_user_dependency

security = HTTPBearer()
router = APIRouter(prefix="", tags=["查询模块"])


# ==================== 数据模型 ====================

class QueryRequest(BaseModel):
    question: str
    max_retries: Optional[int] = 3


class QueryResponse(BaseModel):
    question: str
    answer: str
    sql: Optional[str] = None
    tables: Optional[list] = None
    intention: Optional[str] = None


# ==================== 路由定义 ====================

@router.post("/query", response_model=QueryResponse)
async def query(
        request: QueryRequest,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        current_user: dict = Depends(get_current_user_dependency)
):
    """
    Text2SQL 自然语言查询接口
    - 请求头需携带: Authorization: Bearer <access_token>
    """
    try:
        result = await query_service.execute_query(
            question=request.question,
            max_retries=request.max_retries
        )

        return {
            "question": request.question,
            "answer": result.get("answer", ""),
            "sql": result.get("sql"),
            "tables": result.get("tables"),
            "intention": result.get("intention")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Text2SQL execution failed: {str(e)}"
        )
