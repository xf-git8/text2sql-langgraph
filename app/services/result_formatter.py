"""
- 使用 LLM 将SQL执行结果转换为自然语言回答
- 处理空结果、单行结果和多行结果
- 结果长度限制防止超出模型上下文
- 降级方案：简单格式化作为兜底
"""
import json
import logging
from decimal import Decimal
from datetime import date, datetime
from typing import List, Dict, Any, Union

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ResultFormatter:
    """查询结果格式化器，将SQL执行结果转换为自然语言回答"""

    MAX_RESULT_LENGTH = 2000

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.3,
        )
        self.format_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一个数据分析专家。请根据用户的问题、执行的SQL和查询结果，生成清晰、友好的自然语言回答。

            回答规则：
            1. 使用中文回答
            2. 如果结果为空，说明没有找到相关数据
            3. 如果结果只有一行，直接给出答案
            4. 如果结果有多行，可以用列表或表格形式呈现
            5. 不要解释SQL，直接回答用户问题
            6. 如果数据量较大，给出摘要和关键信息
            7. 保持回答简洁明了""",
                ),
                (
                    "human",
                    """用户问题：{question}

            执行的SQL：{sql}

            查询结果：{result}

            请用自然语言回答用户问题：""",
                ),
            ]
        )
        self.format_chain = self.format_prompt | self.llm

    #  新的序列化方法
    def _serialize_result(self, data: Any) -> str:
        """
        将包含 Decimal/日期等不可序列化对象的结果转换为截断后的 JSON 字符串
        """
        def _convert(obj: Any) -> Any:
            if isinstance(obj, Decimal):
                return float(obj)
            elif isinstance(obj, (datetime, date)):
                return obj.isoformat()
            elif isinstance(obj, list):
                return [_convert(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: _convert(v) for k, v in obj.items()}
            return obj

        try:
            clean_data = _convert(data)
            result_str = json.dumps(clean_data, ensure_ascii=False, indent=2)
            # 防止超出 LLM 上下文窗口
            if len(result_str) > self.MAX_RESULT_LENGTH:
                result_str = result_str[: self.MAX_RESULT_LENGTH] + "\n... (数据已截断)"
            return result_str
        except Exception as e:
            logger.warning(f"序列化结果失败，降级为 str(): {e}")
            return str(data)[: self.MAX_RESULT_LENGTH]

    def format(self, question: str, sql: str, result: Union[List, Dict, Any]) -> str:
        """将SQL查询结果格式化为自然语言回答"""
        try:
            if not result or (isinstance(result, (list, dict)) and len(result) == 0):
                return f"未找到与「{question}」相关的数据"

            #_serialize_result定义
            result_str = self._serialize_result(result)
            response = self.format_chain.invoke(
                {"question": question, "sql": sql, "result": result_str}
            )
            return response.content.strip()

        except Exception as e:
            logger.error(f"结果格式化失败: {e}", exc_info=True)
            return self._simple_format(question, result)

    def _simple_format(self, question: str, result: Any) -> str:
        """降级格式化：当LLM调用失败时，使用简单规则格式化结果"""
        if not result:
            return f"未找到与「{question}」相关的数据"

        # 降级方案也需要处理 Decimal，避免打印出 Decimal('5999.00')
        def _safe_str(val: Any) -> str:
            if isinstance(val, Decimal):
                return str(float(val))
            return str(val)

        if isinstance(result, list):
            if len(result) == 1:
                row = result[0]
                if isinstance(row, dict):
                    items = ", ".join(f"{k}: {_safe_str(v)}" for k, v in row.items())
                    return f"查询结果：{items}"
                return f"查询结果：{_safe_str(row)}"
            lines = []
            for i, row in enumerate(result, 1):
                if isinstance(row, dict):
                    items = ", ".join(f"{k}: {_safe_str(v)}" for k, v in row.items())
                    lines.append(f"{i}. {items}")
                else:
                    lines.append(f"{i}. {_safe_str(row)}")
            return "\n".join(lines)

        if isinstance(result, dict):
            lines = [f"- {k}: {_safe_str(v)}" for k, v in result.items()]
            return "查询结果：\n" + "\n".join(lines)

        return _safe_str(result)


result_formatter = ResultFormatter()