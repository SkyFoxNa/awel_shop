import os
import io
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

load_dotenv()

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
                    print(f"🔄 Помилка оновлення токена: {e}. Видаляємо старий токен...")
                    if os.path.exists(TOKEN_FILE):
                        os.remove(TOKEN_FILE)
                    # Запускаємо авторизацію заново
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    self.creds = flow.run_local_server(port=0)

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
        Шукає файл у папці товару, який починається на file_name.
        Це дозволяє знайти '12345.jpg' або '12345.png', шукаючи просто '12345'.
        """
        try:
            # 1. Отримуємо ID папки товару (наприклад, "1339000")
            subfolder_id = self._get_or_create_folder(folder_name, self.photo_folder_id)

            # 2. Шукаємо файли, назва яких починається з нашого імені
            # Використовуємо 'contains', бо Google Drive API не завжди стабільно перетравлює розширення
            query = f"name contains '{file_name}' and '{subfolder_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                fields="files(id, name, mimeType)",
                pageSize=1  # Нам потрібен лише один, перший ліпший варіант
            ).execute()

            files = results.get('files', [])

            if not files:
                print(f"📭 Файл {file_name} не знайдено в папці {folder_name} на Диску.")
                return None

            # 3. Беремо ID знайденого файлу
            target_file = files[0]
            print(f"✅ Знайдено файл на Диску: {target_file['name']} (ID: {target_file['id']})")

            request = self.service.files().get_media(fileId=target_file['id'])
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            fh.seek(0)
            return fh
        except Exception as e:
            print(f"❌ Помилка завантаження з Диска: {e}")
            return None


# Ініціалізація
drive = None
try:
    drive = GoogleDriveHandler()
except Exception as e:
    print(f"⚠️ Google Drive не ініціалізовано: {e}")