from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import AuthorizationService
from app.db.models.database import User
from app.services.user.category import CategoryService
from app.services.user.courses import CoursePublicService

router = APIRouter(prefix="/categories", tags=["User Category"])


@router.get("", status_code=status.HTTP_200_OK)
async def getCategory(
    category_service: CategoryService = Depends(CategoryService),
):
    return await category_service.get_categories_async()


@router.get("/all", status_code=status.HTTP_200_OK)
async def getCategory_all(
    category_service: CategoryService = Depends(CategoryService),
):
    return await category_service.get_all_categories_async()


@router.get("/subcategories", status_code=status.HTTP_200_OK)
async def get_all_subcategories(
    category_service: CategoryService = Depends(CategoryService),
):
    return await category_service.get_categories_with_topics()


@router.get("/{category_slug}/lectures/feed/recommend")
async def recommend_lectures_feed(
    category_slug: str,
    service: CategoryService = Depends(CategoryService),
):
    try:
        return await service.get_top_instructors(category_slug)
    except Exception as e:
        print("❌ Recommend lectures feed error:", e)
        raise HTTPException(500, f"Có lỗi khi lấy danh sách gợi ý bài học. {e}")


@router.get("/{category_slug}/courses/feed/recommend")
async def recommend_feed(
    category_slug: str,
    auth: AuthorizationService = Depends(AuthorizationService),
    service: CategoryService = Depends(CategoryService),
):
    try:
        user: User = await auth.get_current_user()
        return await service.get_related_courses_async(user.id, category_slug)
    except Exception as e:
        print("❌ Recommend feed error:", e)
        raise HTTPException(500, f"Có lỗi khi lấy danh sách gợi ý khóa học. {e}")


@router.get("/{category_slug}/courses/feed/top-rated")
async def top_rated_courses(
    category_slug: str,
    limit: int = Query(10, ge=1, le=50),
    cursor: str | None = Query(None),
    auth: AuthorizationService = Depends(AuthorizationService),
    category_service: CategoryService = Depends(CategoryService),
    course_service: CoursePublicService = Depends(CoursePublicService),
):

    try:
        # Nếu user chưa đăng nhập → user_id = None (vẫn dùng đc)
        user = await auth.get_current_user_if_any()

        result = await course_service.get_top_rated_courses(
            user_id=user.id if user else None,
            category_slug=category_slug,
            limit=limit,
            cursor=cursor,
            category_sv=category_service,
        )
        return result

    except Exception as e:
        raise HTTPException(500, f"Lỗi router top-rated: {e}")


@router.get("/{category_slug}/courses/feed/newest")
async def newest_courses(
    category_slug: str,
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
            category_slug=category_slug,
            limit=limit,
            cursor=cursor,
            category_sv=category_service,
        )
        return result

    except Exception as e:
        raise HTTPException(500, f"Lỗi router top-rated: {e}")


@router.get("/{category_slug}/related")
async def get_related_categories(
    category_slug: str,
    service: CategoryService = Depends(CategoryService),
):
    try:
        return await service.get_related_categories(category_slug)
    except HTTPException:
        raise
    except Exception as e:
        print("❌ Related category route error:", e)
        raise HTTPException(500, f"Lỗi khi lấy danh mục liên quan. {e}")


@router.get("/{category_slug}/courses")
async def get_courses_by_category(
    category_slug: str,
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = None,
    rating: float | None = Query(None, ge=1.0, le=5.0),
    duration: str | None = Query(None, regex="^(0-1|1-3|3-6|6-17)$"),
    level: str | None = None,
    language: str | None = None,
    price: str | None = Query(None, regex="^(free|paid)$"),
    sort: str = Query("newest", regex="^(newest|top_rated|most_popular)$"),
    service: CategoryService = Depends(CategoryService),
):
    """
    Lấy danh sách khóa học theo category:
    - Cursor-based pagination
    - Filter: rating, duration, level, language, price
    - Sort: newest, top_rated, most_popular
    """

    try:
        return await service.get_category_courses(
            category_slug=category_slug,
            limit=limit,
            cursor=cursor,
            rating=rating,
            duration=duration,
            level=level,
            language=language,
            sort=sort,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Lỗi khi lấy danh sách khóa học theo category. {e}")


@router.get("/{category_slug}/get_root_and_level1")
async def get_root_and_level1_categories(
    category_slug: str,
    service: CategoryService = Depends(CategoryService),
):
    try:
        return await service.get_root_and_level1_async(category_slug)
    except HTTPException:
        raise
    except Exception as e:
        print("❌ get_root_and_level1_categories route error:", e)
        raise HTTPException(500, f"Lỗi khi lấy danh mục gốc và cấp 1. {e}")
