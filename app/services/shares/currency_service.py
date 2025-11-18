import httpx


async def convert_vnd_to_usd(amount_vnd: float) -> float:
    """Đổi VNĐ sang USD (free, không cần API key)."""
    url = "https://open.er-api.com/v6/latest/VND"
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        data = res.json()
        if data.get("result") != "success":
            raise ValueError("Không lấy được tỷ giá.")
        rate = data["rates"]["USD"]
        return round(amount_vnd * rate, 2)
