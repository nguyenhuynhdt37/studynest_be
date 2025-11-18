from fastapi import APIRouter, Depends, status

from app.services.user.category import CategoryService

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
