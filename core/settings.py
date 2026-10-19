import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# Завантаження змінних оточення з .env
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Безпека
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-change-me-in-production')
DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['*']  # На Koyeb можна буде звузити до вашого домену

# Список додатків
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Ваш додаток для моделей та адмінки
    'shop',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise для роздачі статики на Koyeb (опціонально, але корисно):
    # 'whitenoise.middleware.WhiteNoiseMiddleware', 
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# База даних (Neon PostgreSQL через DATABASE_URL)
# dj_database_url автоматично перетворить postgresql+asyncpg:// в потрібний формат для Django
# core/settings.py

# core/settings.py

DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # 1. Замінюємо асинхронний драйвер на стандартний для Django
    if "postgresql+asyncpg://" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    # 2. Замінюємо ?ssl=require на ?sslmode=require для psycopg2
    if "?ssl=require" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("?ssl=require", "?sslmode=require")

    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            # ssl_require НЕ передаємо окремим параметром,
            # оскільки sslmode вже є в самому URL
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Валідація паролів
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Локалізація та Часовий пояс
LANGUAGE_CODE = 'uk'  # Встановлюємо українську мову для адмінки

TIME_ZONE = os.getenv('TIME_ZONE', 'Europe/Kyiv')

USE_I18N = True
USE_TZ = True

# Статичні файли (CSS, JavaScript, Зображення)
STATIC_URL = 'static/'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'