# OpsBridge API client

Typed TypeScript client for the tenant-scoped OpsBridge REST API. It is a private workspace package and is not published to npm.

## Build and verify

From the repository root:

```sh
npm run test:api-client
npm run build:api-client
```

The generated contract types come from `packages/contracts/openapi.yaml` through `openapi-typescript`; run `npm run generate:api-client-types` after changing the contract. The build emits ESM JavaScript and TypeScript declarations under `dist/`. The operations dashboard consumes the built package. CI regenerates the types and fails if the generated file is stale, then runs `npm pack --dry-run` to verify package contents without publishing it.

## Example

```ts
import { createOpsBridgeClient } from '@opsbridge/api-client';
import { createOpsBridgeAuth } from '@opsbridge/auth-client';

const auth = createOpsBridgeAuth({
  url: 'https://identity.example.test',
  realm: 'opsbridge',
  clientId: 'opsbridge-operations',
});
await auth.initialize();

const client = createOpsBridgeClient({
  baseUrl: 'https://api.example.test/api/v1',
  getHeaders: () => auth.headers(),
});

const firstPage = await client.listCases({ status: 'review_required', limit: 25 });
const caseRecord = await client.getCase(firstPage.items[0].id);
```

`listCases` accepts the API's status, page-size and opaque cursor filters. `createCase` posts a typed JSON body. `uploadDocument` sends multipart form data and lets `fetch` generate the boundary. `decideCase` accepts only the decision values and reason defined in the OpenAPI contract. Non-2xx responses throw `OpsBridgeApiError`, which exposes the HTTP status and parsed response body.

The caller supplies authentication headers so the SDK can use the existing Keycloak auth client without owning token storage or refresh policy. Tenant scoping is derived by the API from the authenticated identity in production; the SDK does not set a caller-controlled tenant header itself.

## Scope

The client currently covers case list/create/detail, document upload and final case decisions. Voice-policy, webhook and agent APIs are not included. No npm publication or external consumer compatibility is claimed.
