FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/services/event-consumer
COPY services/event-consumer/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY services/event-consumer/app.py services/event-consumer/db_config.py services/event-consumer/event_contract.py ./
COPY packages/contracts/events/ /app/packages/contracts/events/
USER 10001:10001
EXPOSE 8092
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8092"]
