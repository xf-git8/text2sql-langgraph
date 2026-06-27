# -*-coding:utf-8-*-
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional


from app.agents.text2sql_agent import text2sql_graph
from app.api.auth import get_current_user


router = APIRouter()


class QueryRequest(BaseModel):
    """Text2SQL 查询请求体"""
    question: str
    max_retries: Optional[int] = 3


class QueryResponse(BaseModel):
    """Text2SQL 查询响应体"""
    question: str
    answer: str
    sql: Optional[str] = None
    tables: Optional[list] = None
    intention: Optional[str] = None


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user)  # 需要认证才能访问
):
    """
    Text2SQL 自然语言转 SQL 查询接口
    - 需要先通过 /v1/login 获取 Access Token
    - 在请求头中携带 Authorization: Bearer <token>
    """
    try:
        inputs = {
            "question": request.question,
            "processed_question": "",
            "intention": "",
            "relevant_tables": [],
            "schema_context": "",
            "generated_sql": None,
            "validation_result": {},
            "execution_result": [],
            "execution_error": None,
            "answer": "",
            "retry_count": 0,
            "max_retries": request.max_retries
        }

        result = text2sql_graph.invoke(inputs)

        return {
            "question": request.question,
            "answer": result.get("answer", ""),
            "sql": result.get("generated_sql"),
            "tables": result.get("relevant_tables"),
            "intention": result.get("intention")
        }

    except HTTPException:
        #让认证失败的 401 正常透传，不被包装成 500
        raise
    except Exception as e:
        # 仅捕获 text2sql_graph 的业务执行异常
        raise HTTPException(
            status_code=500,
            detail=f"Text2SQL execution failed: {str(e)}"
        )