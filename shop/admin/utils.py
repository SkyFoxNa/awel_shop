# shop/admin/utils.py
import base64
import logging
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from utils.drive_utils import drive

logger = logging.getLogger(__name__)


def get_drive_image_thumbnail(photo_name: str, product_code: str, height: int = 140) -> str:
    """
    Отримує фото з Google Диска та повертає мініатрому з автоматичною шириною (зберігає пропорції).
    """
    if not photo_name or not product_code:
        return mark_safe("— (немає назви або коду)")

    if not drive:
        return mark_safe(f"🖼 {photo_name} <br><small style='color:red;'>(Drive не ініціалізовано)</small>")

    try:
        clean_name = str(photo_name).split('.')[0]
        code_str = str(product_code)

        file_stream = drive.download_file_by_name(code_str, clean_name)

        if not file_stream:
            return mark_safe(f"🖼 {photo_name} <br><small style='color:orange;'>(Не знайдено на Диску)</small>")

        image_bytes = file_stream.read()
        encoded_image = base64.b64encode(image_bytes).decode('utf-8')

        mime_type = "image/png" if str(photo_name).lower().endswith('.png') else "image/jpeg"
        data_uri = f"data:{mime_type};base64,{encoded_image}"

        # Зафіксовано висоту (height), ширина адаптується автоматично (width: auto),
        # а max-width захищає від занадто широких фото.
        return format_html(
            '<img src="{}" style="height: {}px; width: auto; max-width: 300px; object-fit: contain; border-radius: 8px; border: 2px solid #ddd; box-shadow: 0 2px 5px rgba(0,0,0,0.1); background: #f9f9f9; padding: 2px;" />',
            data_uri, height
        )

    except Exception as e:
        logger.error(f"❌ Помилка генерації мініатюри для {product_code} / {photo_name}: {e}")
        return mark_safe(f"🖼 {photo_name} <br><small style='color:red;'>(Помилка)</small>")