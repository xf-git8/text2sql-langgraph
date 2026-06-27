import logging
from typing import Optional

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.config.settings import settings

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 根据用户问题和检索数据表结构生成sql
class SQLGenerator:
    """生成 sql和修正类"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0,
            timeout=30,  # 设置超时时间，防止网络卡顿
        )
        # 定义生成 SQL 的提示词
        self.generate_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的SQL生成助手。请根据用户的问题和提供的数据库表结构，生成正确的SQL查询语句。

        规则：
        1. 只生成SQL语句，不包含任何解释或额外文本
        2. SQL必须是有效的MySQL语法
        3. 不要使用DROP、DELETE、UPDATE等危险操作
        4. 必须使用提供的表结构中的字段名
        5. 如果需要模糊查询，请使用LIKE语句
        6. 只返回SELECT语句"""),
            ("human", """数据库表结构：
        {schema_context}
        用户问题：{question}
        请生成SQL查询语句：""")
        ])
        # 定义修正 SQL 的提示词
        self.correct_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个SQL纠错专家。请根据错误信息修正SQL语句。
        规则：
        1. 只返回修正后的SQL语句
        2. 保持原有的查询逻辑不变
        3. 修复语法错误或执行错误"""),
            ("human", """原始SQL：{sql}
        错误信息：{error}
        数据库表结构：
        {schema_context}
        请修正SQL：""")
        ])
        # 组装调用链
        self.generate_chain = self.generate_prompt | self.llm
        self.correct_chain = self.correct_prompt | self.llm


def generate_sql(self, question: str, schema_context: str) -> Optional[str]:
    """根据用户问题和表结构生成 SQL。
    Args:
        question (str): 用户问题
        schema_context (str): 数据库表结构
    Returns: 生成的 SQL 语句，如果失败返回 None
    """
    try:
        response = self.generate_chain.invoke(
            {"question": question, "schema_context": schema_context})
        # 确保 response 是 AIMessage 类型再取 content
        if isinstance(response, AIMessage):
            logger.info(f"生成sql:{response.content}")
            return response.content.strip()
        else:
            logger.error(f"生成sql失败，返回类型错误：{type(response)}")
            return str(response)
    except Exception as e:
        logger.error(f"生成sql失败：{e}")
        return None


def correct_sql(self, original_sql: str, error: str, schema_context: str) -> Optional[str]:
    """根据错误信息修正 SQL。
    Args:
        sql (str): 原始 SQL 语句
        error (str): 错误信息
        schema_context (str): 数据库表结构
    Returns: 修正后的 SQL 语句，如果失败返回 None
        """
    try:
        response = self.correct_chain.invoke(
            {"sql": original_sql, "error": error, "schema_context": schema_context})
        # 确保 response 是 AIMessage 类型再取 content
        if isinstance(response, AIMessage):
            logger.info(f"修正sql:{response.content}")
            return response.content.strip()
        else:
            logger.error(f"修正sql失败，返回类型错误：{type(response)}")
            return str(response)
    except Exception as e:
        # 修正失败时，返回原始 SQL 让调用者决定如何处理（比如直接报错/转人工/）
        logger.error(f"修正sql失败：{e}")
        return original_sql


sql_generator = SQLGenerator()
