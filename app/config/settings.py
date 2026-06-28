# 配置管理类
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # ==================== 项目基础信息 ====================
    PROJECT_NAME: str = "LangGraph Text-to-SQL Agent"
    PROJECT_VERSION: str = "1.0.0"
    DESCRIPTION: str = "基于 LangGraph 的自然语言转 SQL 查询服务"

    # ==================== JWT 认证配置 ====================
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default-secret-key")
    REFRESH_SECRET_KEY: str = os.getenv("REFRESH_SECRET_KEY", "default-refresh-key")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # ==================== 数据库配置 ====================
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_NAME: str = os.getenv("DB_NAME", "text2sql_langgraph")
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # ==================== 重试策略配置 ====================
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    INITIAL_DELAY: float = float(os.getenv("INITIAL_DELAY", "1.0"))
    BACKOFF_FACTOR: float = float(os.getenv("BACKOFF_FACTOR", "2.0"))

    # ==================== LLM 配置 ====================
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    @property
    def DB_URL(self) -> str:
        """动态拼接数据库连接字符串（不作为 Pydantic 字段）"""
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()