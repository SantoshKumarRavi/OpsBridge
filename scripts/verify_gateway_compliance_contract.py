"""Run the Express gateway against the real Django API without Docker."""

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import csv
import json
import math
import platform
import re
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

import httpx
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate_spec
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


ROOT = Path(__file__).resolve().parents[1]
COMPLIANCE_DIR = ROOT / "services" / "compliance-api"
GATEWAY_DIR = ROOT / "services" / "api-gateway"
OPENAPI_PATH = ROOT / "packages" / "contracts" / "openapi.yaml"
MOCK_AI_CALLS = []


class MockAIHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        request_body = json.loads(self.rfile.read(size) or b"{}")
        MOCK_AI_CALLS.append(
            {
                "path": self.path,
                "tenant_id": self.headers.get("X-Tenant-Id"),
                "correlation_id": self.headers.get("X-Correlation-Id"),
                "request": request_body,
            }
        )
        if self.path == "/v1/extract":
            response_body = {
                "fields": {"name": "Example Worker", "document_number": "DEMO-0001"},
                "confidence": 0.42,
                "warnings": ["Synthetic fixture requires a human review."],
                "human_review_required": True,
            }
        elif self.path == "/v1/recommend":
            response_body = {
                "suggested_next_step": "request_changes",
                "human_decision_required": True,
                "policy_sources": ["synthetic-onboarding-policy"],
                "rationale": "Synthetic test response; a human reviewer must decide.",
            }
        else:
            response_body = {"error": "Unknown mock AI route."}
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            encoded = json.dumps(response_body).encode("utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        encoded = json.dumps(response_body).encode("utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format, *_args):
        return


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_for_health(url, process, log_path, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Service exited early. Logs: {log_path}\n{log_path.read_text(errors='replace')[-6000:]}")
        try:
            response = httpx.get(url, timeout=1)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise TimeoutError(f"Service did not become healthy: {url}\n{log_path.read_text(errors='replace')[-6000:]}")


def validate_response(spec, path, method, status_code, body):
    response = spec["paths"][path][method]["responses"][str(status_code)]
    schema = response["content"]["application/json"]["schema"]
    registry = Registry().with_resource(
        "https://opsbridge.local/openapi.yaml",
        Resource.from_contents(spec, default_specification=DRAFT202012),
    )
    Draft202012Validator(
        schema,
        registry=registry,
        _resolver=registry.resolver("https://opsbridge.local/openapi.yaml"),
        format_checker=FormatChecker(),
    ).validate(body)


def assert_private_no_store(response):
    cache_control = response.headers.get("Cache-Control", "").lower()
    assert "private" in cache_control and "no-store" in cache_control, {
        "status": response.status_code,
        "cache_control": cache_control,
    }


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def seed_load_cases(gateway_base, env, client):
    seed_count = int(env.get("LOAD_SEED_CASES", "30"))
    tenant_id = env.get("TENANT_ID", "load-test-tenant")
    headers = {"X-Tenant-Id": tenant_id}
    for index in range(seed_count):
        response = client.post(
            f"{gateway_base}/api/v1/cases",
            headers=headers,
            json={
                "workerName": f"Synthetic Load Worker {index + 1}",
                "email": f"load-{index + 1}@example.invalid",
                "role": "Performance Test Fixture",
                "country": "US",
            },
        )
        if response.status_code != 201:
            raise RuntimeError(f"Could not seed load case {index + 1}/{seed_count}: {response.status_code} {response.text}")
    return seed_count, tenant_id


def run_locust_load(gateway_base, env, client):
    seed_count, tenant_id = seed_load_cases(gateway_base, env, client)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    result_dir = ROOT / "tests" / "performance" / "results" / f"locust-{timestamp}"
    result_dir.mkdir(parents=True, exist_ok=False)
    load_env = env.copy()
    load_env.update({"API_URL": f"{gateway_base}/api/v1", "TENANT_ID": tenant_id})
    load_env.pop("API_TOKEN", None)
    command = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        str(ROOT / "tests" / "performance" / "locustfile.py"),
        "--headless",
        "--only-summary",
        "--host",
        f"{gateway_base}/api/v1",
        "--users",
        env.get("LOCUST_USERS", "5"),
        "--spawn-rate",
        env.get("LOCUST_SPAWN_RATE", "1"),
        "--run-time",
        env.get("LOCUST_RUN_TIME", "15s"),
        "--csv",
        str(result_dir / "cases"),
    ]
    print(f"Running Locust against disposable SQLite API with {seed_count} synthetic cases; results: {result_dir}")
    result = subprocess.run(command, cwd=ROOT, env=load_env, check=False, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
    if result.returncode:
        raise RuntimeError(f"Locust load check failed with exit code {result.returncode}; inspect {result_dir}.")
    console_output = f"{result.stdout}\n{result.stderr}"
    console_output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", console_output)
    summary = re.search(
        r"(?m)^\s*Aggregated\s+(\d+)\s+(\d+)\(([\d.]+)%\)\s+\|\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+\|\s+([\d.]+)\s+([\d.]+)\s*$",
        console_output,
    )
    if not summary:
        raise RuntimeError(f"Could not parse Locust's final aggregate summary; inspect {result_dir}.")
    requests, failures, failure_percent, average_ms, minimum_ms, maximum_ms, median_ms, requests_per_second, failures_per_second = summary.groups()
    percentile_rows = [line.split() for line in console_output.splitlines() if line.strip().startswith("Aggregated") and "|" not in line]
    if not percentile_rows or len(percentile_rows[-1]) < 7:
        raise RuntimeError(f"Could not parse Locust's final percentile summary; inspect {result_dir}.")
    if int(requests) < 1 or int(failures) > 0:
        raise RuntimeError(f"Locust recorded {requests} requests and {failures} failures; inspect {result_dir}.")
    baseline = {
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "runner": "Locust",
        "target": "Express gateway + Django REST API + temporary SQLite",
        "seeded_cases": seed_count,
        "users": int(env.get("LOCUST_USERS", "5")),
        "spawn_rate_users_per_second": float(env.get("LOCUST_SPAWN_RATE", "1")),
        "duration": env.get("LOCUST_RUN_TIME", "15s"),
        "requests": int(requests),
        "failures": int(failures),
        "failure_percent": float(failure_percent),
        "average_response_ms": int(average_ms),
        "minimum_response_ms": int(minimum_ms),
        "maximum_response_ms": int(maximum_ms),
        "median_response_ms": int(median_ms),
        "p95_response_ms": int(percentile_rows[-1][6]),
        "requests_per_second": float(requests_per_second),
        "failures_per_second": float(failures_per_second),
        "final_summary_source": "Locust headless console aggregate",
        "csv_note": "Locust CSV files are periodically flushed and can lag the final console totals slightly.",
        "python_version": platform.python_version(),
        "locust_version": subprocess.run([sys.executable, "-m", "locust", "--version"], capture_output=True, text=True, check=True).stdout.strip(),
    }
    summary_path = result_dir / "baseline.json"
    summary_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    print(f"Locust load check passed; authoritative summary: {summary_path}; CSV details: {result_dir}.")


def find_k6_binary():
    configured = os.environ.get("K6_BIN")
    candidates = [configured, shutil.which("k6")]
    if os.name == "nt":
        candidates.append(str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "k6" / "k6.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("k6 is required. Install it from Grafana's official Windows package or set K6_BIN to k6.exe.")


def run_k6_load(gateway_base, env, client):
    seed_count, tenant_id = seed_load_cases(gateway_base, env, client)
    users = int(env.get("K6_VUS", "5"))
    duration = env.get("K6_DURATION", "15s")
    k6 = find_k6_binary()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    result_dir = ROOT / "tests" / "performance" / "results" / f"k6-{timestamp}"
    result_dir.mkdir(parents=True, exist_ok=False)
    native_summary_path = result_dir / "k6-summary.json"
    baseline_path = result_dir / "baseline.json"
    load_env = env.copy()
    load_env.pop("API_TOKEN", None)
    script_path = ROOT / "tests" / "performance" / "k6-cases.js"
    command = [
        k6,
        "run",
        "--vus",
        str(users),
        "--duration",
        duration,
        "--summary-export",
        str(native_summary_path),
        "--env",
        f"API_URL={gateway_base}/api/v1",
        "--env",
        f"TENANT_ID={tenant_id}",
        "--env",
        f"VUS={users}",
        "--env",
        f"DURATION={duration}",
        str(script_path),
    ]
    print(f"Running k6 against disposable SQLite API with {seed_count} synthetic cases; results: {result_dir}")
    result = subprocess.run(command, cwd=ROOT, env=load_env, check=False, capture_output=True, text=True)
    console_output = f"{result.stdout}\n{result.stderr}"
    (result_dir / "console.log").write_text(console_output, encoding="utf-8")
    if console_output:
        print(console_output, end="" if console_output.endswith("\n") else "\n")
    if result.returncode:
        raise RuntimeError(f"k6 load check failed with exit code {result.returncode}; inspect {result_dir}.")
    if not native_summary_path.is_file():
        raise RuntimeError(f"k6 did not write its summary; inspect {result_dir}.")
    summary = json.loads(native_summary_path.read_text(encoding="utf-8"))
    metrics = summary.get("metrics", {})
    requests = metrics.get("http_reqs", {})
    duration_stats = metrics.get("http_req_duration", {})
    failed = metrics.get("http_req_failed", {}).get("value", 0)
    app_errors = metrics.get("case_list_errors", {}).get("value", 0)
    request_count = int(requests.get("count", 0))
    if request_count < 1 or failed > 0 or app_errors > 0:
        raise RuntimeError(f"k6 recorded {request_count} requests, {failed:.2%} HTTP failures, and {app_errors:.2%} application errors; inspect {result_dir}.")
    version = subprocess.run([k6, "version"], capture_output=True, text=True, check=True).stdout.strip()
    baseline = {
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "runner": "k6",
        "runner_version": version,
        "target": "Express gateway + Django REST API + temporary SQLite",
        "seeded_cases": seed_count,
        "virtual_users": users,
        "duration": duration,
        "requests": request_count,
        "failures": round(failed * request_count),
        "failure_rate": failed,
        "application_error_rate": app_errors,
        "average_response_ms": duration_stats.get("avg"),
        "median_response_ms": duration_stats.get("med"),
        "p95_response_ms": duration_stats.get("p(95)"),
        "maximum_response_ms": duration_stats.get("max"),
        "requests_per_second": requests.get("rate"),
        "thresholds_passed": result.returncode == 0,
        "configured_thresholds": {
            "http_req_failed": "rate<0.01",
            "http_req_duration": "p(95)<750ms",
            "case_list_errors": "rate<0.01",
        },
        "summary_source": "k6 --summary-export",
    }
    baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    print(f"k6 load check passed; authoritative summary and console log saved to {result_dir}.")


def find_jmeter_home():
    configured = os.environ.get("JMETER_HOME")
    candidates = [Path(configured) if configured else None]
    executable = shutil.which("jmeter")
    if executable:
        candidates.append(Path(executable).parent.parent)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "Programs" / "apache-jmeter-5.6.3")
    for candidate in candidates:
        if candidate and (candidate / "bin" / "ApacheJMeter.jar").is_file():
            return candidate
    raise RuntimeError("Apache JMeter is required. Install it and set JMETER_HOME to its extracted directory.")


def run_jmeter_load(gateway_base, env, client):
    seed_count, tenant_id = seed_load_cases(gateway_base, env, client)
    threads = int(env.get("JMETER_THREADS", "5"))
    loops = int(env.get("JMETER_LOOPS", "10"))
    jmeter_home = find_jmeter_home()
    java = shutil.which("java")
    if not java:
        raise RuntimeError("A Java runtime is required to run Apache JMeter.")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    result_dir = ROOT / "tests" / "performance" / "results" / f"jmeter-{timestamp}"
    result_dir.mkdir(parents=True, exist_ok=False)
    results_path = result_dir / "cases.jtl"
    log_path = result_dir / "jmeter.log"
    console_path = result_dir / "console.log"
    test_plan = ROOT / "tests" / "performance" / "cases-smoke.jmx"
    command = [
        java,
        "-jar",
        str(jmeter_home / "bin" / "ApacheJMeter.jar"),
        "-n",
        "-t",
        str(test_plan),
        "-l",
        str(results_path),
        "-j",
        str(log_path),
        f"-Jhost=127.0.0.1",
        f"-Jport={urlsplit(gateway_base).port}",
        f"-Jthreads={threads}",
        f"-Jloops={loops}",
        f"-JtenantId={tenant_id}",
        "-Jjmeter.save.saveservice.output_format=csv",
        "-Jjmeter.save.saveservice.print_field_names=true",
    ]
    print(f"Running JMeter against disposable SQLite API with {seed_count} synthetic cases; results: {result_dir}")
    started = time.monotonic()
    result = subprocess.run(command, cwd=jmeter_home, check=False, capture_output=True, text=True)
    elapsed_seconds = time.monotonic() - started
    console_output = f"{result.stdout}\n{result.stderr}"
    console_path.write_text(console_output, encoding="utf-8")
    if console_output:
        print(console_output, end="" if console_output.endswith("\n") else "\n")
    if result.returncode:
        raise RuntimeError(f"JMeter failed with exit code {result.returncode}; inspect {result_dir}.")
    if not results_path.is_file():
        raise RuntimeError(f"JMeter did not write sample results; inspect {result_dir}.")
    with results_path.open(encoding="utf-8-sig", newline="") as results_file:
        samples = list(csv.DictReader(results_file))
    expected_samples = threads * loops
    failures = [sample for sample in samples if sample.get("success", "").lower() != "true" or sample.get("responseCode") != "200"]
    if len(samples) != expected_samples or failures:
        raise RuntimeError(f"JMeter recorded {len(samples)}/{expected_samples} expected samples and {len(failures)} failures; inspect {result_dir}.")
    response_times = sorted(int(sample["elapsed"]) for sample in samples)
    sample_start_ms = min(int(sample["timeStamp"]) for sample in samples)
    sample_end_ms = max(int(sample["timeStamp"]) + int(sample["elapsed"]) for sample in samples)
    sample_window_seconds = max((sample_end_ms - sample_start_ms) / 1000, 0.001)
    p95_index = max(0, min(len(response_times) - 1, math.ceil(len(response_times) * 0.95) - 1))
    version_result = subprocess.run(
        [java, "-jar", str(jmeter_home / "bin" / "ApacheJMeter.jar"), "--version"],
        cwd=jmeter_home,
        check=True,
        capture_output=True,
        text=True,
    )
    version_match = re.search(r"(?m)^.*\s(\d+\.\d+\.\d+)\s*$", version_result.stdout + version_result.stderr)
    baseline = {
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "runner": "Apache JMeter",
        "runner_version": version_match.group(1) if version_match else jmeter_home.name.removeprefix("apache-jmeter-"),
        "target": "Express gateway + Django REST API + temporary SQLite",
        "seeded_cases": seed_count,
        "threads": threads,
        "loops_per_thread": loops,
        "requests": len(samples),
        "failures": len(failures),
        "average_response_ms": round(sum(response_times) / len(response_times), 2),
        "median_response_ms": response_times[len(response_times) // 2],
        "p95_response_ms": response_times[p95_index],
        "maximum_response_ms": response_times[-1],
        "sample_window_seconds": round(sample_window_seconds, 3),
        "sample_window_requests_per_second": round(len(samples) / sample_window_seconds, 2),
        "runner_wall_seconds": round(elapsed_seconds, 3),
        "runner_wall_requests_per_second": round(len(samples) / elapsed_seconds, 2),
        "sample_results": results_path.name,
        "console_log": console_path.name,
    }
    baseline_path = result_dir / "baseline.json"
    baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    print(f"JMeter load check passed; summary and JTL saved to {result_dir}.")


def main():
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required to run the API gateway contract check.")

    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    validate_spec(spec)

    with tempfile.TemporaryDirectory(prefix="opsbridge-gateway-contract-", ignore_cleanup_errors=True) as temporary:
        temporary_path = Path(temporary)
        backend_port, gateway_port = free_port(), free_port()
        browser_project_option = next(
            (argument.split("=", 1)[1] for argument in sys.argv[1:] if argument.startswith("--browser-projects=")),
            None,
        )
        run_browser = "--browser" in sys.argv[1:] or browser_project_option is not None
        browser_projects = ["chromium"]
        if browser_project_option is not None:
            browser_projects = ["chromium", "firefox", "webkit"] if browser_project_option == "all" else browser_project_option.split(",")
            if not browser_projects or any(project not in {"chromium", "firefox", "webkit"} for project in browser_projects):
                raise ValueError("--browser-projects must be 'all' or a comma-separated list of chromium,firefox,webkit")
            if len(set(browser_projects)) != len(browser_projects):
                raise ValueError("--browser-projects cannot contain duplicates")
        run_locust = "--locust" in sys.argv[1:]
        run_k6 = "--k6" in sys.argv[1:]
        run_jmeter = "--jmeter" in sys.argv[1:]
        MOCK_AI_CALLS.clear()
        mock_ai = ThreadingHTTPServer(("127.0.0.1", free_port()), MockAIHandler) if run_browser else None
        mock_ai_thread = Thread(target=mock_ai.serve_forever, daemon=True) if mock_ai else None
        if mock_ai_thread:
            mock_ai_thread.start()
        env = os.environ.copy()
        env.update(
            {
                "APP_ENV": "development",
                "OPSBRIDGE_SQLITE_PATH": str(temporary_path / "compliance.sqlite3"),
                "MEDIA_ROOT": str(temporary_path / "uploads"),
                "DEV_IDENTITY_ENABLED": "true",
                "PORT": str(gateway_port),
                "COMPLIANCE_SERVICE_URL": f"http://127.0.0.1:{backend_port}",
                "NEXT_PUBLIC_API_URL": f"http://127.0.0.1:{gateway_port}/api/v1",
                "OPSBRIDGE_EAGER_TASKS": "true" if run_browser else "false",
                "OTEL_TRACES_EXPORTER": "none",
                "OTEL_METRICS_EXPORTER": "none",
            }
        )
        if mock_ai:
            env["AI_SERVICE_URL"] = f"http://127.0.0.1:{mock_ai.server_port}"
        migration = subprocess.run(
            [sys.executable, "manage.py", "migrate", "--noinput", "--settings=config.test_settings"],
            cwd=COMPLIANCE_DIR,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if migration.returncode:
            raise RuntimeError(f"SQLite migrations failed:\n{migration.stdout}\n{migration.stderr}")

        compliance_log = (temporary_path / "compliance.log").open("w+b")
        gateway_log = (temporary_path / "gateway.log").open("w+b")
        compliance = subprocess.Popen(
            [sys.executable, "manage.py", "runserver", f"127.0.0.1:{backend_port}", "--noreload", "--settings=config.test_settings"],
            cwd=COMPLIANCE_DIR,
            env=env,
            stdout=compliance_log,
            stderr=subprocess.STDOUT,
        )
        gateway = None
        try:
            wait_for_health(f"http://127.0.0.1:{backend_port}/health", compliance, temporary_path / "compliance.log")
            gateway = subprocess.Popen(
                [node, "src/server.js"],
                cwd=GATEWAY_DIR,
                env=env,
                stdout=gateway_log,
                stderr=subprocess.STDOUT,
            )
            gateway_base = f"http://127.0.0.1:{gateway_port}"
            wait_for_health(f"{gateway_base}/health", gateway, temporary_path / "gateway.log")

            tenant_id = "contract-tenant"
            headers = {"X-Tenant-Id": tenant_id, "X-Correlation-Id": "gateway-contract-42"}
            with httpx.Client(timeout=10) as client:
                created_response = client.post(
                    f"{gateway_base}/api/v1/cases",
                    headers=headers,
                    json={
                        "workerName": "Contract Test Worker",
                        "email": "contract@example.invalid",
                        "phone": "+10000000000",
                        "role": "API Contract Tester",
                        "country": "us",
                    },
                )
                assert created_response.status_code == 201, created_response.text
                assert_private_no_store(created_response)
                assert created_response.headers["X-Correlation-Id"] == "gateway-contract-42"
                case = created_response.json()
                validate_response(spec, "/cases", "post", 201, case)
                case_id = case["id"]

                second_created = client.post(
                    f"{gateway_base}/api/v1/cases",
                    headers=headers,
                    json={
                        "workerName": "Second Contract Worker",
                        "email": "contract-second@example.invalid",
                        "role": "Pagination Contract Tester",
                        "country": "GB",
                    },
                )
                assert second_created.status_code == 201, second_created.text
                second_case_id = second_created.json()["id"]

                listed_response = client.get(f"{gateway_base}/api/v1/cases", headers=headers, params={"limit": 1})
                assert listed_response.status_code == 200, listed_response.text
                assert_private_no_store(listed_response)
                validate_response(spec, "/cases", "get", 200, listed_response.json())
                first_page = listed_response.json()
                assert first_page["total"] == 2 and len(first_page["items"]) == 1
                assert first_page["next_cursor"]
                second_page_response = client.get(
                    f"{gateway_base}/api/v1/cases",
                    headers=headers,
                    params={"limit": 1, "cursor": first_page["next_cursor"]},
                )
                assert second_page_response.status_code == 200, second_page_response.text
                assert_private_no_store(second_page_response)
                validate_response(spec, "/cases", "get", 200, second_page_response.json())
                second_page = second_page_response.json()
                assert second_page["total"] == 2 and len(second_page["items"]) == 1
                assert second_page["next_cursor"] is None
                assert {first_page["items"][0]["id"], second_page["items"][0]["id"]} == {case_id, second_case_id}

                detail_response = client.get(f"{gateway_base}/api/v1/cases/{case_id}", headers=headers)
                assert detail_response.status_code == 200, detail_response.text
                assert_private_no_store(detail_response)
                validate_response(spec, "/cases/{caseId}", "get", 200, detail_response.json())

                decision_response = client.post(
                    f"{gateway_base}/api/v1/cases/{case_id}/decision",
                    headers=headers,
                    json={"decision": "approve", "reason": "Synthetic contract test decision"},
                )
                assert decision_response.status_code == 200, decision_response.text
                assert_private_no_store(decision_response)
                validate_response(spec, "/cases/{caseId}/decision", "post", 200, decision_response.json())

                repeated_decision = client.post(
                    f"{gateway_base}/api/v1/cases/{case_id}/decision",
                    headers=headers,
                    json={"decision": "reject", "reason": "Must be rejected as already final"},
                )
                assert repeated_decision.status_code == 409, repeated_decision.text
                assert_private_no_store(repeated_decision)
                validate_response(spec, "/cases/{caseId}/decision", "post", 409, repeated_decision.json())

                other_tenant = client.get(
                    f"{gateway_base}/api/v1/cases/{case_id}",
                    headers={"X-Tenant-Id": "different-tenant"},
                )
                assert other_tenant.status_code == 404, other_tenant.text
                assert_private_no_store(other_tenant)

                consent_response = client.put(
                    f"{gateway_base}/api/v1/voice/contacts",
                    headers=headers,
                    json={
                        "phoneNumber": "+15551234567",
                        "consentStatus": "granted",
                        "consentRecordedAt": datetime.now(timezone.utc).isoformat(),
                        "consentSource": "synthetic contract fixture",
                        "consentReference": "voice-contract-42",
                        "suppressed": False,
                        "suppressionReason": "",
                    },
                )
                assert consent_response.status_code == 200, consent_response.text
                assert_private_no_store(consent_response)
                validate_response(spec, "/voice/contacts", "put", 200, consent_response.json())

                consent_detail = client.get(
                    f"{gateway_base}/api/v1/voice/contacts",
                    headers=headers,
                    params={"phoneNumber": "+15551234567"},
                )
                assert consent_detail.status_code == 200, consent_detail.text
                assert_private_no_store(consent_detail)
                validate_response(spec, "/voice/contacts", "get", 200, consent_detail.json())
                assert consent_detail.json()["consentReference"] == "voice-contract-42"

                voice_eligibility = client.get(
                    f"{gateway_base}/api/v1/voice/contacts/eligibility",
                    headers=headers,
                    params={"phoneNumber": "+15551234567"},
                )
                assert voice_eligibility.status_code == 200, voice_eligibility.text
                assert_private_no_store(voice_eligibility)
                assert voice_eligibility.json() == {"eligible": True, "reason": "eligible"}
                validate_response(spec, "/voice/contacts/eligibility", "get", 200, voice_eligibility.json())

                other_tenant_voice = client.get(
                    f"{gateway_base}/api/v1/voice/contacts/eligibility",
                    headers={"X-Tenant-Id": "different-tenant"},
                    params={"phoneNumber": "+15551234567"},
                )
                assert other_tenant_voice.status_code == 200, other_tenant_voice.text
                assert other_tenant_voice.json() == {"eligible": False, "reason": "no_record"}

            print("Gateway-to-Django contract passed: case create/list/detail/decision, voice consent persistence and eligibility, tenant isolation, private cache headers, and OpenAPI response validation.")
            if run_locust:
                with httpx.Client(timeout=10) as load_client:
                    run_locust_load(gateway_base, env, load_client)
            if run_k6:
                with httpx.Client(timeout=10) as load_client:
                    run_k6_load(gateway_base, env, load_client)
            if run_jmeter:
                with httpx.Client(timeout=10) as load_client:
                    run_jmeter_load(gateway_base, env, load_client)
            if run_browser:
                playwright = subprocess.run(
                    [
                        node,
                        str(ROOT / "node_modules" / "@playwright" / "test" / "cli.js"),
                        "test",
                        "tests/e2e/worker-case-contract.spec.ts",
                        "tests/e2e/worker-onboarding.spec.ts",
                        "--workers=1",
                        *[f"--project={project}" for project in browser_projects],
                    ],
                    cwd=ROOT,
                    env=env,
                    check=False,
                )
                if playwright.returncode:
                    raise RuntimeError("Worker portal browser-to-Django onboarding tests failed.")

                ai_calls_by_correlation = {}
                for call in MOCK_AI_CALLS:
                    ai_calls_by_correlation.setdefault(call["correlation_id"], []).append(call)
                if len(ai_calls_by_correlation) != len(browser_projects):
                    raise AssertionError(
                        f"Expected one mock AI workflow per browser ({len(browser_projects)}), "
                        f"received correlations: {list(ai_calls_by_correlation)}"
                    )
                for correlation_id, calls in ai_calls_by_correlation.items():
                    paths = [call["path"] for call in calls]
                    if paths != ["/v1/extract", "/v1/recommend"]:
                        raise AssertionError(f"Incomplete or unexpected mock AI calls for {correlation_id}: {paths}")
                    if any(call["tenant_id"] != "demo-tenant" for call in calls):
                        raise AssertionError(f"Mock AI tenant context mismatch for {correlation_id}: {calls}")
                with httpx.Client(timeout=10) as verification_client:
                    cases_response = verification_client.get(
                        f"{gateway_base}/api/v1/cases", headers={"X-Tenant-Id": "demo-tenant"}
                    )
                assert cases_response.status_code == 200, cases_response.text
                processed = [item for item in cases_response.json()["items"] if item["documents"] and item["ai_recommendation"]]
                processed_correlations = set()
                for case in processed:
                    upload_event = next(
                        (event for event in case["audit_events"] if event["event_type"] == "document.received"),
                        None,
                    )
                    if upload_event:
                        processed_correlations.add(upload_event["correlation_id"])
                assert processed_correlations == set(ai_calls_by_correlation), {
                    "processed_correlations": processed_correlations,
                    "ai_correlations": set(ai_calls_by_correlation),
                }
                assert len(processed_correlations) == len(browser_projects), {
                    "expected_browser_flows": len(browser_projects),
                    "processed_correlations": processed_correlations,
                }
                print(
                    f"Worker portal upload-to-human-review workflow passed in {', '.join(browser_projects)}: "
                    "extraction, recommendation, tenant context, and per-case correlation IDs verified."
                )
        finally:
            stop_process(gateway) if gateway else None
            stop_process(compliance)
            gateway_log.close()
            compliance_log.close()
            if mock_ai:
                mock_ai.shutdown()
                mock_ai.server_close()


if __name__ == "__main__":
    main()
