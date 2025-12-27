from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import AuthorizationService
from app.services.shares.notification import NotificationService
from app.services.user.lecturer import LecturerService

router = APIRouter(prefix="/users/instructors", tags=["User • instructors"])


@router.get("/top")
async def get_top_instructors(
    service: LecturerService = Depends(LecturerService),
):
    try:
        return await service.get_top4_instructors_async()
    except Exception as e:
        print("❌ Get top instructors error:", e)
        raise HTTPException(500, f"Có lỗi khi lấy danh sách giảng viên hàng đầu. {e}")


@router.get("/{lecturer_id}")
async def get_instructor_detail(
    lecturer_id: UUID,
    service: LecturerService = Depends(LecturerService),
):
    result = await service.get_instructor_detail_async(lecturer_id)

    if result is None:
        raise HTTPException(404, "Không tìm thấy giảng viên hợp lệ.")

    return result


@router.get("/{lecturer_id}/courses")
async def get_instructor_courses(
    lecturer_id: UUID,
    limit: int = 20,
    cursor: str | None = None,
    keyword: str | None = None,
    category_slug: str | None = None,
    topic_slug: str | None = None,
    level: str | None = None,
    sort: str = "created_at_desc",
    service: LecturerService = Depends(LecturerService),
    authorization_service: AuthorizationService = Depends(AuthorizationService),
):
    try:
        user = await authorization_service.get_current_user_if_any()
        return await service.get_instructor_courses_async(
            lecturer_id=lecturer_id,
            user_id=user.id if user else None,
            limit=limit,
            cursor=cursor,
            keyword=keyword,
            category_slug=category_slug,
            topic_slug=topic_slug,
            level=level,
            sort=sort,
        )
    except Exception as e:
        print("❌ Get instructor courses error:", e)
        raise HTTPException(
            500, f"Có lỗi khi lấy danh sách khóa học của giảng viên. {e}"
        )


@router.post("/become")
async def become_instructor(
    authorization_service: AuthorizationService = Depends(AuthorizationService),
    notification_service: NotificationService = Depends(NotificationService),
    service: LecturerService = Depends(LecturerService),
):
    """
    Đăng ký làm giảng viên:
    - Trừ 1.000.000 VNĐ trong ví user
    - Tạo role LECTURER nếu chưa có
    - Gán role cho user
    - Log giao dịch vào bảng Transactions
    """
    user = await authorization_service.get_current_user()
    return await service.become_instructor_async(user, notification_service)
