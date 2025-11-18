from datetime import datetime, timedelta, timezone
from typing import Any

# Múi giờ Việt Nam (UTC+7)
VIETNAM_TIMEZONE = timezone(timedelta(hours=7))


def now() -> datetime:
    """Lấy datetime hiện tại với múi giờ Hồ Chí Minh (UTC+7) và bỏ tzinfo (naive).
    Đây là hàm chuẩn cho toàn bộ dự án.
    """
    return datetime.now(VIETNAM_TIMEZONE).replace(tzinfo=None)


def now_tzinfo() -> datetime:
    return datetime.now(VIETNAM_TIMEZONE)


async def to_vietnam_naive(dt: datetime | None) -> datetime | None:
    """Chuyển datetime (có hoặc không tzinfo) sang múi giờ Việt Nam (UTC+7) và bỏ tzinfo.
    - Nếu dt là None → trả về None
    - Nếu dt có timezone → convert sang UTC+7, bỏ tzinfo
    - Nếu dt không có timezone → giả định đã là UTC+7, trả về nguyên
    """
    if dt is None:
        return None

    # Nếu có tzinfo thì normalize sang UTC+7 trước
    if dt.tzinfo is not None:
        return dt.astimezone(VIETNAM_TIMEZONE).replace(tzinfo=None)

    # Trả về nguyên nếu đã là naive (giả định là UTC+7)
    return dt


# Giữ lại để backward compatibility, nhưng sẽ redirect sang hàm mới
async def to_utc_naive(dt: datetime | None) -> datetime | None:
    """DEPRECATED: Sử dụng to_vietnam_naive() thay thế.
    Chuyển datetime (có hoặc không tzinfo) sang múi giờ Việt Nam (UTC+7) và bỏ tzinfo.
    """
    return await to_vietnam_naive(dt)


async def serialize(obj: Any) -> Any:
    # datetime → ISO string
    if isinstance(obj, datetime):
        return obj.isoformat()

    # dict → duyệt key/value
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            result[k] = await serialize(v)
        return result

    # list → duyệt từng item
    if isinstance(obj, list):
        return [await serialize(v) for v in obj]

    # tuple (nếu bạn có)
    if isinstance(obj, tuple):
        return tuple([await serialize(v) for v in obj])

    # value thường → trả nguyên
    return obj


def strip_tz(dt: datetime | None):
    return dt.replace(tzinfo=None) if dt and dt.tzinfo else dt
