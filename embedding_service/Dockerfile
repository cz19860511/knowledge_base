FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements-embedding-service.txt /app/requirements-embedding-service.txt
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple \
    --trusted-host mirrors.aliyun.com \
    -r /app/requirements-embedding-service.txt

COPY embedding_service /app/embedding_service

ENV KB_EMBEDDING_PROVIDER=transformers \
    KB_EMBEDDING_MODEL_PATH=/data/kb/models/bge-small-zh-v1.5 \
    KB_EMBEDDING_MODEL_NAME=bge-small-zh-v1.5 \
    KB_EMBEDDING_HOST=0.0.0.0 \
    KB_EMBEDDING_PORT=9100

EXPOSE 9100

CMD ["uvicorn", "embedding_service.main:app", "--host", "0.0.0.0", "--port", "9100"]
