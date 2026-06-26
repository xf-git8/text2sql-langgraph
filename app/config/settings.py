# 配置管理类
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # project description
    PROJECT_NAME = "LangGranph Text-to-SQL Agent"
    PROJECT_VERSION = "1.0.0"
    DESCRIPTION = "基于LangGraph构建的生产级Text-to-SQL服务"

    # database
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    # 指数退避（Exponential Backoff）重试策略配置参数，常自动重试机制
    # 最大重试次数
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
    # wait time 重试等待时间
    INITIAL_DELAY = float(os.getenv("INITIAL_DELAY", 1.0))
    BACKOFF_FACTOR = float(os.getenv("BACKOFF_FACTOR", 2.0))

    # LLM | API_KEY
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

settings = Settings()
