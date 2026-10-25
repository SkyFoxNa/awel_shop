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
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() in ("true", "1", "t")

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*.koyeb.app 127.0.0.1 localhost").split()

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
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
    if "postgresql+asyncpg://" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    if "?ssl=require" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("?ssl=require", "?sslmode=require")

    # 1. Парсимо URL без зайвих параметрів у parse()
    db_config = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=0,
        conn_health_checks=True,
    )

    # 2. Додаємо OPTIONS для PostgreSQL окремо
    db_config['OPTIONS'] = {
        'options': '-c statement_timeout=30000'
    }

    DATABASES = {
        'default': db_config
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'CONN_HEALTH_CHECKS': True,
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

CSRF_TRUSTED_ORIGINS = [
    'https://*.koyeb.app',
    'https://subsequent-pig-skyhome-ee275133.koyeb.app',
]
