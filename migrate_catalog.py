import asyncio
import asyncpg
import logging
import os
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

# Імпортуємо ваші налаштування та моделі
from db.session import AsyncSessionLocal
from db.models import (
    Location, Product, ProductPhoto, ProductStock,
    Package, PackageStock, ProductComponent, ProductAnalogue
)

# Завантажуємо змінні з .env
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate():
    # 1. Підключення до старої бази (дані з .env)
    try:
        old_conn = await asyncpg.connect(
            user=os.getenv('OLD_DB_USER'),
            password=os.getenv('OLD_DB_PASSWORD'),
            database=os.getenv('OLD_DB_NAME'),
            host=os.getenv('OLD_DB_HOST'),
            port=os.getenv('OLD_DB_PORT', 5432)
        )
        logger.info("✅ Підключено до старої бази даних.")
    except Exception as e:
        logger.error(f"❌ Помилка підключення до старої БД: {e}")
        return

    async with AsyncSessionLocal() as new_session:
        try:
            # --- КРОК 1: Локація (Склад Запоріжжя) ---
            logger.info("Пошук локації 'Склад Запоріжжя'...")
            stmt = select(Location).where(Location.name == "Склад Запоріжжя")
            result = await new_session.execute(stmt)
            main_loc = result.scalar_one_or_none()

            if not main_loc:
                logger.info("Локацію не знайдено, створюємо нову...")
                main_loc = Location(name="Склад Запоріжжя")
                new_session.add(main_loc)
                await new_session.flush()
            else:
                logger.info(f"Використовуємо існуючу локацію ID: {main_loc.id}")

            # --- КРОК 2: Пакування (packages) ---
            logger.info("Перенесення пакування...")
            old_pkgs = await old_conn.fetch("SELECT * FROM packages")
            pkg_id_map = {}  # Словник для зв'язку старого ID з новим

            for p in old_pkgs:
                new_pkg = Package(
                    name=p['name'],
                    info=p['info'],
                    price=float(p['price'] or 0),
                    is_sticker=p['is_sticker']
                )
                new_session.add(new_pkg)
                await new_session.flush()
                pkg_id_map[p['id']] = new_pkg.id

                # Додаємо залишок пакування на склад
                new_session.add(PackageStock(
                    package_id=new_pkg.id,
                    location_id=main_loc.id,
                    balance=float(p['balance'] or 0)
                ))

            # --- КРОК 3: Товари та Залишки ---
            logger.info("Перенесення товарів та залишків...")
            old_prods = await old_conn.fetch("SELECT * FROM products")
            existing_codes = set()  # Для перевірки Foreign Keys на наступних кроках

            for pr in old_prods:
                existing_codes.add(pr['code'])

                # Основна картка
                new_p = Product(
                    code=pr['code'],
                    name_ua=pr['name_ua'] or pr['name'],
                    catalog_number=pr['catalog_number'],
                    category=pr['category'],
                    url=pr['url'],
                    is_package=pr['is_package'] or False
                )
                new_session.add(new_p)

                # Створюємо запис у ProductStock (неупакований за замовчуванням)
                new_session.add(ProductStock(
                    product_code=pr['code'],
                    location_id=main_loc.id,
                    price=float(pr['price'] or 0),
                    balance=float(pr['balance'] or 0),
                    storage_address=pr['storages'],
                    is_packed=False,
                    min_balance=0.0,  # Поки що нуль, налаштуєте пізніше
                    is_active=True
                ))

                # Аналоги (якщо є в колонці analogues через кому)
                if pr.get('analogues'):
                    codes = [c.strip() for c in pr['analogues'].split(',') if c.strip()]
                    for a_code in codes:
                        new_session.add(ProductAnalogue(
                            product_code=pr['code'],
                            analogue_code=a_code
                        ))

            # --- КРОК 4: Фотографії (з захистом від "сиріт") ---
            logger.info("Перенесення фотографій...")
            old_photos = await old_conn.fetch("SELECT * FROM photo_tg")
            for ph in old_photos:
                if ph['code'] not in existing_codes:
                    logger.warning(f"⚠️ Товар {ph['code']} відсутній. Фото {ph['photo']} пропущено.")
                    continue

                order = 0
                try:
                    if "_" in ph['photo']:
                        order = int(ph['photo'].split("_")[-1].split(".")[0])
                except:
                    pass

                new_session.add(ProductPhoto(
                    product_code=ph['code'],
                    photo_name=ph['photo'],
                    file_path=ph['put_photo'],
                    tg_file_id=ph['id_tg'],
                    display_order=order
                ))

            # --- КРОК 5: Комплекти ---
            logger.info("Перенесення компонентів комплектів...")
            old_comps = await old_conn.fetch("SELECT * FROM product_components")
            for c in old_comps:
                if c['product_code'] not in existing_codes:
                    continue

                new_session.add(ProductComponent(
                    parent_code=c['product_code'],
                    component_code=c['component_code'],
                    quantity=float(c['quantity'] or 1),
                    is_sticker=c['is_sticker'],
                    package_id=pkg_id_map.get(c['id_package'])  # Мапінг ID пакування
                ))

            # Фінальний коміт
            await new_session.commit()
            logger.info("✨ МІГРАЦІЯ ЗАВЕРШЕНА УСПІШНО!")

        except Exception as e:
            await new_session.rollback()
            logger.error(f"💥 Помилка під час міграції: {e}", exc_info=True)
        finally:
            await old_conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())