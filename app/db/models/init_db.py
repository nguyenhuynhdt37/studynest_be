from database import Base  # import Base từ ORM của bạn
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

PG_USER = "admin"
PG_PASS = "Admin1234"  # nếu pg_hba dùng trust, có thể bỏ qua mật khẩu
PG_HOST = "127.0.0.1"
PG_PORT = 5432
DB_NAME = "study_nest"

# 1) Kết nối vào DB hệ thống (postgres) để tạo DB nếu thiếu
admin_url = URL.create(
    "postgresql+psycopg2",
    username=PG_USER,
    password=PG_PASS,
    host=PG_HOST,
    port=PG_PORT,
    database="postgres",
)
admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", echo=False)

with admin_engine.connect() as conn:
    exists = conn.execute(
        text("SELECT 1 FROM pg_database WHERE datname = :d"),
        {"d": DB_NAME},
    ).scalar()
    if not exists:
        conn.execute(text(f'CREATE DATABASE "{DB_NAME}" OWNER "{PG_USER}";'))
        print(f"✅ Tạo database {DB_NAME} thành công")

# 2) Kết nối vào elearn để bật extensions + tạo schema
app_url = URL.create(
    "postgresql+psycopg2",
    username=PG_USER,
    password=PG_PASS,
    host=PG_HOST,
    port=PG_PORT,
    database=DB_NAME,
)
app_engine = create_engine(app_url, echo=True)

with app_engine.begin() as conn:  # begin() tự commit/rollback
    conn.execute(text('CREATE EXTENSION IF NOT EXISTS "vector";'))
    conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
    conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pg_trgm";'))

# 3) Tạo toàn bộ bảng từ ORM
Base.metadata.create_all(bind=app_engine)
print("🎉 Khôi phục cấu trúc cơ sở dữ liệu thành công!")
