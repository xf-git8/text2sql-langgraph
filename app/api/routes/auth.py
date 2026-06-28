# app/api/routes/auth.py
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException
# 从服务层导入唯一的单例对象
from app.api.auth import auth_service

router = APIRouter(prefix="", tags=["认证模块"])


# ==================== 数据模型 (Pydantic) ====================
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str


# ==================== 接口定义 ====================

@router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(req: LoginRequest):
    """
    登录接口
    1. 接收账号密码
    2. 调用 Service 层验证
    3. 成功则签发双 Token
    """
    # 1. 验证身份
    user = auth_service.authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 2. 签发令牌
    access_token = auth_service.create_access_token(
        data={"sub": user["username"], "role": user["role"]}
    )
    refresh_token = auth_service.create_refresh_token(
        data={"sub": user["username"]}
    )

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse, summary="刷新令牌")
async def refresh_token(req: RefreshRequest):
    """
    刷新接口
    使用有效的 Refresh Token 换取新的 Access Token
    """
    # 1. 验证 Refresh Token
    payload = auth_service.verify_refresh_token(req.refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Refresh Token 无效或已过期")

    # 2. 确认用户依然有效
    username = payload["username"]
    user = auth_service.get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    # 3. 签发新令牌（通常也会轮换 Refresh Token 以增加安全性）
    new_access_token = auth_service.create_access_token(
        data={"sub": user["username"], "role": user["role"]}
    )
    new_refresh_token = auth_service.create_refresh_token(
        data={"sub": user["username"]}
    )

    return TokenResponse(access_token=new_access_token, refresh_token=new_refresh_token)