import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from aiogram.client.default import DefaultBotProperties
from db.session import AsyncSessionLocal, engine
from db.middleware import DbSessionMiddleware
from middlewares.error_middleware import ErrorMiddleware
from db.init_db import init_db
from handlers import routers
from middlewares.user_middleware import UserMiddleware

# from utils.scheduler import setup_scheduler

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)

async def main():
    # 1. Створюємо/оновлюємо структуру бази даних
    await init_db()

    # 2. Ініціалізуємо бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )

    dp = Dispatcher()

    dp["session_pool"] = AsyncSessionLocal

    # 3. Реєструємо Middleware (важливий порядок!)
    # dp.update.middleware(ErrorMiddleware())            # Ловить помилки
    dp.update.middleware(DbSessionMiddleware(AsyncSessionLocal)) # Дає сесію БД
    dp.update.middleware(UserMiddleware())

    # 4. Підключаємо роутери
    for r in routers:
        dp.include_router(r)

    # 5. Шедулер (залишаємо на майбутнє)
    # setup_scheduler(bot, AsyncSessionLocal)

    # 6. Цикл стабільності 24/7
    while True:
        try:
            logging.info("Бот AWEL Shop запускається...")
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        except Exception as e:
            logging.critical(f"Критична помилка, рестарт через 10 сек: {e}")
            await bot.session.close()
            await asyncio.sleep(10)
            # bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
            bot = Bot(
                token=BOT_TOKEN,
                default=DefaultBotProperties(parse_mode="HTML")
            )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот вимкнений")