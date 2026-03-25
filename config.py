import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Отримуємо шлях до теки, де лежить цей файл (config.py)
BASE_DIR = Path(__file__).resolve().parent

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Отримуємо URL з .env
DATABASE_URL = os.getenv("DATABASE_URL")

# Якщо використовуємо PostgreSQL від Neon (вона потребує asyncpg)
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

# Для SQLite (залишаємо для тестів)
elif DATABASE_URL and DATABASE_URL.startswith("sqlite"):
    db_file = DATABASE_URL.split("/")[-1]
    DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / db_file}"