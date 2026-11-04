FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
RUN groupadd -g 10001 minimo && useradd -u 10001 -g minimo -s /usr/sbin/nologin minimo
COPY services/python/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY services/python/minimo /app/minimo
RUN mkdir -p /data && chown -R minimo:minimo /data
USER minimo
EXPOSE 8001
CMD ["uvicorn","minimo.app:app","--host","0.0.0.0","--port","8001","--workers","1"]
