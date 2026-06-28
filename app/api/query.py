# app/api/query.py
import logging
from typing import Dict, Any
from app.agents.text2sql_agent import text2sql_graph

logger = logging.getLogger(__name__)


class QueryService:
    """Text2SQL 查询服务类"""

    async def execute_query(self, question: str, max_retries: int = 3) -> Dict[str, Any]:
        inputs = {
            "question": question,
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
            "max_retries": max_retries
        }

        try:
            result = text2sql_graph.invoke(inputs)
            return {
                "answer": result.get("answer", ""),
                "sql": result.get("generated_sql"),
                "tables": result.get("relevant_tables"),
                "intention": result.get("intention")
            }
        except Exception as e:
            logger.error(f"Text2SQL Agent execution error: {e}", exc_info=True)
            raise


# 单例导出
query_service = QueryService()