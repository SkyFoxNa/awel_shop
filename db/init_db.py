import logging
from sqlalchemy import select
from db.models import Base, Role, Location
from db.session import engine, AsyncSessionLocal

async def init_db():
    async with engine.begin() as conn:
        # ОБЕРЕЖНО: drop_all видаляє всі дані при кожному запуску!
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