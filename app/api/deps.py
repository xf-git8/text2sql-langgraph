from fastapi import Request
from fastapi import HTTPException
from app.services import auth_service

async def get_current_user(request: Request) -> dict:
    """
    FastAPI 依赖注入函数：从请求头中提取 Token 并验证用户身份
    用法：current_user: dict = Depends(get_current_user)
    """
    # 1. 从 Authorization 头中提取 Bearer Token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供有效的认证令牌")

    token = auth_header.split("Bearer ")[1].strip()

    # 2. 调用 AuthService 的方法验证 Token
    user = auth_service.get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    return user