import logging
from sqlalchemy import select, text
from db.models import Base, Role, Location
from db.session import engine, AsyncSessionLocal

async def init_db():
    async with engine.begin() as conn:
        # ОБЕРЕЖНО: drop_all видаляє всі дані при кожному запуску!
        # async with engine.begin() as conn:
        #     # 1. Примусово видаляємо всі таблиці через CASCADE
        #     # Отримуємо імена всіх таблиць, що зараз є в метаданих
        #     for table in reversed(Base.metadata.sorted_tables):
        #         await conn.execute(text(f'DROP TABLE IF EXISTS "{table.name}" CASCADE;'))
        #
        #     # 2. Якщо в базі залишилися старі таблиці, яких немає в моделях (як package_stock)
        #     # Можна додати їх видалення вручну:
        #     await conn.execute(text('DROP TABLE IF EXISTS "package_stock" CASCADE;'))
        #     await conn.execute(text('DROP TABLE IF EXISTS "packages" CASCADE;'))
        #
        #     # 3. Створюємо все заново
        #     # await conn.run_sync(Base.metadata.drop_all) # Це можна тепер не викликати
        #     await conn.run_sync(Base.metadata.create_all)
        # await conn.run_sync(Base.metadata.drop_all) #-- тільки для тестів

        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Список ролей як "Словник": Ім'я -> Опис
        base_roles = {
            "admin": "Адміністратор",
            "owner": "Власник бізнесу",
            "manager": "Менеджер",
            "creator": "Content Creator",
            "seller": "Продавець-консультант",
            "pro_client": "Покупець (Склад + Магазин)",
            "client": "Покупець",
            "warehouse": "Робітник складу"
        }

        for r_name, r_desc in base_roles.items():
            stmt = select(Role).where(Role.name == r_name)
            res = await session.execute(stmt)
            if not res.scalar_one_or_none():
                session.add(Role(name=r_name, description=r_desc))
                logging.info(f"Додано роль: {r_name}")

        # Локації
        for l_name in ["Склад Запоріжжя", "Автокрамниця", "Магазин Запоріжжя"]:
            stmt = select(Location).where(Location.name == l_name)
            if not (await session.execute(stmt)).scalar_one_or_none():
                session.add(Location(name=l_name))

        await session.commit()