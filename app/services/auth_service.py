import logging
from jose import jwt, JWTError
from typing import Dict, Any, Optional
from passlib.context import CryptContext
from datetime import timedelta, datetime, timezone



from app.config.settings import settings

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SECRET_KEY = getattr(settings, "JWT_SECRET_KEY", None) or getattr(settings, "SECRET_KEY", None)
if not SECRET_KEY:
    raise ValueError(
        " 未配置 JWT_SECRET_KEY 或 SECRET_KEY！"
    )

ALGORITHM = "HS256"                # JWT 签名算法
ACCESS_TOKEN_EXPIRE_MINUTES = 30   # Access Token 默认过期时间（分钟）
# 密码哈希上下文，使用 bcrypt 算法
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# 模拟用户
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
        """
        验证用户名和密码
        :return: 验证成功返回用户字典，失败返回 None
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

    @staticmethod
    def create_access_token(
            data: dict,
            expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        创建 JWT Access Token
        :param data:          要编码到 Token 中的载荷（建议包含 sub=用户名）
        :param expires_delta: 自定义过期时长，为空则使用默认 ACCESS_TOKEN_EXPIRE_MINUTES
        :return:              编码后的 JWT 字符串
        """
        to_encode = data.copy()
        now = datetime.now(timezone.utc)
        expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        logger.debug(f"Token 已签发，过期时间: {expire.isoformat()}")
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, str]]:
        """
        解码并验证 JWT Token
        :return: 有效时返回 {"username": ..., "role": ...}，无效时返回 None
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: Optional[str] = payload.get("sub")
            if username is None:
                logger.warning("Token 解码失败：payload 中缺少 'sub' 字段")
                return None
            return {
                "username": username,
                "role": payload.get("role", "user")  # 兜底默认角色
            }
        except JWTError as e:
            logger.warning(f"Token 解码失败: {e}")
            return None

    @staticmethod
    def get_current_user(token: str) -> Dict[str, Any]:
        """
        根据 Token 获取当前用户信息（供 FastAPI Depends 注入使用）
        :raises Exception: Token 无效或用户不存在时抛出异常
        """
        credentials_exception = Exception("Could not validate credentials")

        user_data = AuthService.decode_token(token)
        if user_data is None:
            raise credentials_exception

        user = users_db.get(user_data["username"])
        if user is None:
            raise credentials_exception

        return user

auth_service = AuthService()
