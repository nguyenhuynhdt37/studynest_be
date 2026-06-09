from fastapi import APIRouter, Body, Depends, Response, status, Request, Cookie, Query
from typing import Optional

from app.core.deps import AuthorizationService
from app.core.ws_manager import ws_manager
from app.schemas.auth.user import (
    GoogleLogin,
    LoginUser,
    RefreshEmail,
    SendOtp,
    UserCreate,
    VerifyEmail,
    VerifyOtp,
)
from app.services.shares.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", status_code=200)
async def login(
    req: Request,
    res: Response,
    schema: LoginUser = Body(),
    auth_service: AuthService = Depends(AuthService),
):
    user_agent = req.headers.get("user-agent")
    ip = req.client.host if req.client else None
    return await auth_service.login_async(schema, res, user_agent=user_agent, ip=ip)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    schema: UserCreate = Body(),
    auth_service: AuthService = Depends(AuthService),
):
    return await auth_service.register_async(schema)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    res: Response,
    session_id: str | None = Query(None),
    auth_service: AuthService = Depends(AuthService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    sid = session_id or await authorization.get_current_sid()
    return await auth_service.logout_async(res, sid=sid)


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh(
    req: Request,
    res: Response,
    refresh_token: Optional[str] = Cookie(None),
    body: dict = Body(None),
    auth_service: AuthService = Depends(AuthService),
):
    # Ưu tiên lấy từ body nếu mobile gửi lên, nếu không thì lấy từ cookie
    token = refresh_token or (body.get("refresh_token") if body else None)
    
    user_agent = req.headers.get("user-agent")
    ip = req.client.host if req.client else None
    return await auth_service.refresh_token_async(token, res, user_agent=user_agent, ip=ip)


@router.get("/sessions")
async def list_sessions(
    auth_service: AuthService = Depends(AuthService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    sid = await authorization.get_current_sid()
    return await auth_service.list_sessions_async(user.id, current_sid=sid)


@router.post("/logout-all")
async def logout_all(
    auth_service: AuthService = Depends(AuthService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await auth_service.logout_all_async(user.id)


@router.post("/logout-others")
async def logout_others(
    auth_service: AuthService = Depends(AuthService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    sid = await authorization.get_current_sid()
    result = await auth_service.logout_all_async(user.id, keep_sid=sid)
    if result.get("revoked_session_ids"):
        await ws_manager.broadcast(
            f"AUTH_{user.id}",
            {
                "type": "auth.sessions_revoked",
                "data": {
                    "revoked_session_ids": result["revoked_session_ids"],
                },
            },
        )
    return result


@router.post("/security-alert-test")
async def security_alert_test(
    req: Request,
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    sid = await authorization.get_current_sid()
    await ws_manager.broadcast(
        f"AUTH_{user.id}",
        {
            "type": "auth.new_session",
            "data": {
                "session": {
                    "id": f"test-{sid}",
                    "device_type": "WEB",
                    "ip_address": req.client.host if req.client else None,
                    "user_agent": req.headers.get("user-agent"),
                    "created_at": None,
                    "is_test": True,
                }
            },
        },
    )
    return {"message": "Security alert test sent"}


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    auth_service: AuthService = Depends(AuthService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    result = await auth_service.revoke_session_async(session_id, user.id)
    if result.get("revoked_session_id"):
        await ws_manager.broadcast(
            f"AUTH_{user.id}",
            {
                "type": "auth.sessions_revoked",
                "data": {
                    "revoked_session_ids": [result["revoked_session_id"]],
                },
            },
        )
    return result


@router.post("/refesh-email", status_code=status.HTTP_200_OK)
async def refesh_email(
    schema: RefreshEmail = Body(),
    auth_service: AuthService = Depends(AuthService),
):
    return await auth_service.refesh_email_async(schema)


@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    res: Response,
    schema: VerifyEmail = Body(),
    auth_service: AuthService = Depends(AuthService),
):
    return await auth_service.verify_email_async(schema, res=res)


@router.get("/me")
async def me(
    auth_service: AuthService = Depends(AuthService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await auth_service.me_async(user)


@router.get("/check_is_login")
async def check_is_login(
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    if user:
        return {"message": "account is login"}
    return {"message": "account is not login"}


@router.post("/google")
async def login_with_google(
    req: Request,
    res: Response,
    body: GoogleLogin = Body(),
    service: AuthService = Depends(AuthService),
):
    user_agent = req.headers.get("user-agent")
    ip = req.client.host if req.client else None
    return await service.login_google_async(body, res, user_agent=user_agent, ip=ip)


@router.post("/send-otp")
async def send_otp(
    schema: SendOtp = Body(),
    auth_service: AuthService = Depends(AuthService),
):
    return await auth_service.send_otp_async(schema)


@router.get("/check-email")
async def check_email(
    email: str,
    auth_service: AuthService = Depends(AuthService),
):
    return await auth_service.check_email_async(email)


@router.post("/verify-otp")
async def verify_otp(
    req: Request,
    res: Response,
    schema: VerifyOtp = Body(),
    auth_service: AuthService = Depends(AuthService),
):
    user_agent = req.headers.get("user-agent")
    ip = req.client.host if req.client else None
    return await auth_service.verify_otp_login_async(schema, res, user_agent=user_agent, ip=ip)
