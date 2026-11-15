# utils/drive_utils.py
import os
import io
import json
import logging
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

load_dotenv()

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive']
PARENT_FOLDER_ID = os.getenv("PARENT_FOLDER_ID")

# Визначаємо кореневу папку проєкту на основі розташування цього файлу (utils/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
LOCAL_JSON_PATH = os.path.join(ROOT_DIR, "service_account.json")


class GoogleDriveHandler:
    def __init__(self):
        self.creds = None

        # 1. Шукаємо JSON у змінній середовища (для Koyeb / продакшену)
        google_creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

        if google_creds_json:
            try:
                creds_dict = json.loads(google_creds_json)
                self.creds = service_account.Credentials.from_service_account_info(
                    creds_dict, scopes=SCOPES
                )
            except Exception as e:
                logger.error(f"❌ Помилка парсингу GOOGLE_SERVICE_ACCOUNT_JSON: {e}")

        # 2. Якщо змінної немає, перевіряємо абсолютний шлях до service_account.json у корені
        elif os.path.exists(LOCAL_JSON_PATH):
            try:
                self.creds = service_account.Credentials.from_service_account_file(
                    LOCAL_JSON_PATH, scopes=SCOPES
                )
            except Exception as e:
                logger.error(f"❌ Помилка завантаження service_account.json: {e}")

        if not self.creds:
            raise ValueError(
                f"Не вдалося ініціалізувати Google Drive: відсутні дані сервісного акаунта "
                f"(не знайдено GOOGLE_SERVICE_ACCOUNT_JSON або файл за шляхом {LOCAL_JSON_PATH})"
            )

        self.service = build('drive', 'v3', credentials=self.creds)
        self.photo_folder_id = self._get_or_create_folder("Photo", PARENT_FOLDER_ID)

    def _get_or_create_folder(self, folder_name, parent_id):
        """Шукає або створює папку на Диску"""
        if not parent_id:
            return None
        query = f"name='{folder_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = self.service.files().list(q=query).execute()
        files = results.get('files', [])
        if files:
            return files[0]['id']

        meta = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
        return self.service.files().create(body=meta, fields='id').execute().get('id')

    def download_file_by_name(self, folder_name, file_name):
        """
        Шукає файл у папці товару, який містить file_name.
        Дозволяє знайти зображення без обов'язкового розширення в запиті.
        """
        try:
            if not self.photo_folder_id:
                return None

            subfolder_id = self._get_or_create_folder(folder_name, self.photo_folder_id)
            if not subfolder_id:
                return None

            query = f"name contains '{file_name}' and '{subfolder_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                fields="files(id, name, mimeType)",
                pageSize=1
            ).execute()

            files = results.get('files', [])

            if not files:
                logger.info(f"📭 Файл {file_name} не знайдено в папці {folder_name} на Диску.")
                return None

            target_file = files[0]
            logger.info(f"✅ Знайдено файл на Диску: {target_file['name']} (ID: {target_file['id']})")

            request = self.service.files().get_media(fileId=target_file['id'])
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            fh.seek(0)
            return fh
        except Exception as e:
            logger.error(f"❌ Помилка завантаження з Диска: {e}")
            return None


# Безпечна ініціалізація єдиного екземпляра
# --- Безпечна ініціалізація єдиного екземпляра ---
class DummyDriveHandler:
    """Заглушка, щоб бот не падав, якщо Google Drive не налаштовано"""
    def download_file_by_name(self, folder_name, file_name):
        logger.warning(f"⚠️ Спроба завантажити файл {file_name}, але Google Drive не ініціалізовано.")
        return None

drive = None
try:
    drive = GoogleDriveHandler()
except Exception as e:
    logger.warning(f"⚠️ Google Drive не ініціалізовано ({e}). Використовується заглушка.")
    drive = DummyDriveHandler()