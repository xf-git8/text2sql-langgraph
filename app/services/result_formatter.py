"""
- 使用 LLM 将SQL执行结果转换为自然语言回答
- 处理空结果、单行结果和多行结果
- 结果长度限制防止超出模型上下文
- 降级方案：简单格式化作为兜底
"""
import logging
from langchain_openai import ChatOpenAI
from typing import List, Dict, Any, Union
from langchain.prompts import ChatPromptTemplate

from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ResultFormatter:
    """查询结果格式化器，将SQL执行结果转换为自然语言回答"""
    # 结果字符串最大长度，超过则截断
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

    def format(self, question: str, sql: str, result: Union[List, Dict, Any]) -> str:

        """
        将SQL查询结果格式化为自然语言回答
        Args:
            question: 用户原始问题
            sql: 执行的SQL语句
            result: SQL查询结果
        Returns:
            自然语言格式化的回答
        """
        try:
            # 空结果快速返回
            if not result or (isinstance(result, (list, dict)) and len(result) == 0):
                return f"未找到与「{question}」相关的数据"

            result_str = self._serialize_result(result)
            response = self.format_chain.invoke(
                {"question": question, "sql": sql, "result": result_str}
            )
            return response.content.strip()

        except Exception as e:
            logger.error(f"结果格式化失败: {e}")
            return self._simple_format(question, result)

    def _simple_format(self, question: str, result: Any) -> str:
        """降级格式化：当LLM调用失败时，使用简单规则格式化结果"""
        if not result:
            return f"未找到与「{question}」相关的数据"
        # 列表类型结果
        if isinstance(result, list):
            if len(result) == 1:
                return f"查询结果：{result[0]}"
            lines = [f"{i}. {row}" for i, row in enumerate(result, 1)]
            return "\n".join(lines)
        # 字典类型结果（单行记录）
        if isinstance(result, dict):
            lines = [f"- {k}: {v}" for k, v in result.items()]
            return "查询结果：\n" + "\n".join(lines)

        # 其他类型直接转字符串
        return str(result)


result_formatter = ResultFormatter()
