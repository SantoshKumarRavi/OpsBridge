"""Idempotent Kafka-to-PostgreSQL event projection lab."""
from __future__ import annotations

import json
import hashlib
import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import psycopg
from confluent_kafka import Consumer, KafkaError, KafkaException, Producer
from fastapi import FastAPI
from psycopg.types.json import Jsonb
from event_contract import safe_summary, schema_version_for_topic, validate_event
from db_config import connection_kwargs

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("opsbridge.event-consumer")
KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "opsbridge-case-projection-v1")
DATABASE_CONFIG = connection_kwargs(os.environ)
stop_event = threading.Event()
consumer_thread: threading.Thread | None = None


def ensure_schema() -> None:
    with psycopg.connect(**DATABASE_CONFIG) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS consumed_domain_events (
                event_id text PRIMARY KEY,
                event_type text NOT NULL,
                tenant_id text NOT NULL,
                aggregate_id text,
                occurred_at timestamptz,
                summary jsonb NOT NULL DEFAULT '{}'::jsonb,
                schema_version integer NOT NULL DEFAULT 1,
                consumed_at timestamptz NOT NULL DEFAULT now()
            )"""
        )
        connection.execute(
            "ALTER TABLE consumed_domain_events ADD COLUMN IF NOT EXISTS "
            "schema_version integer NOT NULL DEFAULT 1"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS consumed_domain_events_tenant_time_idx "
            "ON consumed_domain_events (tenant_id, consumed_at DESC)"
        )


def persist(event: dict, schema_version: int) -> None:
    event_id = str(event["eventId"])
    event_type = str(event["eventType"])
    tenant_id = str(event["tenantId"])
    aggregate_id = str(event.get("caseId") or "")
    occurred_raw = event.get("occurredAt")
    occurred_at = datetime.fromisoformat(str(occurred_raw).replace("Z", "+00:00")) if occurred_raw else None
    if occurred_at and occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)

    # The DB transaction commits before the caller commits the Kafka offset.
    # Redelivery after a crash is safe because event_id is the primary key.
    with psycopg.connect(**DATABASE_CONFIG) as connection:
        connection.execute(
            """INSERT INTO consumed_domain_events
               (event_id, event_type, tenant_id, aggregate_id, occurred_at, summary, schema_version)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (event_id) DO NOTHING""",
            (event_id, event_type, tenant_id, aggregate_id, occurred_at, Jsonb(safe_summary(event)), schema_version),
        )


def dead_letter(producer: Producer, message, reason: str) -> None:
    delivery_errors = []
    source_key = f"{message.topic()}:{message.partition()}:{message.offset()}"
    raw = message.value() or b""
    raw_bytes = raw if isinstance(raw, bytes) else str(raw).encode("utf-8", "replace")
    diagnostic = json.dumps({
        "sourceTopic": message.topic(),
        "sourcePartition": message.partition(),
        "sourceOffset": message.offset(),
        "rawSha256": hashlib.sha256(raw_bytes).hexdigest(),
        "rawByteLength": len(raw_bytes),
        "reason": reason[:300],
    }).encode("utf-8")
    producer.produce(
        "opsbridge.consumer.dlq.v1",
        key=source_key,
        value=diagnostic,
        headers={
            "source-topic": message.topic(),
            "source-partition": str(message.partition()),
            "source-offset": str(message.offset()),
            "failure-reason": reason[:300],
        },
        on_delivery=lambda error, _message: delivery_errors.append(error),
    )
    remaining = producer.flush(10)
    if remaining or not delivery_errors or delivery_errors[0] is not None:
        raise RuntimeError("Dead-letter publish was not confirmed; source offset remains uncommitted")


def consume_loop() -> None:
    consumer = Consumer({
        "bootstrap.servers": KAFKA_SERVERS,
        "security.protocol": os.getenv("KAFKA_SECURITY_PROTOCOL", "plaintext"),
        "group.id": GROUP_ID,
        "enable.auto.commit": False,
        "enable.auto.offset.store": False,
        "auto.offset.reset": "earliest",
    })
    producer = Producer({"bootstrap.servers": KAFKA_SERVERS, "security.protocol": os.getenv("KAFKA_SECURITY_PROTOCOL", "plaintext"), "enable.idempotence": True, "acks": "all"})
    consumer.subscribe(["opsbridge.domain.v1", "opsbridge.domain.v2", "opsbridge.external.v1"])
    try:
        while not stop_event.is_set():
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                if message.error().code() != KafkaError._PARTITION_EOF:
                    logger.error("Kafka consumer error: %s", message.error())
                continue
            while not stop_event.is_set():
                try:
                    event = validate_event(json.loads(message.value()), message.topic())
                    persist(event, schema_version_for_topic(message.topic()))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    logger.warning("Sending invalid event to DLQ from %s[%s]@%s", message.topic(), message.partition(), message.offset())
                    try:
                        dead_letter(producer, message, str(exc))
                    except Exception:
                        logger.exception("DLQ publish failed; source message will be retried")
                        stop_event.wait(2)
                        continue
                except Exception:
                    # Retry this same message before polling any later offsets.
                    # Persist is idempotent, so this also handles an uncertain
                    # DB commit outcome without skipping ahead in the partition.
                    logger.exception("Event processing failed at %s[%s]@%s; retrying", message.topic(), message.partition(), message.offset())
                    stop_event.wait(2)
                    continue
                try:
                    consumer.commit(message=message, asynchronous=False)
                    break
                except Exception:
                    logger.exception("Offset commit failed; source message will be retried idempotently")
                    stop_event.wait(2)
    except KafkaException:
        logger.exception("Kafka consumer stopped after a client error")
    finally:
        consumer.close()
        producer.flush(10)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global consumer_thread
    ensure_schema()
    stop_event.clear()
    consumer_thread = threading.Thread(target=consume_loop, name="kafka-projection-consumer", daemon=True)
    consumer_thread.start()
    yield
    stop_event.set()
    if consumer_thread:
        consumer_thread.join(timeout=10)


app = FastAPI(title="OpsBridge Event Consumer Lab", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str | bool]:
    running = bool(consumer_thread and consumer_thread.is_alive())
    return {"status": "ok" if running else "degraded", "service": "event-consumer", "consumerRunning": running}
