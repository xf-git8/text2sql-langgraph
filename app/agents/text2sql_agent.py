import logging
import re
from typing import TypedDict, Optional, List, Dict, Literal

from langgraph.graph import StateGraph, START, END

# 从自定义模块中导入业务逻辑服务
from app.services import (
    rag_retrieval,
    sql_generator,
    sql_validator,
    question_processor,
    result_formatter,
)
from app.core.database import db_manager

# --- 配置日志 ---
# 设置日志级别为 INFO，这样可以看到程序运行过程中的关键信息
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_llm_sql(raw_sql: str) -> str:
    """清除 LLM 输出中的 Markdown 代码块标记和多余空白"""
    if not raw_sql:
        return ""

    s = raw_sql.strip()

    # 统一移除开头和结尾的 ``` 代码块（兼容 sql/SQL/mysql 等语言标识）
    # 开头：```sql\n 或 ```\n
    s = re.sub(r'^```\w*\s*\n?', '', s, count=1)
    # 结尾：\n``` 或 \n\n``` 或直接 ```
    s = re.sub(r'\s*```\s*$', '', s, count=1)

    # 移除首尾分号和空白
    s = s.strip().rstrip(';').strip()

    return s


# AgentState 定义了整个工作流中共享的数据结构（状态）
# 每个节点都可以读取和更新这个状态
class AgentState(TypedDict):
    question: str              # 用户的原始问题
    processed_question: str    # 处理后的用户问题
    intention: str             # 用户问题的意图
    relevant_tables: List[str] # 与问题相关的表
    schema_context: str        # 相关表的数据库 Schema 上下文信息
    generated_sql: Optional[str]          # 生成 SQL 查询语句
    validation_result: Dict[str, any]     # SQL 查询的验证结果
    execution_result: List[Dict]          # SQL 查询的执行结果
    execution_error: Optional[str]        # SQL 查询执行过程中的错误信息
    answer: str                # 最终生成的答案
    retry_count: int           # 重试次数
    max_retries: int           # 最大重试次数


# --- 定义节点函数 ---


def process_question_node(state: AgentState) -> AgentState:
    """
    节点1：处理用户问题
    功能：分析用户意图，并检索相关的数据库表结构信息。
    """
    # 调用服务来处理问题，返回重写后的问题、意图和相关表结构
    logger.info(f"处理问题: {state['question']}")
    # 进行处理后问题
    question = state['question']
    re_question = question_processor.rewrite(question, question_processor.analyze(question))
    print(type(re_question))
    print(re_question)
    if re_question["intention"] == "invalid":
        # 如果意图是无效的，则直接返回错误信息
        return {
            **state,
            "processed_question": re_question["rewritten"],
            "intention": "invalid",
            "answer": "抱歉，我无法回答这个问题。请提出与数据库查询相关的问题。",
            "relevant_tables": [],
            "schema_context": "",
        }
    # 检索库表结构
    tables = rag_retrieval.retrieve_relevant_tables(question)
    state['relevant_tables'] = tables
    # 获取数据库 Schema 上下文信息 {key value}
    schema_context = rag_retrieval.get_relevant_schemas(question)
    state['schema_context'] = schema_context

    # 如果问题改写，检索表结构然后 更新状态 传给下个节点
    if re_question["intention"] == "rewrite":
        return {
            **state,
            "processed_question": re_question["rewritten"],
            "intention": re_question["intention"],
            "relevant_tables": tables,
            "schema_context": schema_context,
        }
    else:
        return {
            **state,
            "processed_question": question,
            "intention": re_question["intention"],
            "relevant_tables": tables,
            "schema_context": schema_context,
        }


def generate_sql_node(state: AgentState) -> AgentState:
    """
    节点2：生成 SQL 查询
    功能：根据用户问题和相关表结构生成 SQL 查询语句。
    """
    # 如果问题无效，直接跳过该节点
    if state["intention"] == "invalid":
        return state

    logger.info(f"生成SQL: {state['processed_question']}")
    # 调用服务来生成 SQL 查询语句
    raw_sql = sql_generator.generate_sql(state['processed_question'], state['schema_context'])
    print(raw_sql)

    #  在源头清洗 LLM 输出的 Markdown 标记，确保下游所有节点拿到纯净 SQL
    cleaned_sql = clean_llm_sql(raw_sql)
    logger.info(f"生成并清洗后SQL: {cleaned_sql}")

    return {
        **state,
        "generated_sql": cleaned_sql,
    }


def validate_sql_node(state: AgentState) -> AgentState:
    """
    节点3：校验 SQL
    功能：对生成的 SQL 语句进行语法和逻辑校验。
    """
    # 如果问题无效，直接跳过该节点
    if state["intention"] == "invalid":
        return state

    #  使用已在 generate_sql_node 中清洗过的 SQL
    sql = state['generated_sql']
    logger.info(f"校验SQL: {sql}")

    # 如果没有生成 SQL，直接返回失败结果
    if not sql:
        return {
            **state,
            "validation_result": {"valid": False, "errors": ["SQL生成失败，无SQL可校验"]},
        }

    # 调用服务来校验 SQL 语句
    try:
        validation_result = sql_validator.validate(sql)
    except Exception as e:
        logger.error(f"SQL验证服务调用异常: {e}", exc_info=True)
        validation_result = None

    logger.warning(f"DEBUG validation_result 原始值: {repr(validation_result)}")

    # 防御性处理：validate 返回 None 或非法类型时，标记为失败
    if not isinstance(validation_result, dict):
        logger.warning(f"SQL验证返回非字典结果({type(validation_result)})，标记为验证失败")
        return {
            **state,
            "validation_result": {
                "valid": False,
                "errors": [f"SQL验证服务返回无效结果: {repr(validation_result)}"],
            },
        }

    valid = validation_result.get('valid', False)
    errors = validation_result.get('errors', [])
    return {
        **state,
        "validation_result": {"valid": valid, "errors": errors},
    }


def execute_sql_node(state: AgentState) -> AgentState:
    """节点4：执行 SQL"""
    if state["intention"] == "invalid":
        return state

    if not state.get("validation_result", {}).get("valid"):
        errors = state.get("validation_result", {}).get("errors", ["未知校验错误"])
        return {**state, "answer": f"SQL校验失败: {', '.join(errors)}"}

    sql = state["generated_sql"]
    logger.info(f"执行SQL: {sql}")

    # 防止 execute_query 返回 None 或非元组
    try:
        exec_result = db_manager.execute_query(sql)
    except Exception as e:
        logger.error(f"execute_query 调用本身抛出异常: {e}", exc_info=True)
        exec_result = None

    # 严格校验返回值格式
    if exec_result is None or not isinstance(exec_result, (tuple, list)) or len(exec_result) != 2:
        logger.error(f"execute_query 返回异常值: {repr(exec_result)}, 类型: {type(exec_result)}")
        result, error = [], f"数据库执行模块返回异常结果: {repr(exec_result)}"
    else:
        result, error = exec_result

    return {
        **state,
        "execution_result": result,
        "execution_error": error,
    }


def summarize_node(state: AgentState) -> AgentState:
    """
    节点5：总结答案
    功能：将 SQL 执行结果格式化为自然语言，作为最终答案。
    """
    if state["intention"] == "invalid":
        return state

    # 如果 SQL 执行出错，返回错误信息
    if state["execution_error"]:
        return {
            **state,
            "answer": f"SQL执行失败: {state['execution_error']}",
        }

    # ✅ 如果校验失败（由条件边路由至此），直接返回校验错误
    if not state.get("validation_result", {}).get("valid"):
        errors = state.get("validation_result", {}).get("errors", ["未知校验错误"])
        return {
            **state,
            "answer": f"SQL校验失败: {', '.join(errors)}",
        }

    print(state["execution_result"])
    # 调用服务将查询结果格式化为易读的文本
    answer = result_formatter.format(
        question=state["question"],
        sql=state["generated_sql"],
        result=state["execution_result"],
    )
    return {
        **state,
        "answer": answer,
    }


def retry_correction_node(state: AgentState) -> AgentState:
    """失败重试尝试修正节点"""

    if state["intention"] == "invalid":
        return state

    if not state["execution_error"]:
        return state

    error = state["execution_error"]
    sql = state["generated_sql"]

    logger.info(f"修正SQL，错误: {error}")
    corrected_sql = sql_generator.correct_sql(sql, error, state["schema_context"])

    # ✅ 修正后的 SQL 同样需要清洗
    cleaned_corrected_sql = clean_llm_sql(corrected_sql)
    logger.info(f"修正并清洗后SQL: {cleaned_corrected_sql}")

    return {
        **state,
        "generated_sql": cleaned_corrected_sql,
        "retry_count": state["retry_count"] + 1,
        "execution_error": None,
    }


# --- 条件路由函数 ---


def should_execute(state: AgentState) -> Literal["execute", "summarize"]:
    """校验通过则执行，否则直接进入总结节点输出错误信息"""
    if state.get("validation_result", {}).get("valid"):
        return "execute"
    return "summarize"


def should_retry(state: AgentState) -> Literal["retry", "end"]:
    """判断是否需要重试"""
    if state["intention"] == "invalid":
        return "end"
    # 如果执行出错且未达到最大重试次数，则返回 "retry"
    if state["execution_error"] and state["retry_count"] < state["max_retries"]:
        return "retry"
    # 其他情况（成功或重试次数用尽）都结束
    return "end"


# --- 工作流创建函数 ---


def create_text2sql_graph():
    """创建工作流agent"""
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("process_question_node", process_question_node)
    workflow.add_node("generate_sql_node", generate_sql_node)
    workflow.add_node("validate_sql_node", validate_sql_node)
    workflow.add_node("execute_sql_node", execute_sql_node)
    workflow.add_node("summarize_node", summarize_node)
    workflow.add_node("retry_correction_node", retry_correction_node)

    # 添加边
    workflow.add_edge(START, "process_question_node")
    workflow.add_edge("process_question_node", "generate_sql_node")
    workflow.add_edge("generate_sql_node", "validate_sql_node")

    # ✅ 校验通过后执行，校验失败直接进入总结节点报错（不再硬连线到 execute）
    workflow.add_conditional_edges(
        "validate_sql_node",
        should_execute,
        {
            "execute": "execute_sql_node",
            "summarize": "summarize_node",
        },
    )

    # 添加条件边：从 execute_sql_node 指向 retry_correction_node
    workflow.add_edge("execute_sql_node", "retry_correction_node")

    # 添加条件边：从 retry_correction_node 根据 should_retry 的结果决定下一步
    workflow.add_conditional_edges(
        "retry_correction_node",
        should_retry,
        {
            "retry": "validate_sql_node",
            "end": "summarize_node",
        },
    )
    workflow.add_edge("summarize_node", END)

    # 编译图
    return workflow.compile()


text2sql_graph = create_text2sql_graph()