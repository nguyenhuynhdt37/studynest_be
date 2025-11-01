from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.sesson import get_session
from app.services.user.category import CategoryService

router = APIRouter(prefix="/categories", tags=["User Category"])


def get_category_service(
    category_service: CategoryService = Depends(CategoryService),
) -> CategoryService:
    return category_service


@router.get("", status_code=status.HTTP_200_OK)
async def getCategory(
    category_service: CategoryService = Depends(get_category_service),
):
    return await category_service.get_categories_async()
