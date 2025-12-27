from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import LLMService
from app.db.models.database import User
from app.db.sesson import get_session
from app.schemas.chat.user.profile import CreateBioSchema


class ProfileService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        llm_service: LLMService = Depends(LLMService),
    ) -> None:
        self.db = db
        self.llm_service = llm_service

    async def create_bio_async(self, schema: CreateBioSchema, user: User) -> str:
        """
        Tạo bio cho học viên.
        Trả về: text thuần (markdown string)
        """
        try:
            prompt = f"""
            Bạn là chuyên gia viết hồ sơ học viên (student bio) cho nền tảng học trực tuyến — giống như Udemy hoặc Coursera.

            Nhiệm vụ:
            - Viết phần **giới thiệu bản thân (bio)** của học viên ngắn gọn, tự nhiên và tích cực.
            - Giọng văn thân thiện, thể hiện tinh thần học hỏi và mục tiêu phát triển bản thân.
            - Đầu ra là **Markdown thuần túy**, không bao quanh bằng code block hoặc thêm tiêu đề.

            ---  
            🧩 **Thông tin học viên**
            - Họ và tên: {user.fullname}
            - Email: {user.email}
            - Tiểu sử hiện tại (nếu có): {user.bio or "Chưa có"}
            - Kỹ năng / lĩnh vực quan tâm: {user.preferences_str or "Chưa cập nhật"}
            - Khu vực sinh sống: {user.conscious or "Không rõ"}, {user.district or "Không rõ"}
            - Mục tiêu học tập: {"Nâng cao kỹ năng và tìm cơ hội nghề nghiệp mới" if not getattr(user, "goals", None) else user.goals}
            - Yêu cầu cụ thể từ học viên: "{schema.request}"
            ---

            ✍️ **Yêu cầu đầu ra**
            - Viết bằng tiếng Việt.
            - Độ dài khoảng 3–5 câu.
            - Cho phép dùng Markdown nhẹ (**in đậm**, *in nghiêng*).
            - Không thêm tiêu đề "Giới thiệu", không chèn emoji hay HTML.
            - Tập trung vào hành trình học tập, động lực và mục tiêu phát triển của học viên.

            Ví dụ đầu ra mong muốn (Markdown):
            Tôi là **sinh viên Công nghệ thông tin**, yêu thích học hỏi và khám phá những công nghệ mới.  
            Tôi mong muốn trau dồi kỹ năng *lập trình web* và phát triển tư duy sáng tạo trong các dự án thực tế.  
            Mục tiêu của tôi là trở thành lập trình viên giỏi và có thể đóng góp vào các sản phẩm ý nghĩa cho cộng đồng.
            """

            result = await self.llm_service.call_model(prompt, temperature=0.7)
            return result.strip()

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, detail=f"❌ Tạo bio học viên thất bại: {e}")
