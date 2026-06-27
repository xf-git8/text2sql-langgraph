import logging
from jose import jwt, JWTError
from typing import Dict, Any, Optional
from passlib.context import CryptContext
from datetime import timedelta, datetime, timezone

from app.config.settings import settings

# ==================== 基础配置 ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SECRET_KEY = getattr(settings, "JWT_SECRET_KEY", None) or getattr(settings, "SECRET_KEY", None)
if not SECRET_KEY:
    raise ValueError("未配置 JWT_SECRET_KEY 或 SECRET_KEY！")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # Access Token 过期时长（分钟）
REFRESH_TOKEN_EXPIRE_DAYS = 7  # Refresh Token 过期天数

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 模拟用户数据库（生产环境应替换为真实数据库查询）
users_db: Dict[str, Dict[str, Any]] = {
    "admin": {
        "username": "admin",
        "hashed_password": pwd_context.hash("admin123"),
        "role": "admin"
    },
    "user": {
        "username": "user",
        "hashed_password": pwd_context.hash("user123"),
        "role": "user"
    }
}


class AuthService:
    """认证服务：封装密码验证、Token 签发与解析等核心认证逻辑"""

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证明文密码是否与哈希密码匹配"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """生成密码的 bcrypt 哈希值"""
        return pwd_context.hash(password)

    @staticmethod
    def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
        """验证用户名和密码
        return: 验证成功返回用户字典（不含密码），失败返回 None
        """
        user = users_db.get(username)
        if not user:
            logger.warning(f"登录失败：用户 '{username}' 不存在")
            return None
        if not AuthService.verify_password(password, user["hashed_password"]):
            logger.warning(f"登录失败：用户 '{username}' 密码错误")
            return None
        logger.info(f"用户 '{username}' 认证成功")
        return user

    # 根据用户名获取用户信息（供 /refresh 接口使用）
    @staticmethod
    def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
        """
        根据用户名查询用户信息
        :param username: 用户名
        :return: 用户字典或 None
        """
        return users_db.get(username)

    @staticmethod
    def create_access_token(
            data: dict,
            expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        创建 JWT Access Token
        :param data:          要编码到 Token 中的载荷（必须包含 sub=用户名）
        :param expires_delta: 自定义过期时长，为空则使用默认 ACCESS_TOKEN_EXPIRE_MINUTES
        :return:              编码后的 JWT 字符串
        """
        to_encode = data.copy()
        now = datetime.now(timezone.utc)
        expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire, "type": "access"})  # ✅ 添加 type 字段区分 Token 类型
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        logger.debug(f"Access Token 已签发，过期时间: {expire.isoformat()}")
        return encoded_jwt

    # 创建 Refresh Token
    @staticmethod
    def create_refresh_token(
            data: dict,
            expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        创建 JWT Refresh Token（仅包含用户名，不含角色等敏感信息）
        :param data:          载荷（仅需包含 sub=用户名）
        :param expires_delta: 自定义过期时长，为空则使用默认 REFRESH_TOKEN_EXPIRE_DAYS
        :return:              编码后的 JWT 字符串
        """
        to_encode = data.copy()
        now = datetime.now(timezone.utc)
        expire = now + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
        to_encode.update({"exp": expire, "type": "refresh"})  # ✅ 标记为 refresh 类型
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        logger.debug(f"Refresh Token 已签发，过期时间: {expire.isoformat()}")
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, str]]:
        """
        解码并验证 JWT Token
        :return: 有效时返回 {"username": ..., "role": ..., "type": ...}，无效时返回 None
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: Optional[str] = payload.get("sub")
            if username is None:
                logger.warning("Token 解码失败：payload 中缺少 'sub' 字段")
                return None
            return {
                "username": username,
                "role": payload.get("role", "user"),
                "type": payload.get("type", "access")  #Token 类型
            }
        except JWTError as e:
            logger.warning(f"Token 解码失败: {e}")
            return None

    # 验证 Refresh Token
    @staticmethod
    def verify_refresh_token(token: str) -> Optional[Dict[str, str]]:
        """
        验证 Refresh Token 的有效性
        :param token: Refresh Token 字符串
        :return: 有效时返回 {"username": ...}，无效/过期/类型错误时返回 None
        """
        user_data = AuthService.decode_token(token)
        if user_data is None:
            return None
        # 确保传入的是 Refresh Token 而非 Access Token
        if user_data.get("type") != "refresh":
            logger.warning("Token 类型错误：期望 refresh，实际为 access")
            return None
        return {"username": user_data["username"]}

    @staticmethod
    def get_current_user(token: str) -> Dict[str, Any]:
        """
        根据 Access Token 获取当前用户信息（供 FastAPI Depends 注入使用）
        :param token: Access Token 字符串（不是用户名！）
        :raises Exception: Token 无效或用户不存在时抛出异常
        """
        credentials_exception = Exception("Could not validate credentials")

        user_data = AuthService.decode_token(token)
        if user_data is None:
            raise credentials_exception

        # 确保是 Access Token
        if user_data.get("type") != "access":
            raise credentials_exception

        user = users_db.get(user_data["username"])
        if user is None:
            raise credentials_exception

        return user


auth_service = AuthService()