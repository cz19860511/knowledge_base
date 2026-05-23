FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements-kb-api.txt /app/requirements-kb-api.txt
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple \
    --trusted-host mirrors.aliyun.com \
    -r /app/requirements-kb-api.txt

COPY kb_api /app/kb_api
COPY pipeline_config.py /app/pipeline_config.py

ENV KB_ROOT_DIR=/data/kb \
    KB_BATCH_ID=batch_20260521 \
    KB_KB_ID=ai_qna_standard_v1 \
    KB_HOST=0.0.0.0 \
    KB_PORT=8080

EXPOSE 8080

CMD ["uvicorn", "kb_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
