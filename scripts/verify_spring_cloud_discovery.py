"""End-to-end checks for the Spring Cloud discovery/config demo topology."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import urlopen


def get_json(url: str) -> Any:
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_until(label: str, probe: Callable[[], Any], ready: Callable[[Any], bool]) -> Any:
    last_error: Exception | None = None
    for _ in range(120):
        try:
            result = probe()
            if ready(result):
                return result
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
        time.sleep(1)
    raise TimeoutError(f"Timed out waiting for {label}; last error: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-url", default="http://localhost:8888")
    parser.add_argument("--registry-url", default="http://localhost:8761")
    parser.add_argument("--caller-url", default="http://localhost:8090")
    args = parser.parse_args()

    wait_until("Config Server health", lambda: get_json(f"{args.config_url}/actuator/health"), lambda item: item.get("status") == "UP")
    wait_until("Eureka health", lambda: get_json(f"{args.registry_url}/actuator/health"), lambda item: item.get("status") == "UP")
    wait_until("discovery caller health", lambda: get_json(f"{args.caller_url}/actuator/health"), lambda item: item.get("status") == "UP")

    environment = get_json(f"{args.config_url}/synthetic-provider/default")
    config_message = environment["propertySources"][0]["source"].get("provider.message")
    if config_message != "Hello from Spring Cloud Config Server":
        raise AssertionError(f"Unexpected centrally served provider.message: {config_message!r}")

    instances = wait_until(
        "both synthetic provider registrations",
        lambda: get_json(f"{args.caller_url}/v1/discovery/instances"),
        lambda items: len(items) == 2,
    )
    instance_ids = sorted(item["instanceId"] for item in instances)
    if instance_ids != ["provider-a", "provider-b"]:
        raise AssertionError(f"Unexpected registered instances: {instance_ids}")

    responses = [
        get_json(f"{args.caller_url}/v1/discovery/call")["provider"]
        for _ in range(6)
    ]
    served_by = sorted({item["instanceId"] for item in responses})
    if served_by != instance_ids:
        raise AssertionError(f"Load-balanced calls reached {served_by}, expected {instance_ids}")
    if any(item["message"] != config_message for item in responses):
        raise AssertionError("Provider responses did not use centrally served configuration")

    print(json.dumps({
        "configServerMessage": config_message,
        "discoveredInstances": instance_ids,
        "loadBalancedResponses": [item["instanceId"] for item in responses],
        "result": "PASS",
    }, indent=2))


if __name__ == "__main__":
    main()
