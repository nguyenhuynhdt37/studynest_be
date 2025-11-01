from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import LLMService
from app.db.sesson import get_session
from app.schemas.chat.admin.topic import CreateDetailsTopic


class TopicService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        llm_service: LLMService = Depends(LLMService),
    ) -> None:
        self.db = db
        self.llm_service = llm_service

    async def create_topic_details_async(self, schema: CreateDetailsTopic):
        try:
            prompt = f"""
                            Bạn là chuyên gia đào tạo trong lĩnh vực công nghệ thông tin.

                            Hãy viết phần **mô tả chi tiết cho một chủ đề học tập** theo hướng chuyên nghiệp và hấp dẫn.

                            **Thông tin:**
                            - Ngành học: {schema.name}
                            - Chủ đề: {schema.category_name}

                            **Yêu cầu:**
                            - Viết bằng tiếng Việt, độ dài 3–5 câu.
                            - Trình bày rõ nội dung chính, kỹ năng đạt được và ứng dụng thực tế.
                            - Trả về **chuẩn Markdown**, sử dụng các thẻ:
                            - `##` cho tiêu đề
                            - `**...**` cho phần nhấn mạnh
                            - danh sách `-` nếu cần
                            - **Chỉ trả về nội dung mô tả**, không thêm lời chào, chú thích hay tiêu đề phụ khác.
                            """
            return await self.llm_service.call_model(prompt)

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, detail=f"❌ Tạo mô tả chủ đề thất bại: {e}")
