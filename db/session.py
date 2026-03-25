from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from config import DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,  # ПЕРЕВІРКА: перед кожним запитом перевіряє, чи живе з'єднання
    pool_recycle=300,    # ПЕРЕЗАПУСК: оновлює з'єднання кожні 5 хвилин
    pool_size=5,         # Кількість одночасних підключень
    max_overflow=10      # Додаткові підключення при навантаженні
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)