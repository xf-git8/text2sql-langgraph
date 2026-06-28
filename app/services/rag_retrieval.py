import os
import shutil, logging, hashlib
from typing import List, Dict, Any
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from app.core.database import db_manager
from app.services.question_process import question_processor

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RagRetrieval:
    """ Schema Retrieval 类，用于从数据库中检索表结构信息，并生成嵌入向量用于向量数据库存储。"""

    def __init__(self):
        """# 配置嵌入模型"""

        """# 配置嵌入模型"""
        # 将这里的路径替换成你本地模型文件夹的实际路径
        # self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        local_model_path = r"E:\AI_Models_Cache\hub\models--BAAI--bge-large-zh-v1.5\snapshots\79e7739b6ab944e86d6171e44d24c997fc1e0116"
        self.embeddings = HuggingFaceEmbeddings(model_name=local_model_path)
        # 路径配置
        self.schema_db_path = "./schema_chroma_db"
        self.version_file_path = os.path.join(self.schema_db_path, ".version")
        # 注入问题处理器
        self.question_processor = question_processor
        # 初始化
        self.vector_db = None
        self._init_vector_db()

    def _get_schema_version(self) -> str:
        """
       计算当前数据库结构的哈希值，作为版本号。
       用于检测表结构是否发生变化。
        """
        # 获取当前数据库表结构转为字符串计算它的哈希值
        # 1. 获取数据库表结构信息
        schemas = db_manager.get_all_schemas()
        # print(f"DEBUG: schemas = {schemas}, type = {type(schemas)}")  # 临时调试
        # 2. 将表结构信息转为字符串
        schema_str = str(sorted(schemas.items()))
        # 3. 计算字符串的哈希值
        schema_hash = hashlib.sha256(schema_str.encode()).hexdigest()
        return schema_hash

    def _save_version(self, version: str):
        """保存当前版本号到文件"""
        os.makedirs(self.schema_db_path, exist_ok=True)
        with open(self.version_file_path, 'w', encoding='utf-8') as f:
            f.write(version)

    def _load_version(self) -> str:
        """从文件中读取版本号"""
        if os.path.exists(self.version_file_path):
            with open(self.version_file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        return ""

    def _init_vector_db(self):
        """初始化向量数据库"""
        # 获取当前数据库表结构版本号
        current_version = self._get_schema_version()
        saved_version = self._load_version()
        # 调试
        schemas = db_manager.get_all_schemas()
        logger.info(f"🔍 当前读取到的表: {list(schemas.keys())}")
        logger.info(f"🔍 当前Schema哈希: {current_version[:16]}...")
        # 如果向量库不存在，或者版本不匹配（表结构变了），则重建
        if not os.path.exists(self.schema_db_path) or current_version != saved_version:
            logger.info("检测到表结构变更或向量库不存在，正在重建...")
            self._build_vector_db()
            self._save_version(current_version)
        else:
            logger.info("向量数据库已存在且版本匹配，无需重建。")
            # 加载现有的向量数据库
            try:
                self.vector_db = Chroma(
                    persist_directory=self.schema_db_path,
                    embedding_function=self.embeddings,
                )
                logger.info("Schema向量库加载完成 (版本匹配)")
            except Exception as e:
                logger.error(f"加载Schema向量库失败: {e}")
                logger.error(f"加载向量库失败: {e}，尝试重建...")
                self._build_vector_db()
                self._save_version(current_version)

    def _build_vector_db(self):
        """构建向量数据库"""
        schemas = db_manager.get_all_schemas()
        docs = []
        if not schemas:
            logger.warning("数据库中没有表结构信息，无法构建向量数据库。")
            return
        for table_name, schema in schemas.items():
            # 构建文档内容
            columns_info = [f"{col['name']} ({col['type']})" for col in schema["columns"]]
            doc_content = (
                f"表名: {table_name}\n"
                f"字段列表: {', '.join(columns_info)}\n"
                f"用途: 存储与 {table_name.replace('_', ' ')} 相关的数据"
            )
            doc = Document(page_content=doc_content, metadata={"table_name": table_name})
            docs.append(doc)
        if docs:
            # 创建并持久化
            self.vector_db = Chroma.from_documents(
                documents=docs,
                embedding=self.embeddings,
                persist_directory=self.schema_db_path
            )

            logger.info(f"Schema向量库构建完成，共索引 {len(docs)} 张表")

    def _rewrite_question(self, question: str) -> str:
        """
        内部方法：调用问题处理器改写问题
        如果没有配置处理器或处理失败，返回原问题
        """
        if not self.question_processor:
            return question

        try:
            analysis_result =self.question_processor.analyze(question)
            result =self.question_processor.rewrite(question, analysis_result)
            # 假设 rewrite 方法返回的字典中包含 'rewritten' 字段
            # 且状态为 success
            if result.get("status") == "success":
                logger.debug(f"问题改写: '{question}' -> '{result.get('rewritten')}'")
                return result.get("rewritten", question)
        except Exception as e:
            logger.error(f"调用问题改写失败: {e}")
            return question

    def retrieve_relevant_tables(self, question: str, top_k: int = 5) -> List[str]:
        """根据问题检索相关表
        Args:
            question (str): 用户问题
            top_k (int): 返回相关表的数量
        Returns:
            List[str]: 相关表名列表
        """
        if not self.vector_db:
            logger.warning("向量库未初始化")
            return []
        # 检索之前对问题进行改写
        # 1. 先改写问题
        rewritten_question = self._rewrite_question(question)

        try:
            # 2. 使用改写后的问题进行检索
            results = self.vector_db.similarity_search(rewritten_question, k=top_k)
            tables = [doc.metadata.get("table_name") for doc in results if doc.metadata.get("table_name")]
            logger.info(f"检索到相关表: {tables}")
            return tables
        except Exception as e:
            logger.error(f"检索失败: {e}")
            return []

    def format_schemas_for_prompt(self, question: str, top_k: int = 5) -> str:
        """
        将 Schema 格式化为 LLM 可读的字符串
        直接调用修改后的 retrieve_relevant_tables
        """
        schemas = self.get_relevant_schemas(question, top_k)
        if not schemas:
            return "未找到相关的数据库表结构。"

        prompt_parts = []
        for table_name, schema in schemas.items():
            columns = []
            for col in schema["columns"]:
                nullable = "可空" if col.get("nullable", True) else "非空"
                # 增加字段描述（如果有的话）
                col_desc = col.get("comment", "")
                col_info = f"- {col['name']}: {col['type']} ({nullable})"
                if col_desc:
                    col_info += f" // {col_desc}"
                columns.append(col_info)

            table_str = f"""表名: {table_name}
            字段详情:
            {chr(10).join(columns)}"""
            prompt_parts.append(table_str)

        return "\n\n".join(prompt_parts)

    def rebuild_vector_db(self):
        """
        强制重建向量库（供手动调用）
        """
        logger.info("正在强制重建 Schema 向量库...")
        if os.path.exists(self.schema_db_path):
            shutil.rmtree(self.schema_db_path)
        self._build_vector_db()
        self._save_version(self._get_schema_version())

    def get_relevant_schemas(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """获取相关表结构
        Args:
            question (str): 用户问题
            top_k (int): 返回相关表的数量
        Returns:
            Dict[table_name(str), table_struct(Any)]: 相关表结构
        """
        table_names = self.retrieve_relevant_tables(question, top_k)
        schemas = {}
        for table_name in table_names:
            schema = db_manager.get_table_schema(table_name)
            if schema:
                schemas[table_name] = schema
        return schemas

rag_retrieval = RagRetrieval()
