# Сайт БРО + админка + приём заказов (tools/admin_server.py) в одном контейнере.
FROM python:3.12-slim
RUN pip install --no-cache-dir pillow==11.0.0
WORKDIR /app
RUN chown 1000:1000 /app
# владелец 1000 — как пользователь в compose.yaml: сборка пишет dist/ внутри /app
COPY --chown=1000:1000 . .
ENV BRO_ADMIN_HOST=0.0.0.0 \
    BRO_ADMIN_PORT=8100 \
    PYTHONUNBUFFERED=1
EXPOSE 8100
CMD ["python3", "tools/admin_server.py"]
