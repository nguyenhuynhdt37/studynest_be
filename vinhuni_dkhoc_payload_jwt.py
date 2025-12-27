#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tool đăng ký học phần Vinh University - Hỗ trợ đăng ký song song nhiều tài khoản.

Usage:
    python vinhuni_dkhoc_payload_jwt.py payload.json

payload.json có thể là:
    - Object đơn lẻ: { "jwt": "...", "maSinhVien": "...", ... }
    - Mảng nhiều tài khoản: [ { "jwt": "...", ... }, { "jwt": "...", ... } ]
"""

import asyncio
import json
import logging
import sys
from datetime import datetime

import httpx

# Tắt log của httpx và httpcore (log tiếng Anh)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Setup logging cho ứng dụng
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

URL = (
    "https://usmart.vinhuni.edu.vn/gwsg/dbdaotao_chinhquysv/DangKyHoc/SinhVienDangKyHoc"
)

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "origin": "https://congsv.vinhuni.edu.vn",
    "referer": "https://congsv.vinhuni.edu.vn/",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36"
    ),
}

# Timeout config (seconds)
TIMEOUT = httpx.Timeout(
    connect=10.0,  # Thời gian kết nối
    read=60.0,  # Thời gian đọc response (tăng lên 60s)
    write=10.0,  # Thời gian ghi request
    pool=10.0,  # Thời gian chờ connection pool
)


async def register_single(client: httpx.AsyncClient, payload: dict, index: int) -> dict:
    """
    Gửi request đăng ký cho 1 tài khoản.
    Trả về dict chứa kết quả.
    """
    ma_sv = payload.get("maSinhVien", f"Tài khoản #{index + 1}")
    id_hoc_phans = payload.get("idHocPhans", [])
    id_lop_hoc_phans = payload.get("idLopHocPhans", [])

    logger.info(f"[{index + 1}] 🚀 GỬI REQUEST")
    logger.info(f"    ├─ MSSV: {ma_sv}")
    logger.info(f"    ├─ Mã học phần: {id_hoc_phans}")
    logger.info(f"    └─ Mã lớp học phần: {id_lop_hoc_phans}")

    # Validate JWT
    if "jwt" not in payload or not payload["jwt"]:
        logger.error(f"[{index + 1}] ❌ Thiếu JWT token trong payload")
        return {
            "index": index,
            "maSinhVien": ma_sv,
            "idHocPhans": id_hoc_phans,
            "idLopHocPhans": id_lop_hoc_phans,
            "success": False,
            "error": "❌ Thiếu field 'jwt' trong payload",
        }

    headers = {
        **HEADERS,
        "authorization": f"Bearer {payload['jwt']}",
    }

    start_time = datetime.now()

    try:
        resp = await client.post(URL, headers=headers, json=payload)

        elapsed = (datetime.now() - start_time).total_seconds()

        try:
            data = resp.json()
        except Exception:
            data = resp.text

        result = {
            "index": index,
            "maSinhVien": ma_sv,
            "idHocPhans": id_hoc_phans,
            "idLopHocPhans": id_lop_hoc_phans,
            "status_code": resp.status_code,
            "success": resp.status_code == 200,
            "response": data,
            "elapsed_seconds": elapsed,
        }

        if resp.status_code == 200:
            logger.info(f"[{index + 1}] ✅ THÀNH CÔNG sau {elapsed:.2f}s")
        elif resp.status_code in (401, 403):
            logger.warning(
                f"[{index + 1}] ⚠️ JWT hết hạn hoặc không hợp lệ - HTTP {resp.status_code}"
            )
            result["warning"] = "⚠️ JWT hết hạn hoặc không hợp lệ"
        else:
            logger.error(
                f"[{index + 1}] ❌ THẤT BẠI - HTTP {resp.status_code} sau {elapsed:.2f}s"
            )

        # In JSON response từ server
        if isinstance(data, dict):
            response_json = json.dumps(data, ensure_ascii=False)
            logger.info(f"[{index + 1}] 📄 Phản hồi: {response_json}")
        else:
            logger.info(f"[{index + 1}] 📄 Phản hồi: {data}")

        return result

    except httpx.TimeoutException:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"[{index + 1}] ⏱️ HẾT THỜI GIAN CHỜ sau {elapsed:.2f}s")
        return {
            "index": index,
            "maSinhVien": ma_sv,
            "idHocPhans": id_hoc_phans,
            "idLopHocPhans": id_lop_hoc_phans,
            "success": False,
            "error": f"❌ Hết thời gian chờ sau {elapsed:.2f}s",
            "elapsed_seconds": elapsed,
        }
    except httpx.ConnectError as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"[{index + 1}] 🔌 LỖI KẾT NỐI: {str(e)}")
        return {
            "index": index,
            "maSinhVien": ma_sv,
            "idHocPhans": id_hoc_phans,
            "idLopHocPhans": id_lop_hoc_phans,
            "success": False,
            "error": f"❌ Lỗi kết nối: {str(e)}",
            "elapsed_seconds": elapsed,
        }
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.exception(f"[{index + 1}] 💥 LỖI: {type(e).__name__}: {str(e)}")
        return {
            "index": index,
            "maSinhVien": ma_sv,
            "idHocPhans": id_hoc_phans,
            "idLopHocPhans": id_lop_hoc_phans,
            "success": False,
            "error": f"❌ Lỗi: {type(e).__name__}: {str(e)}",
            "elapsed_seconds": elapsed,
        }


async def register_all(payloads: list[dict]) -> list[dict]:
    """
    Đăng ký song song tất cả tài khoản.
    """
    logger.info(f"🔄 Đang khởi tạo {len(payloads)} yêu cầu đăng ký song song...")
    logger.info("-" * 60)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        tasks = [
            register_single(client, payload, i) for i, payload in enumerate(payloads)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Xử lý trường hợp exception không được catch
    processed_results = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.error(
                f"[{i + 1}] 💥 Lỗi không xử lý được: {type(r).__name__}: {str(r)}"
            )
            processed_results.append(
                {
                    "index": i,
                    "maSinhVien": payloads[i].get("maSinhVien", f"Tài khoản #{i + 1}"),
                    "idHocPhans": payloads[i].get("idHocPhans", []),
                    "idLopHocPhans": payloads[i].get("idLopHocPhans", []),
                    "success": False,
                    "error": f"❌ Lỗi: {type(r).__name__}: {str(r)}",
                }
            )
        else:
            processed_results.append(r)

    return processed_results


def print_results(results: list[dict]):
    """
    In kết quả đẹp ra console.
    """
    print("\n" + "=" * 70)
    print(
        f"📋 KẾT QUẢ ĐĂNG KÝ HỌC PHẦN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print("=" * 70)

    success_count = 0
    fail_count = 0

    for r in results:
        elapsed = r.get("elapsed_seconds", 0)
        elapsed_str = f" ({elapsed:.2f}s)" if elapsed else ""

        print(f"\n🔹 [{r['index'] + 1}] MSSV: {r['maSinhVien']}{elapsed_str}")
        print(f"    Mã học phần: {r.get('idHocPhans', [])}")
        print(f"    Mã lớp học phần: {r.get('idLopHocPhans', [])}")

        if r.get("success"):
            print(f"    ✅ Trạng thái: THÀNH CÔNG (HTTP {r.get('status_code', 'N/A')})")
            success_count += 1
        else:
            fail_count += 1
            if "error" in r:
                print(f"    {r['error']}")
            else:
                print(
                    f"    ❌ Trạng thái: THẤT BẠI (HTTP {r.get('status_code', 'N/A')})"
                )

        if "warning" in r:
            print(f"    {r['warning']}")

        # In response (nếu có)
        if "response" in r:
            response_str = json.dumps(r["response"], ensure_ascii=False, indent=2)
            # Indent response
            indented = "\n".join(f"    {line}" for line in response_str.split("\n"))
            print(f"    Phản hồi từ server:\n{indented}")

    print("\n" + "=" * 70)
    print(f"📊 TỔNG KẾT: ✅ {success_count} thành công | ❌ {fail_count} thất bại")
    print("=" * 70 + "\n")


def main():
    if len(sys.argv) != 2:
        print("Cách dùng: python vinhuni_dkhoc_payload_jwt.py payload.json")
        print("\npayload.json có thể là:")
        print('  - Đối tượng đơn lẻ: { "jwt": "...", ... }')
        print("  - Mảng nhiều tài khoản: [ {...}, {...} ]")
        sys.exit(1)

    payload_file = sys.argv[1]

    logger.info(f"📂 Đang đọc file: {payload_file}")

    with open(payload_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Normalize: chuyển object đơn thành list
    if isinstance(data, dict):
        payloads = [data]
        logger.info("📌 Chế độ: Đăng ký 1 tài khoản")
    elif isinstance(data, list):
        payloads = data
        logger.info(f"📌 Chế độ: Đăng ký song song {len(payloads)} tài khoản")
    else:
        logger.error("❌ payload.json phải là object hoặc array")
        sys.exit(1)

    if not payloads:
        logger.error("❌ Không có payload nào để xử lý")
        sys.exit(1)

    # Log thông tin tổng quan
    logger.info("-" * 60)
    logger.info("📋 DANH SÁCH ĐĂNG KÝ:")
    for i, p in enumerate(payloads):
        logger.info(
            f"    [{i + 1}] MSSV: {p.get('maSinhVien')} | HP: {p.get('idHocPhans')} | LHP: {p.get('idLopHocPhans')}"
        )
    logger.info("-" * 60)

    # Chạy async
    start_time = datetime.now()
    results = asyncio.run(register_all(payloads))
    total_elapsed = (datetime.now() - start_time).total_seconds()

    logger.info("-" * 60)
    logger.info(f"⏱️ Tổng thời gian thực hiện: {total_elapsed:.2f} giây")

    # In kết quả
    print_results(results)


if __name__ == "__main__":
    main()
