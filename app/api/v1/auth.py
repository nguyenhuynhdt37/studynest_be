from fastapi import APIRouter, Body, Depends, Response, status

from app.core.deps import AuthorizationService
from app.schemas.auth.user import LoginUser, RefreshEmail, UserCreate, VerifyEmail
from app.services.shares.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_auth_service(auth: AuthService = Depends(AuthService)) -> AuthService:
    return auth


def get_authorization_service(
    authorization_service: AuthorizationService = Depends(AuthorizationService),
) -> AuthorizationService:
    return authorization_service


@router.post("/login", status_code=200)
async def login(
    res: Response,
    schema: LoginUser = Body(),
    auth_service: AuthService = Depends(get_auth_service),
):
    return await auth_service.login_async(schema, res)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    schema: UserCreate = Body(),
    auth_service: AuthService = Depends(get_auth_service),
):
    return await auth_service.register_async(schema)


@router.get("/logout", status_code=status.HTTP_200_OK)
async def logout(
    res: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    return await auth_service.logout_async(res)


@router.post("/refesh-email", status_code=status.HTTP_200_OK)
async def refesh_email(
    schema: RefreshEmail = Body(),
    auth_service: AuthService = Depends(get_auth_service),
):
    return await auth_service.refesh_email_async(schema)


@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    res: Response,
    schema: VerifyEmail = Body(),
    auth_service: AuthService = Depends(get_auth_service),
):
    return await auth_service.verify_email_async(schema, res=res)


@router.get("/me")
async def me(
    auth_service: AuthService = Depends(get_auth_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    return await auth_service.me_async(user)


@router.get("/check_is_login")
async def check_is_login(
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    if user:
        return {"message": "account is login"}
    return {"message": "account is not login"}
