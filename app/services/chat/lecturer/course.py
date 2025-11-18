from fastapi import Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import LLMService
from app.db.sesson import get_session
from app.schemas.chat.lecturer.course import (
    CreateCourseDescriptionSchema,
    CreateCourseObjectivesAndAudienceSchema,
    CreateShortCourseDescriptionSchema,
)


class CourseService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_session),
        llm_service: LLMService = Depends(LLMService),
    ) -> None:
        self.db = db
        self.llm_service = llm_service

    async def create_short_description_async(
        self, schema: CreateShortCourseDescriptionSchema
    ):
        try:
            prompt = f"""
                Bạn là chuyên gia đào tạo trong lĩnh vực viết nội dung cho các khóa học trực tuyến..

                Hãy viết phần mô tả ngắn gọn, chuyên nghiệp và hấp dẫn cho một khóa học.

                Thông tin khóa học:
                - Tên khóa học: {schema.course_name}

                Yêu cầu:
                - Viết bằng tiếng Việt, độ dài khoảng 2 câu.
                - Trình bày rõ mục tiêu, kiến thức và kỹ năng đạt được, cùng với ứng dụng thực tế của khóa học.
                - Văn phong tự nhiên, dễ hiểu, mang tính truyền cảm hứng.
                - Chỉ trả về nội dung mô tả thuần văn bản, không dùng ký hiệu Markdown hoặc thẻ định dạng.
                """

            return await self.llm_service.call_model(prompt)

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, detail=f"❌ Tạo mô tả chủ đề thất bại: {e}")

    async def create_description_async(self, schema: CreateCourseDescriptionSchema):
        try:
            prompt = f"""
                Bạn là chuyên gia đào tạo trong lĩnh vực **viết nội dung cho các khóa học trực tuyến.**.

                Hãy viết phần **mô tả chi tiết khóa học** thật chuyên nghiệp, hấp dẫn và có chiều sâu.

                **Thông tin đầu vào:**
                - Tên khóa học: {schema.course_name}
                - Chủ đề: {schema.category_name}
                - Mô tả ngắn: {schema.short_description}
                - Tên topic (nếu có): {schema.topic_name or "Không có"}

                **Yêu cầu:**
                - Viết bằng **tiếng Việt**, độ dài khoảng **6–10 câu**.
                - Trả về ở **định dạng Markdown siêu đẹp**, có bố cục rõ ràng:
                - `##` cho tiêu đề khóa học
                - `###` cho phần giới thiệu hoặc nội dung trọng tâm
                - Dùng `**...**` để nhấn mạnh kỹ năng hoặc công nghệ quan trọng
                - Dùng danh sách `-` để trình bày lợi ích hoặc kỹ năng đạt được
                - Nội dung nên có:
                - Giới thiệu tổng quan và mục tiêu khóa học
                - Kiến thức và kỹ năng học viên sẽ đạt được
                - Ứng dụng thực tế hoặc hướng phát triển nghề nghiệp
                - Văn phong tự nhiên, truyền cảm hứng, thể hiện chuyên môn sâu.
                - Không trả về tiêu đề ví dụ:  "Nền tảng CNTT và Phần mềm cho Lập trình viên Web"
                - **Chỉ trả về phần mô tả Markdown**, không thêm lời dẫn, hướng dẫn hay ký tự thừa. chỉ trả về markdown.
                - không được trả ra dạng json {{"description": "nội dung mô tả"}} mà hãy trả ra đúng phần mô tả thôi
                """
            result = await self.llm_service.call_model(prompt)
            return PlainTextResponse(result, media_type="text/markdown")

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, detail=f"❌ Tạo mô tả chủ đề thất bại: {e}")

    async def create_learning_goals_async(
        self, schema: CreateCourseObjectivesAndAudienceSchema
    ):
        try:
            prompt = f"""
                Bạn là chuyên gia đào tạo trong lĩnh vực viết nội dung cho các khóa học trực tuyến..

                Hãy liệt kê **ngắn gọn các mục tiêu học tập** mà học viên sẽ đạt được sau khi hoàn thành khóa học.

                **Thông tin đầu vào:**
                - Tên khóa học: {schema.course_name}
                - Mô tả ngắn: {schema.short_description}
                - Chủ đề: {schema.category_name}
                - Tên topic (nếu có): {schema.topic_name or "Không có"}

                **Yêu cầu:**
                - Trả về **dưới dạng mảng JSON hợp lệ** (list trong Python), ví dụ:
                ["Hiểu khái niệm A", "Thực hành kỹ năng B"] không được có bất cứ ký tự nào khác
                - Mỗi phần tử là **một chuỗi ngắn gọn (5–15 từ)** mô tả một kỹ năng hoặc kiến thức cụ thể.
                - Viết bằng **tiếng Việt**, tự nhiên, rõ ràng, không có Markdown, không giải thích, không thêm ký tự thừa.
                - Tối thiểu **3 phần tử**, tối đa **8 phần tử**.
                - **Chỉ trả về mảng JSON**, không kèm văn bản khác.
                """

            return await self.llm_service.call_model(prompt)

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, detail=f"❌ Tạo mô tả chủ đề thất bại: {e}")

    async def create_request_async(
        self, schema: CreateCourseObjectivesAndAudienceSchema
    ):
        try:
            prompt = f"""
                Bạn là chuyên gia đào tạo trong lĩnh vực viết nội dung cho các khóa học trực tuyến..

                Hãy liệt kê **ngắn gọn các yêu cầu cần có hoặc điều kiện cần chuẩn bị** khi học khóa học này.

                **Thông tin đầu vào:**
                - Tên khóa học: {schema.course_name}
                - Mô tả ngắn: {schema.short_description}
                - Chủ đề: {schema.category_name}
                - Tên topic (nếu có): {schema.topic_name or "Không có"}

                **Yêu cầu:**
                - Trả về **dưới dạng mảng JSON hợp lệ** (list trong Python), ví dụ:
                ["Biết kiến thức cơ bản về lập trình", "Có laptop cài đặt môi trường Python"]
                - Mỗi phần tử là **một chuỗi ngắn gọn (5–15 từ)** mô tả yêu cầu hoặc điều kiện học tập cụ thể.
                - Viết bằng **tiếng Việt**, tự nhiên, rõ ràng, không có Markdown, không giải thích, không thêm ký tự thừa.
                - Tối thiểu **2 phần tử**, tối đa **6 phần tử**.
                - **Chỉ trả về mảng JSON**, không kèm văn bản khác.
                """

            return await self.llm_service.call_model(prompt)

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, detail=f"❌ Tạo mô tả chủ đề thất bại: {e}")

    async def create_student_target_async(
        self, schema: CreateCourseObjectivesAndAudienceSchema
    ):
        try:
            prompt = f"""
                Bạn là chuyên gia đào tạo trong lĩnh vực viết nội dung cho các khóa học trực tuyến..

                Hãy liệt kê **các nhóm đối tượng học viên phù hợp nhất** với khóa học này.

                **Thông tin đầu vào:**
                - Tên khóa học: {schema.course_name}
                - Mô tả ngắn: {schema.short_description}
                - Chủ đề: {schema.category_name}
                - Tên topic (nếu có): {schema.topic_name or "Không có"}

                **Yêu cầu:**
                - Trả về **dưới dạng mảng JSON hợp lệ** (list trong Python), ví dụ:
                ["Sinh viên ngành CNTT", "Người mới bắt đầu học lập trình", "Lập trình viên muốn nâng cao kỹ năng"]
                - Mỗi phần tử là **một chuỗi ngắn gọn (5–15 từ)** mô tả rõ đối tượng phù hợp.
                - Viết bằng **tiếng Việt**, tự nhiên, rõ ràng, không có Markdown, không giải thích, không thêm ký tự thừa.
                - Tối thiểu **2 phần tử**, tối đa **6 phần tử**.
                - **Chỉ trả về mảng JSON**, không kèm bất kỳ văn bản nào khác.
                """

            return await self.llm_service.call_model(prompt)

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(500, detail=f"❌ Tạo mô tả chủ đề thất bại: {e}")
