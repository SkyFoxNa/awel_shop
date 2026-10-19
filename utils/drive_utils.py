import os
import io
import logging
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

load_dotenv()

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'
PARENT_FOLDER_ID = os.getenv("PARENT_FOLDER_ID")


class GoogleDriveHandler:
    def __init__(self):
        self.creds = None
        if os.path.exists(TOKEN_FILE):
            self.creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    logger.error(f"🔄 Помилка оновлення токена Google Drive: {e}")
                    if os.path.exists(TOKEN_FILE):
                        os.remove(TOKEN_FILE)

                    if os.path.exists(CREDENTIALS_FILE):
                        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                        self.creds = flow.run_local_server(port=0)
            elif os.path.exists(CREDENTIALS_FILE):
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                self.creds = flow.run_local_server(port=0)

        if not self.creds:
            raise ValueError("Не вдалося ініціалізувати Google Drive: відсутній токен або credentials.json")

        self.service = build('drive', 'v3', credentials=self.creds)
        self.photo_folder_id = self._get_or_create_folder("Photo", PARENT_FOLDER_ID)

    def _get_or_create_folder(self, folder_name, parent_id):
        """Шукає або створює папку на Диску"""
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
            subfolder_id = self._get_or_create_folder(folder_name, self.photo_folder_id)

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


# Ініціалізація
drive = None
try:
    drive = GoogleDriveHandler()
except Exception as e:
    logger.warning(f"⚠️ Google Drive не ініціалізовано: {e}")
