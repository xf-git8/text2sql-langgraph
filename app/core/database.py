import logging, time
from sqlalchemy.engine import Engine, Result
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError

# 引入配置类
from app.config.settings import settings

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.engine: Optional[Engine] = None
        self._connect()

    def _connect(self) -> None:
        """建立数据库连接，包括指数退避重试机制"""
        retry_count = 0
        max_retries = settings.MAX_RETRIES
        delay = settings.DELAY
        # 从 settings 中获取数据库连接 URL，避免在多处拼接
        db_url = settings.DB_URL
        while retry_count < max_retries:
            try:
                # 启用连接池，并设置预 ping，在从连接池获取连接时自动检查连接有效性
                self.engine = create_engine(
                    db_url,
                    echo=False,
                    pool_pre_ping=True,
                    # connect_args 根据具体数据库驱动调整，这里保留原逻辑
                    connect_args={"ssl": {"ssl_mode": "DISABLED"}} if "mysql" in db_url else {}
                )
                # 使用 engine.connect() 测试连接，with 语句会确保连接被正确关闭
                with self.engine.connect() as conn:
                    pass
                logger.info("数据库连接成功")
                return
                # 捕获连接错误
            except Exception as e:
                retry_count += 1
                logger.error(f"数据库连接失败 (尝试 {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    time.sleep(delay)
                else:
                    logger.critical("数据库连接失败，已达到最大重试次数")
                    raise Exception("数据库连接失败，已达到最大重试次数") from e

    def reconnect(self) -> None:
        """
        尝试重新连接数据库。
        """
        logger.info("尝试重新连接数据库")
        self.engine = None
        self._connect()

    def get_table_names(self) -> List[str]:
        """获取数据库中的所有表名"""
        if not self.engine:
            self.reconnect()
        try:
            inspector = inspect(self.engine)
            return inspector.get_table_names()
        except Exception as e:
            logger.error(f"获取表名失败: {e}")
            return []

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """获取指定表的 schema 表结构信息"""
        if not self.engine:
            self.reconnect()
        try:
            inspector = inspect(self.engine)
            columns = inspector.get_columns(table_name)
            schema = {"table_name": table_name, "columns": []}
            for column in columns:
                schema["columns"].append({
                    "name": column["name"],
                    "type": column["type"],
                    "nullable": column["nullable"]
                })
            return schema
        except Exception as e:
            logger.error(f"获取表结构失败: {e}")
            return {}

    def get_all_schemas(self) -> Dict[str:Dict[str, Any]]:
        """获取数据库中所有表的 schema 信息"""
        if not self.engine:
            self.reconnect()
            try:
                tables = self.get_table_names()
                schemas = {}
                for table in tables:
                    schemas[table] = self.get_table_schema(table)
                return schemas
            except Exception as e:
                logger.error(f"获取所有表结构失败: {e}")
                return {}

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Result:
        """执行 SQL 语句。
       Args:
           sql (str): 要执行的 SQL 语句。
           params (dict, optional): SQL 语句的参数，用于防止 SQL 注入。
       Returns:
           tuple: 一个包含两个元素的元组。
               - 第一个元素是查询结果，格式为字典列表。
               - 第二个元素是错误信息，如果执行成功则为 None。
       """
        if not self.engine:
            try:
                self.reconnect()
            except Exception as e:
                logger.error(f"重新连接数据库失败: {e}")
                return [], f"重新连接数据库失败: {e}"
            try:
                # 使用 text() 包装 SQL 语句以支持参数化查询
                statement = text(query)
                with self.engine.connect() as conn:
                    result = conn.execute(statement, params)
                # 对于 SELECT 等查询语句，需要 commit 才能在某些隔离级别下看到结果（虽然通常不需要）
                # 对于 INSERT/UPDATE/DELETE，必须 commit 才会生效
                # 这里统一 commit，对于只读连接或自动提交配置可能不适用，但作为通用方法比较稳妥
                conn.commit()
                # 只有当 result 有返回行时才尝试获取 keys 和 rows
                if result.returns_rows:
                    columns = result.keys()
                    rows = result.fetchall()
                    return [dict(zip(columns, row)) for row in rows], None
                else:
                    # 对于没有返回行的语句（如 INSERT, UPDATE），返回受影响的行数
                    return [{"rowcount": result.rowcount}], None
            except DisconnectionError:
                # 捕获连接断开异常，尝试重连后再次执行
                logger.warning("检测到数据库连接断开，正在尝试重连...")
                try:
                    self.reconnect()
                    return self.execute_query(query, params)
                except Exception as e:
                    logger.error(f"重连后执行 SQL 仍然失败: {e}")
                    return [], f"数据库连接异常: {e}"
                except SQLAlchemyError as e:
                    logger.error(f"SQL执行错误: {e}")
                    return [], str(e)
                except Exception as e:
                    logger.error(f"SQL执行异常: {e}")
                    return [], str(e)


db_manager = DatabaseManager()
