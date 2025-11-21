import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Query,
    status,
)

from app.core.deps import AuthorizationService
from app.db.models.database import User
from app.schemas.lecturer.courses import CourseReview
from app.services.user.category import CategoryService
from app.services.user.courses import CoursePublicService

router = APIRouter(prefix="/courses", tags=["User Course"])


@router.get("/feed/recommend")
async def recommend_feed(
    auth: AuthorizationService = Depends(AuthorizationService),
    course_service: CoursePublicService = Depends(CoursePublicService),
):
    try:
        user: User = await auth.get_current_user()
        return await course_service.get_recommended_top20(user.id)
    except Exception as e:
        print("❌ Recommend feed error:", e)
        raise HTTPException(500, "Có lỗi khi lấy danh sách gợi ý khóa học. {e}")


@router.get("/feed/top-rated")
async def top_rated_courses(
    limit: int = Query(10, ge=1, le=50),
    cursor: str | None = Query(None),
    auth: AuthorizationService = Depends(AuthorizationService),
    category_service: CategoryService = Depends(CategoryService),
    course_service: CoursePublicService = Depends(CoursePublicService),
):

    try:
        user = await auth.get_current_user_if_any()

        result = await course_service.get_top_rated_courses(
            user_id=user.id if user else None,
            limit=limit,
            cursor=cursor,
            category_sv=category_service,
        )
        return result

    except Exception as e:
        raise HTTPException(500, f"Lỗi router top-rated: {e}")


@router.get("/feed/newest")
async def newest_courses(
    limit: int = Query(10, ge=1, le=50),
    cursor: str | None = Query(None),
    auth: AuthorizationService = Depends(AuthorizationService),
    category_service: CategoryService = Depends(CategoryService),
    course_service: CoursePublicService = Depends(CoursePublicService),
):

    try:
        # Nếu user chưa đăng nhập → user_id = None (vẫn dùng đc)
        user = await auth.get_current_user_if_any()

        result = await course_service.get_newest_courses(
            user_id=user.id if user else None,
            limit=limit,
            cursor=cursor,
            category_sv=category_service,
        )
        return result

    except Exception as e:
        raise HTTPException(500, f"Lỗi router top-rated: {e}")


@router.get("/feed/top-view")
async def get_top_view_courses(
    limit: int = Query(10, ge=1, le=50),
    cursor: str | None = Query(None),
    auth: AuthorizationService = Depends(AuthorizationService),
    category_service: CategoryService = Depends(CategoryService),
    course_service: CoursePublicService = Depends(CoursePublicService),
):

    try:
        # Nếu user chưa đăng nhập → user_id = None (vẫn dùng đc)
        user = await auth.get_current_user_if_any()

        result = await course_service.get_top_view_courses(
            user_id=user.id if user else None,
            limit=limit,
            cursor=cursor,
            category_sv=category_service,
        )
        return result

    except Exception as e:
        raise HTTPException(500, f"Lỗi router top-rated: {e}")


@router.post("/{course_id}/review")
async def review_course(
    course_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    schema: CourseReview = Body(...),
    course_service: CoursePublicService = Depends(CoursePublicService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await course_service.review_course_async(
        course_id, background_tasks, schema, user
    )


@router.get("/{course_id}/detail-info", status_code=status.HTTP_200_OK)
async def get_course_detail_info(
    course_id: uuid.UUID,
    course_service: CoursePublicService = Depends(CoursePublicService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user_if_any()
    return await course_service.get_course_detail_info_async(course_id, user)


@router.get("/{course_slug}/detail-info-by-slug", status_code=status.HTTP_200_OK)
async def get_course_detail_info_by_slug(
    course_slug: str,
    course_service: CoursePublicService = Depends(CoursePublicService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user_if_any()
    return await course_service.get_course_detail_info_by_slug_async(course_slug, user)


@router.get("/{course_id}/preview")
async def get_all_lesson_preview(
    course_id: uuid.UUID,
    course_service: CoursePublicService = Depends(CoursePublicService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user_if_any()
    return await course_service.get_all_lesson_preview_async(course_id)


@router.get("/{course_id}/related_courses")
async def get_related_courses(
    course_id: uuid.UUID,
    course_service: CoursePublicService = Depends(CoursePublicService),
    cursor: str | None = None,
    limit: int = 4,  # ✅ thêm mặc định
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user_if_any()
    return await course_service.get_related_courses_async(
        course_id, limit, cursor, user
    )


@router.post("/{course_id}/enroll")
async def enroll_in_course(
    course_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    course_service: CoursePublicService = Depends(CoursePublicService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await course_service.enroll_in_course_async(
        course_id, background_tasks, user
    )


@router.get("/{course_id}/is_enroll")
async def check_user_enroll_course(
    course_id: uuid.UUID,
    course_service: CoursePublicService = Depends(CoursePublicService),
    authorization: AuthorizationService = Depends(AuthorizationService),
):
    user = await authorization.get_current_user()
    return await course_service.check_user_enroll_course_async(course_id, user)
