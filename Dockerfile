FROM python:3.13-slim

# Встановлюємо системні залежності для PostgreSQL та роботи з зображеннями
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копіюємо файл залежностей
COPY requirements.txt .

# Оновлюємо pip та встановлюємо пакети
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копіюємо увесь код проєкту
COPY . .

# Команда за замовчуванням (Koyeb може її перевизначити через Run Command)
CMD ["sh", "-c", "gunicorn config.wsgi:application --workers 1 --bind 0.0.0.0:${PORT:-8000}"]