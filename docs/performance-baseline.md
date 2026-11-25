# Local API load baseline

## Recorded run

The first repeatable Locust baseline ran on 2026-11-20 against the local Express gateway and Django REST API, using a temporary SQLite database and 30 synthetic cases.

| Setting or result | Value |
|---|---:|
| Locust users | 5 |
| Run time | 15 seconds |
| Requests | 50 |
| Failures | 0 |
| Average response time | 9 ms |
| Median response time | 8 ms |
| 95th percentile | 14 ms |
| Maximum response time | 21 ms |
| Throughput | 3.42 requests/second |

The authoritative run summary is [`baseline.json`](../tests/performance/results/locust-20261120T041802.134769Z/baseline.json); the Locust CSV files are alongside it. The JSON records Locust 2.47.0, Python 3.13.3, and the exact run configuration.

## k6 run

A separate k6 run used the same temporary API, seed size, five concurrent users, and 15-second duration. It recorded 75 GET requests, no failures, 16.93 ms average response time, and 38.75 ms p95. The configured k6 thresholds passed: HTTP and application error rates under 1%, and p95 under 750 ms.

The normalized result is [`baseline.json`](../tests/performance/results/k6-20261120T042820.844909Z/baseline.json); the native `k6-summary.json` and full `console.log` are in the same directory. This machine ran k6 v1.2.3. Install k6 with the [official Grafana Windows instructions](https://grafana.com/docs/k6/latest/set-up/install-k6/), then reproduce with `npm run test:load:k6`.

## JMeter run

Apache JMeter 5.6.3 ran the checked-in test plan with five threads and ten loops per thread: 50 GET requests, no failures, 19.38 ms average response time, and 24 ms p95. The normalized summary, JTL sample data, and console log are in [`tests/performance/results/jmeter-20261120T043322.328219Z/`](../tests/performance/results/jmeter-20261120T043322.328219Z/). Reproduce with `npm run test:load:jmeter` after installing JMeter and Java.

## How to reproduce

Install the performance dependency and run:

```powershell
python -m pip install -r tests/performance/requirements.txt
npm run test:load:locust
```

The runner starts disposable Django and Express processes, creates the SQLite database, checks the gateway contract, seeds cases, and runs Locust. Each run writes a timestamped JSON summary and CSV files under `tests/performance/results/`. `LOAD_SEED_CASES`, `LOCUST_USERS`, `LOCUST_SPAWN_RATE`, and `LOCUST_RUN_TIME` can tune the load.

## Limits

These are low-volume development baselines on the local Windows workstation. They use SQLite and the gateway's in-memory rate limiter, and the Locust and k6 numbers should not be compared directly because their runtimes and measurement methods differ. They do not measure PostgreSQL, Redis-backed rate limiting, RabbitMQ, a separately deployed worker, production hardware, or sustained capacity. Repeat runs in a controlled environment before comparing changes or setting production performance targets. Locust periodically flushes its CSV files, so the JSON summary captures the final aggregate printed by the runner and is authoritative when the CSV request total differs slightly.
