import httpx
from fastapi import APIRouter, Request

router = APIRouter(prefix="/location", tags=["Location"])
GEO_API_URL = "http://ip-api.com/json/"


@router.get("", summary="Lấy thông tin vị trí theo IP công khai")
async def get_location(request: Request):
    # Lấy IP client
    ip = request.client.host if request.client else "8.8.8.8"

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GEO_API_URL}{ip}?fields=status,country,regionName,city,zip,lat,lon"
        )

    data = resp.json()

    if data.get("status") != "success":
        return {"error": "Không xác định được vị trí"}

    return {
        "ip": ip,
        "country": data.get("country"),
        "province": data.get("regionName"),
        "city": data.get("city"),
        "postal_code": data.get("zip"),
        "lat": data.get("lat"),
        "lon": data.get("lon"),
    }
