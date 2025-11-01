# Cách 1: gọi qua module (chắc chắn dùng đúng python trong venv)

python -m sqlacodegen postgresql+psycopg://huynh:Huynh2004@localhost:5432/elearn --schema public --outfile app/db/models/database.py
