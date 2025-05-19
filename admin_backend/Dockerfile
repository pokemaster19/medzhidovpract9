FROM python:3.9-slim

WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем файлы приложения
COPY main.py .
COPY docker_main.py .

# Создаем необходимые директории
RUN mkdir -p /app/data
RUN mkdir -p /app/public/admin
RUN mkdir -p /app/docs

# Открываем порт
EXPOSE 8081

# Команда запуска приложения
CMD ["uvicorn", "docker_main:app", "--host", "0.0.0.0", "--port", "8081"]