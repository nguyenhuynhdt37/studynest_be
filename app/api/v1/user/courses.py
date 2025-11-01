import uuid

from fastapi import APIRouter, BackgroundTasks, Body, Depends, status

from app.core.deps import AuthorizationService
from app.schemas.lecturer.courses import CourseReview
from app.services.user.courses import CoursePublicService

router = APIRouter(prefix="/courses", tags=["User Course"])


def get_course_service(
    service: CoursePublicService = Depends(CoursePublicService),
) -> CoursePublicService:
    return service


def get_authorization_service(
    authorization_service: AuthorizationService = Depends(AuthorizationService),
) -> AuthorizationService:
    return authorization_service


@router.post("/{course_id}/review")
async def review_course(
    course_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    schema: CourseReview = Body(...),
    course_service: CoursePublicService = Depends(get_course_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    return await course_service.review_course_async(
        course_id, background_tasks, schema, user
    )


@router.get("/feeds")
async def get_feeds(
    feed_type: str = "all",
    cursor: str | None = None,
    limit: int = 10,  # ✅ thêm mặc định
    course_service: CoursePublicService = Depends(get_course_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user_if_any()
    result = {}
    if feed_type in ("all", "personalization") and user is not None:
        result["personalization"] = await course_service.get_course_feed_async(
            "Khóa học dành riêng cho bạn", "personalization", limit, cursor, user
        )
    if feed_type in ("all", "views"):
        result["views"] = await course_service.get_course_feed_async(
            "Các khóa học thịnh hành", "views", limit, cursor, user
        )

    if feed_type in ("all", "best_sellers"):
        result["best_sellers"] = await course_service.get_course_feed_async(
            "Khóa học bán chạy", "total_enrolls", limit, cursor, user
        )

    if feed_type in ("all", "rating"):
        result["rating"] = await course_service.get_course_feed_async(
            "Khóa học được đánh giá cao", "rating_avg", limit, cursor, user
        )

    if feed_type in ("all", "created_at"):
        result["created_at"] = await course_service.get_course_feed_async(
            "Khóa học mới ra mắt", "created_at", limit, cursor, user
        )

    return result


@router.get("/{course_id}/detail-info", status_code=status.HTTP_200_OK)
async def get_course_detail_info(
    course_id: uuid.UUID,
    course_service: CoursePublicService = Depends(get_course_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user_if_any()
    return await course_service.get_course_detail_info_async(course_id, user)


@router.get("/{course_slug}/detail-info-by-slug", status_code=status.HTTP_200_OK)
async def get_course_detail_info_by_slug(
    course_slug: str,
    course_service: CoursePublicService = Depends(get_course_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user_if_any()
    return await course_service.get_course_detail_info_by_slug_async(course_slug, user)


@router.get("/{course_id}/preview")
async def get_all_lesson_preview(
    course_id: uuid.UUID,
    course_service: CoursePublicService = Depends(get_course_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user_if_any()
    return await course_service.get_all_lesson_preview_async(course_id)


@router.get("/{course_id}/related_courses")
async def get_related_courses(
    course_id: uuid.UUID,
    course_service: CoursePublicService = Depends(get_course_service),
    cursor: str | None = None,
    limit: int = 4,  # ✅ thêm mặc định
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user_if_any()
    return await course_service.get_related_courses_async(
        course_id, limit, cursor, user
    )


@router.post("/{course_id}/enroll")
async def enroll_in_course(
    course_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    course_service: CoursePublicService = Depends(get_course_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    return await course_service.enroll_in_course_async(
        course_id, background_tasks, user
    )


@router.get("/{course_id}/is_enroll")
async def check_user_enroll_course(
    course_id: uuid.UUID,
    course_service: CoursePublicService = Depends(get_course_service),
    authorization: AuthorizationService = Depends(get_authorization_service),
):
    user = await authorization.get_current_user()
    return await course_service.check_user_enroll_course_async(course_id, user)
