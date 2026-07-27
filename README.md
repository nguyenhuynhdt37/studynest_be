# 🧠 StudyNest LMS Backend API - Hệ Thống Quản Lý Học Tập

![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)

Backend REST API cốt lõi cho hệ thống **StudyNest LMS**, xử lý quản lý học viên, khóa học, video bài giảng, hệ thống nạp tiền/ví điện tử và mã giảm giá.

---

## ✨ Tính Năng Nổi Bật

- 🔐 **Xác thực Auth:** JWT Access Token & Refresh Token, mã hóa Bcrypt.
- 📚 **Quản lý Khóa học:** CRUD Khóa học, Chương học, Bài giảng (Video/Văn bản/Code).
- 💰 **Ví & Nạp Tiền:** Xử lý nạp điểm/tiền vào tài khoản học viên, quản lý mã voucher/discount.
- 📈 **Thống Kê Admin:** API báo cáo doanh thu, số lượng học viên đăng ký, tiến độ học tập.

---

## 🚀 Khởi Chạy Backend

```bash
git clone https://github.com/nguyenhuynhdt37/studynest-backend-api.git
cd studynest-backend-api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

---

## 👨‍💻 Tác Giả

**Nguyễn Xuân Huỳnh** — [GitHub Profile](https://github.com/nguyenhuynhdt37)
