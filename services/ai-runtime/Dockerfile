FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
COPY requirements-reranker.txt .
RUN pip install --no-cache-dir -r requirements.txt
ARG INSTALL_RERANKER=false
RUN if [ "$INSTALL_RERANKER" = "true" ]; then pip install --no-cache-dir -r requirements-reranker.txt; fi
COPY app ./app
COPY evals ./evals
EXPOSE 8002
CMD ["opentelemetry-instrument","uvicorn","app.main:app","--host","0.0.0.0","--port","8002"]
