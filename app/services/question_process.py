import logging
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from typing import List, Literal, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pydantic结构化输出模型
class QuestionAnalysis(BaseModel):
    """问题分析的结构化结果"""
    intention: Literal["data_query", "data_analysis", "schema_query", "invalid"] = Field(
        ..., description="问题意图分类")
    needs_rewrite: bool = Field(..., description="是否需要重写")
    enties: List[str] = Field(..., description="实体列表,不确定可以为空")
    keywords: List[str] = Field(..., description="关键词列表,不确定可以为空")
    confidence: float = Field(..., description="置信度")
    reason: str = Field(..., description="分析思路原因")


class QuestionRewrite(BaseModel):
    """问题改写的结构化结果"""
    rewritten_question: str = Field(..., description="重写的问题")
    explanation: str = Field(description="改写理由，如补充了时间范围或明确了实体")


class QuestionProcessor:
    """用户问题处理类"""

    def __init__(self):
        # 初始化 LLM
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0  # 分析任务需要确定性输出
        )
        # 初始化 Parser 分析解析
        self.analysis_parser = PydanticOutputParser(pydantic_object=QuestionAnalysis)
        self.rewrite_parser = PydanticOutputParser(pydantic_object=QuestionRewrite)
        # --- 分析 Prompt ---
        self.analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个资深的数据分析助手。请分析用户的问题并输出结构化结果。

        意图分类标准：
        1. data_query: 明确的数据查询（如"查一下销售额"、"用户列表"）。
        2. data_analysis: 涉及统计、对比、趋势、聚合（如"哪个产品卖得最好"、"月度趋势"）。
        3. schema_request: 询问数据库结构、字段含义、建表语句（如"用户表有哪些字段"）。
        4. invalid: 闲聊、辱骂、与数据无关的内容。

        分析规则：
        - 如果用户未指定时间，通常默认为"最近"或"所有时间"，needs_rewrite 设为 false。
        - 如果用户指代不明（如"它"、"那个"），needs_rewrite 设为 true。
        - 提取 entities 时，尝试匹配常见的业务表名（如 user, order, product）。"""),
            ("human", """用户问题：{question}

        {format_instructions}""")
        ])

        # --- 改写 Prompt ---
        self.rewrite_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个问题改写专家。请根据分析结果，将用户的自然语言问题改写为精确的查询语句。

        改写原则：
        1. 明确实体：将"用户"改为"用户表"，"订单"改为"订单表"。
        2. 明确时间：如果原问题模糊，根据上下文补充（如"今年"、"上个月"），若无上下文则保持原意。
        3. 消除歧义：将代词替换为具体名词。
        4. 保持原意：不要改变用户的查询目的。"""),
            ("human", """原始问题：{question}
        分析结果：{analysis_result}

        请输出改写结果：
        {format_instructions}""")
        ])
        # 构建链
        self.analysis_chain = self.analysis_prompt | self.llm | self.analysis_parser
        self.rewrite_chain = self.rewrite_prompt | self.llm | self.rewrite_parser

    def analyze(self, question: str) -> QuestionAnalysis:
        """分析问题意图"""
        try:
            result = self.analysis_chain.invoke({
                "question": question,
                "format_instructions": self.analysis_parser.get_format_instructions()
            })
            logger.info(f"问题分析成功: {result.intention} (置信度: {result.confidence})")
            return result
        except Exception as e:
            logger.error(f"问题分析失败: {e}")
            # 失败降级策略：默认为查询，并标记需要改写
            return QuestionAnalysis(
                intention="data_query",
                needs_rewrite=True,
                entities=[],
                keywords=[],
                confidence=0.0,
                reasoning=f"解析错误: {str(e)}"
            )
    def rewrite(self, question: str, analysis_result: QuestionAnalysis) -> QuestionRewrite:
        """分析 -> (可选)改写返回统一的字典格式供后续流程使用
        Args:
            question (str): 用户问题
            analysis_result (QuestionAnalysis): 问题分析结果
        Returns:
            QuestionRewrite: 问题改写结果
        """
        try:
            # 分析
            analysis = self.analyze(question)
            # 2. 处理无效或无需改写的情况
            if analysis.intention == "invalid":
                return {
                    "status": "error",
                    "message": "抱歉，我只能回答与数据相关的问题。",
                    "original": question,
                    "intention": "invalid"
                }
            if not analysis.needs_rewrite:
                return {
                    "status": "success",
                    "original": question,
                    "rewritten": question,
                    "intention": analysis.intention,
                    "entities": analysis.entities,
                    "keywords": analysis.keywords,
                    "rewrite_reason": "原问题已足够清晰"
                }
            # 3. 改写
            rewrite_result = self.rewrite_chain.invoke({
                "question": question,
                "analysis_result": analysis.json(),
                "format_instructions": self.rewrite_parser.get_format_instructions()
            })
            logger.info(f"问题改写成功: {rewrite_result.rewritten_question}")
            return {
                "status": "success",
                "original": question,
                "rewritten": rewrite_result.rewritten_question,
                "intention": analysis.intention,
                "entities": analysis.entities,
                "keywords": analysis.keywords,
                "rewrite_reason": rewrite_result.explanation
            }
        except Exception as e:
            logger.error(f"问题改写失败: {e}")
            return {
                "status": "error",
                "message": "抱歉，我无法理解您的问题。",
                "original": question,
                "intention": analysis.intention
                }
# 全局单例
question_processor = QuestionProcessor()