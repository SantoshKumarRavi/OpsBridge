# OpsBridge MCP tools

This local Model Context Protocol server provides read-only case and policy search plus workflow-outline generation. It starts with stdio and never approves cases, sends messages, or calls third-party systems. Configure `API_GATEWAY_URL`, `OPSBRIDGE_MCP_TENANT_ID`, and optionally `OPSBRIDGE_MCP_ACCESS_TOKEN` in the MCP client environment. For a local development profile, run `python server.py` in this directory after starting the API stack.
