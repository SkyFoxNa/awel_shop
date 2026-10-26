# shop/views.py
import asyncio
from django.http import HttpResponse, Http404
from shop.models import ProductPhoto
from utils.drive_utils import drive


def admin_drive_photo_view(request, product_code, photo_name):
    """
    Проксі-в'ю для адмінки: шукає запис фото в базі за кодом товару та назвою,
    завантажує його з Google Диска через GoogleDriveHandler та повертає браузеру.
    """
    if not drive:
        raise Http404("Google Drive не ініціалізовано.")

    # Шукаємо точний запис фото в базі даних
    try:
        # Допускаємо, що передана назва може бути без розширення або з ним
        photo_record = ProductPhoto.objects.filter(
            product_code=product_code,
            photo_name__startswith=photo_name
            .first())

        if not photo_record:
            raise Http404("Фото не знайдено в БД.")

        # Виділяємо чисту назву без розширення (як це робить бот)
        clean_name = photo_record.photo_name.split('.')[0]

        # Завантажуємо файл з Google Диска (використовуємо asyncio.to_thread для сумісності з Django)
        # Папка на диску має назву product_code (наприклад, код товару)
        file_stream = asyncio.run(
            asyncio.to_thread(drive.download_file_by_name, str(product_code), clean_name)
        )

        if not file_stream:
            raise Http404("Файл не знайдено на Google Диску.")

        # Визначаємо тип контенту (за замовчуванням зображення)
        content_type = "image/jpeg"
        if photo_record.photo_name.lower().endswith('.png'):
            content_type = "image/png"

        return HttpResponse(file_stream.read(), content_type=content_type)

    except Exception as e:
        raise Http404(f"Помилка завантаження фото: {e}")