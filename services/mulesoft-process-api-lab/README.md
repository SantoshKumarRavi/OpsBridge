# MuleSoft APIkit process API lab

This lab demonstrates MuleSoft APIkit's contract-first REST routing and a process API that calls the existing Django compliance system API, then uses DataWeave to return a minimal onboarding summary. It adds no second database or case owner.

## Source files

- `api/opsbridge-process-api.raml` defines `GET /api/v1/cases/{caseId}/summary`, bearer-token pass-through, tenant header, response schema, and errors.
- `src/main/mule/opsbridge-process-api.xml` configures an HTTP listener, APIkit router mapping, tenant-scoped downstream request, and response transformation.

## Import and run in Anypoint Studio

MuleSoft's documented workflow requires Anypoint Studio or Anypoint Code Builder and Mule Runtime 4. Import this lab as a Mule project, add the HTTP Connector and APIkit for REST module through Studio's dependency/module tooling, then scaffold or compare the APIkit flows from the RAML contract. Configure these properties using local, non-production values:

```properties
http.port=8081
compliance.protocol=HTTP
compliance.host=localhost
compliance.port=8001
compliance.internalServiceToken=local-development-token
```

Run the process API only on a trusted local network behind the OpsBridge gateway or an Anypoint API Manager authentication policy. The RAML bearer scheme describes pass-through documentation; it does not validate JWTs itself. The tenant ID and bearer token are forwarded to Django, and the internal service token must be configured out of source control. Do not expose this lab listener publicly.

Example request through an authenticated local setup:

```http
GET /api/v1/cases/{caseId}/summary HTTP/1.1
Host: localhost:8081
Authorization: Bearer <development-access-token>
X-Tenant-Id: demo-tenant
```

The sample has not been imported into Anypoint Studio, dependency versions have not been selected by Studio, and Mule Runtime/MUnit checks have not run. Follow the official [APIkit overview](https://docs.mulesoft.com/apikit/latest/), [REST APIkit configuration reference](https://docs.mulesoft.com/apikit/latest/apikit-4-xml-reference), and [build/implement/test walkthrough](https://docs.mulesoft.com/apikit/latest/apikit-4-implement-rest-api) when importing it.
