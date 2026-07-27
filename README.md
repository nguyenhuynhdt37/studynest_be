# 🧠 StudyNest LMS Backend REST API - Hệ Thống Quản Lý Học Tập Trực Tuyến

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![PLpgSQL](https://img.shields.io/badge/PL/pgSQL-Stored_Procedures-336791?style=for-the-badge)](https://www.postgresql.org/docs/current/plpgsql.html)

Máy chủ Backend API chuyên nghiệp cung cấp toàn bộ API nghiệp vụ cho nền tảng **StudyNest LMS**. Hệ thống hỗ trợ đăng ký khóa học, theo dõi bài giảng, quản lý ví điểm/tiền và mã giảm giá voucher.

---

## ✨ Tính Năng Nổi Bật

- 📚 **Quản Lý Khóa Học & Chương Học:** Quản lý cấu trúc Khóa học -> Chương -> Bài giảng (Video, Document, Code Challenge).
- 💰 **Ví Học Viên & Nạp Tiền:** Xử lý hệ thống Ví nội bộ, nạp điểm, áp dụng Voucher giảm giá khi mua khóa học.
- ⚡ **Tối Ưu Với PL/pgSQL:** Sử dụng Stored Procedures và Trigger trong PostgreSQL để đảm bảo tính toàn vẹn dữ liệu giao dịch tài chính.
- 📈 **Báo Cáo Thống Kê Admin:** API báo cáo doanh thu theo tháng, khóa học bán chạy nhất, danh sách học viên mới.

---

## 🚀 Hướng Dẫn Chạy Machine Local

```bash
git clone https://github.com/nguyenhuynhdt37/studynest-backend-api.git
cd studynest-backend-api

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Tạo DB PostgreSQL và import file db.sql có sẵn trong repo
psql -U postgres -d studynest_db -f db.sql

# Chạy Server
uvicorn main:app --reload --port 8000
```

Swagger API Docs: `http://localhost:8000/docs`

---

## 👨‍💻 Tác Giả

**Nguyễn Xuân Huỳnh** — [GitHub Profile](https://github.com/nguyenhuynhdt37)
