#!/bin/bash
# Script để tự động sinh ra models SQLAlchemy từ database hiện tại

echo "🚀 Đang kết nối tới database tại 127.0.0.1:5433..."

# Chạy sqlacodegen với dấu nháy đơn bao quanh URL để tránh lỗi zsh với ký tự '!'
./.venv/bin/python -m sqlacodegen 'postgresql://admin:StrongPass2026!@127.0.0.1:5433/studynest' --schema public --outfile app/db/models/database.py

if [ $? -eq 0 ]; then
    echo "✅ Thành công! Đã cập nhật file: app/db/models/database.py"
else
    echo "❌ Thất bại! Vui lòng kiểm tra xem Docker database đã chạy chưa (docker-compose up -d)"
fi
