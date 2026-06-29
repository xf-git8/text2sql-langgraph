import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config.settings import settings

logger = logging.getLogger(__name__)

# ==================== 全局工具 ====================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """
    认证服务核心类
    职责：处理所有与身份验证相关的纯业务逻辑，不依赖 FastAPI 的 Request/Response 对象。
    """

    def __init__(self):
        # 1. 初始化配置
        self.secret_key = settings.SECRET_KEY
        self.refresh_secret_key = settings.REFRESH_SECRET_KEY
        self.algorithm = settings.ALGORITHM or "HS256"
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES or 30
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS or 7

        # 2. 模拟数据库（生产环境请替换为 SQLAlchemy/Tortoise 等数据库查询）
        # 注意：这里只存数据，不做任何 HTTP 相关的判断
        self._users_db: Dict[str, Dict[str, Any]] = {
            "admin": {
                "username": "admin",
                "hashed_password": pwd_context.hash("admin123"),
                "role": "admin",
                "disabled": False,
            },
            "user": {
                "username": "user",
                "hashed_password": pwd_context.hash("user123"),
                "role": "user",
                "disabled": False,
            }
        }


    # ==================== 密码处理 ====================

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证明文密码是否与哈希值匹配"""
        return pwd_context.verify(plain_password, hashed_password)

    def hash_password(self, password: str) -> str:
        """将明文密码转换为哈希值（用于注册或重置密码）"""
        return pwd_context.hash(password)

    # ==================== 用户查询 ====================

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """根据用户名获取用户信息"""
        user = self._users_db.get(username)
        if user and not user.get("disabled"):
            return user
        return None

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """
        完整认证流程：查用户 -> 验密码
        返回：脱敏后的用户字典（不含密码），失败返回 None
        """
        user = self.get_user_by_username(username)
        if not user:
            return None
        if not self.verify_password(password, user["hashed_password"]):
            return None

        # 返回安全数据
        return {"username": user["username"], "role": user["role"]}

    # ==================== Token 签发 ====================

    def _create_token(self, data: dict, secret: str, expires_delta: timedelta) -> str:
        """内部通用方法：生成 JWT"""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, secret, algorithm=self.algorithm)

    def create_access_token(self, data: dict) -> str:
        """签发短期 Access Token"""
        expires = timedelta(minutes=self.access_token_expire_minutes)
        return self._create_token(data, self.secret_key, expires)

    def create_refresh_token(self, data: dict) -> str:
        """签发长期 Refresh Token"""
        expires = timedelta(days=self.refresh_token_expire_days)
        return self._create_token(data, self.refresh_secret_key, expires)

    # ==================== Token 校验 ====================

    def _decode_token(self, token: str, secret: str) -> Optional[Dict]:
        """内部通用方法：解码 JWT"""
        try:
            payload = jwt.decode(token, secret, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.debug(f"Token 解码失败: {e}")
            return None

    def get_current_user(self, token: str) -> Optional[Dict]:
        """
        解析 Access Token 并获取当前用户
        供 Depends(get_current_user) 调用
        """
        payload = self._decode_token(token, self.secret_key)
        if payload is None:
            return None

        username: str = payload.get("sub")
        if not username:
            return None

        user = self.get_user_by_username(username)
        if not user:
            return None

        return {"username": user["username"], "role": payload.get("role", user["role"])}

    def verify_refresh_token(self, token: str) -> Optional[Dict]:
        """校验 Refresh Token 有效性"""
        payload = self._decode_token(token, self.refresh_secret_key)
        if payload is None:
            return None

        username = payload.get("sub")
        if not username:
            return None

        return {"username": username}


# 单例模式：整个应用共享这一个实例，避免重复初始化
auth_service = AuthService()

