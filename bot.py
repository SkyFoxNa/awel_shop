import os
import asyncio
import logging
from dotenv import load_dotenv

# 1. Завантажуємо .env змінні
load_dotenv()

# 2. Ініціалізація Django ПЕРЕД імпортом aiogram та моделей
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

# 3. Тепер імпортуємо aiogram, роутери та мідлварі
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from handlers import routers
from middlewares.error_middleware import ErrorMiddleware
from middlewares.user_middleware import UserMiddleware
# from utils.scheduler import setup_scheduler

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)


async def main():
    # 1. Ініціалізуємо бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )

    dp = Dispatcher()

    # 2. Реєструємо Middleware
    # dp.update.middleware(ErrorMiddleware())  # Ловить помилки
    dp.update.middleware(UserMiddleware())     # Створення/перевірка юзера у Django ORM

    # 3. Підключаємо роутери
    for r in routers:
        dp.include_router(r)

    # 4. Шедулер (залишаємо на майбутнє)
    # setup_scheduler(bot)

    # 5. Цикл стабільності 24/7
    while True:
        try:
            logging.info("🚀 Бот AWEL Shop успішно запущений (Django ORM)...")
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        except Exception as e:
            logging.critical(f"Критична помилка, рестарт через 10 сек: {e}")
            await bot.session.close()
            await asyncio.sleep(10)
            bot = Bot(
                token=BOT_TOKEN,
                default=DefaultBotProperties(parse_mode="HTML")
            )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот вимкнений")