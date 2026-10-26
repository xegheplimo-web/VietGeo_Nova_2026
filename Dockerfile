FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 VIETGEO_CONTAINER=1 VIETGEO_DB=/runtime/vietgeo.sqlite3
COPY vietgeo/ ./vietgeo/
COPY web/ ./web/
COPY tools/ ./tools/
COPY data/provinces_34.json ./data/provinces_34.json
RUN mkdir -p /runtime
EXPOSE 8765
CMD ["python","-m","vietgeo.server","--host","0.0.0.0","--port","8765"]
