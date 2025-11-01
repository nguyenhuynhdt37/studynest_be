# app/services/mailer.py
from pathlib import Path

from fastapi import Depends
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import SecretStr

from app.core.settings import settings


class MailerService:
    """Service gửi email hệ thống (xác thực, reset mật khẩu, thông báo, v.v.)."""

    def __init__(self):
        base_dir = Path(__file__).resolve().parent.parent.parent  # -> app/
        template_dir = base_dir / "templates" / "emails"

        self.conf = ConnectionConfig(
            MAIL_USERNAME=settings.MAIL_USERNAME,
            MAIL_PASSWORD=SecretStr(settings.MAIL_PASSWORD),
            MAIL_FROM=settings.MAIL_FROM,
            MAIL_PORT=settings.MAIL_PORT,
            MAIL_SERVER=settings.MAIL_SERVER,
            MAIL_STARTTLS=settings.MAIL_TLS,
            MAIL_SSL_TLS=settings.MAIL_SSL,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
            TEMPLATE_FOLDER=template_dir,
        )
        self.fastmail = FastMail(self.conf)

    async def send_verification_email(self, email: str, fullname: str, code: str):
        """Gửi email xác thực tài khoản."""
        message = MessageSchema(
            subject="Xác thực email - Huỳnh E-learning",
            recipients=[email],
            template_body={"fullname": fullname, "code": code},
            subtype=MessageType.html,
        )
        await self.fastmail.send_message(message, template_name="verify_email.html")
        return {"message": f"Đã gửi email xác thực đến {email}"}

    async def send_reset_password_email(
        self, email: str, fullname: str, reset_link: str
    ):
        """Gửi email đặt lại mật khẩu."""
        message = MessageSchema(
            subject="Đặt lại mật khẩu - Huỳnh E-learning",
            recipients=[email],
            template_body={"fullname": fullname, "reset_link": reset_link},
            subtype=MessageType.html,
        )
        await self.fastmail.send_message(message, template_name="reset_password.html")
        return {"message": f"Đã gửi email đặt lại mật khẩu đến {email}"}

    async def send_custom_email(
        self,
        subject: str,
        recipients: list[str],
        template_name: str,
        context: dict,
    ):
        """Gửi email tùy chỉnh (dùng chung cho thông báo hệ thống)."""
        message = MessageSchema(
            subject=subject,
            recipients=recipients,
            template_body=context,
            subtype=MessageType.html,
        )
        await self.fastmail.send_message(message, template_name=template_name)
        return {"message": f"Đã gửi email '{subject}' đến {', '.join(recipients)}"}


# ✅ Dependency Injection để dùng trong router
def get_mailer_service() -> MailerService:
    return MailerService()
