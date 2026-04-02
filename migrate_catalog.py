import asyncio
import asyncpg
import logging
import os
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

from db.session import AsyncSessionLocal
from db.models import (
    Location, Product, ProductPhoto, ProductStock,
    ProductComponent, ProductAnalogue
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
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
            # 1. Отримуємо головну локацію
            stmt = select(Location).where(Location.name == "Склад Запоріжжя")
            result = await new_session.execute(stmt)
            main_loc = result.scalar_one_or_none()
            if not main_loc:
                main_loc = Location(name="Склад Запоріжжя")
                new_session.add(main_loc)
                await new_session.flush()

            # 2. МІГРАЦІЯ ТАРИ ТА НАЛІПОК (зі старої таблиці packages у нову products)
            logger.info("📦 Перенесення пакування та наліпок...")
            old_pkgs = await old_conn.fetch("SELECT * FROM packages")
            pkg_map = {} # Для мапінгу старого ID на новий згенерований код

            for p in old_pkgs:
                # Генеруємо код: наприклад PKG_10 або STK_5
                prefix = "STK" if p['is_sticker'] else "PKG"
                gen_code = f"{prefix}_{p['id']}"
                pkg_map[p['id']] = {"code": gen_code, "is_sticker": p['is_sticker']}

                # Додаємо як товар
                new_pkg_product = Product(
                    code=gen_code,
                    name_ua=p['name'],
                    info=p['info'],
                    is_sticker=p['is_sticker'],
                    category="Логістика"
                )
                new_session.add(new_pkg_product)

                # Додаємо залишок для цієї тари
                new_session.add(ProductStock(
                    product_code=gen_code,
                    location_id=main_loc.id,
                    price=float(p['price'] or 0),
                    balance=float(p['balance'] or 0),
                    storage_address="Склад пакування",
                    is_active=True
                ))

            # 3. МІГРАЦІЯ ОСНОВНИХ ТОВАРІВ
            logger.info("🛒 Перенесення основних товарів...")
            old_prods = await old_conn.fetch("SELECT * FROM products")
            existing_codes = set()

            for pr in old_prods:
                existing_codes.add(pr['code'])
                new_session.add(Product(
                    code=pr['code'],
                    name_ua=pr['name_ua'] or pr['name'],
                    catalog_number=pr['catalog_number'],
                    category=pr['category'],
                    url=pr['url'],
                    is_package=pr['is_package'] or False
                ))
                new_session.add(ProductStock(
                    product_code=pr['code'],
                    location_id=main_loc.id,
                    price=float(pr['price'] or 0),
                    balance=float(pr['balance'] or 0),
                    storage_address=pr['storages'],
                    is_active=True
                ))

            # 4. МІГРАЦІЯ КОМПЛЕКТАЦІЇ (ProductComponent)
            logger.info("🛠 Збірка компонентів комплектів...")
            old_comps = await old_conn.fetch("SELECT * FROM product_components")
            for c in old_comps:
                if c['product_code'] not in existing_codes:
                    continue

                # Визначаємо код компонента та прапорці
                comp_code = c['component_code']
                is_boxing = False
                is_sticker_flag = False

                # Якщо в старій базі було посилання на package_id
                if c['id_package']:
                    p_info = pkg_map.get(c['id_package'])
                    if p_info:
                        comp_code = p_info['code']
                        if p_info['is_sticker']:
                            is_sticker_flag = True
                        else:
                            is_boxing = True

                new_session.add(ProductComponent(
                    parent_code=c['product_code'],
                    component_code=comp_code,
                    quantity=float(c['quantity'] or 1),
                    is_boxing=is_boxing,
                    is_sticker=is_sticker_flag
                ))

            # --- КРОК 5: Фотографії (з захистом від "сиріт") ---
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

            await new_session.commit()
            logger.info("✨ МІГРАЦІЯ ЗАВЕРШЕНА!")

        except Exception as e:
            await new_session.rollback()
            logger.error(f"💥 Помилка: {e}", exc_info=True)
        finally:
            await old_conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())