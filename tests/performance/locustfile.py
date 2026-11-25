import os
from locust import HttpUser, between, task


class CaseListUser(HttpUser):
    host = os.getenv("API_URL", "http://localhost:8080/api/v1")
    wait_time = between(0.5, 2)

    def on_start(self):
        self.headers = {"X-Tenant-Id": os.getenv("TENANT_ID", "demo-tenant")}
        if os.getenv("API_TOKEN"):
            self.headers["Authorization"] = f"Bearer {os.environ['API_TOKEN']}"

    @task
    def list_cases(self):
        self.client.get("/cases?limit=25", headers=self.headers, name="GET /cases")
