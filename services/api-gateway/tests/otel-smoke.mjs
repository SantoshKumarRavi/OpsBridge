import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { createConnection } from 'node:net';
import { fileURLToPath } from 'node:url';

async function listen(server) {
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  return server.address().port;
}

async function stop(child) {
  if (child.exitCode !== null) return;
  child.kill('SIGTERM');
  await Promise.race([
    once(child, 'exit'),
    new Promise((_, reject) => {
      const timer = setTimeout(() => reject(new Error('API gateway did not stop after SIGTERM')), 5000);
      timer.unref();
    }),
  ]);
}

async function waitForPort(port, child, getStderr) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (child.exitCode !== null) throw new Error(`Gateway exited during startup: ${getStderr()}`);
    try {
      await new Promise((resolve, reject) => {
        const socket = createConnection({ host: '127.0.0.1', port });
        socket.once('connect', () => {
          socket.destroy();
          resolve();
        });
        socket.once('error', reject);
      });
      return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  throw new Error(`Gateway did not open port ${port}: ${getStderr()}`);
}

let resolveExport;
let rejectExport;
const exported = new Promise((resolve, reject) => {
  resolveExport = resolve;
  rejectExport = reject;
});
const collector = createServer((request, response) => {
  const chunks = [];
  request.on('data', (chunk) => chunks.push(chunk));
  request.on('end', () => {
    const payload = Buffer.concat(chunks);
    if (request.url === '/v1/traces' && payload.length > 0) {
      resolveExport({ contentType: request.headers['content-type'], payload });
    } else {
      rejectExport(new Error(`Unexpected OTLP request ${request.method} ${request.url}`));
    }
    response.writeHead(200, { 'Content-Type': 'application/x-protobuf' });
    response.end();
  });
});
const collectorPort = await listen(collector);
let downstreamTraceparent;
const downstream = createServer((request, response) => {
  downstreamTraceparent = request.headers.traceparent;
  response.writeHead(200, { 'Content-Type': 'application/json' });
  response.end(JSON.stringify({ items: [], total: 0 }));
});
const downstreamPort = await listen(downstream);
const reservation = createServer();
const appPort = await listen(reservation);
await new Promise((resolve) => reservation.close(resolve));

const app = spawn(process.execPath, [
  '--experimental-loader=@opentelemetry/instrumentation/hook.mjs',
  '--require', './src/instrumentation.cjs',
  'src/server.js',
], {
  cwd: fileURLToPath(new URL('..', import.meta.url)),
  env: {
    ...process.env,
    PORT: String(appPort),
    DEV_IDENTITY_ENABLED: 'true',
    COMPLIANCE_SERVICE_URL: `http://127.0.0.1:${downstreamPort}`,
    OTEL_SERVICE_NAME: 'opsbridge-api-gateway-smoke',
    OTEL_TRACES_EXPORTER: 'otlp',
    OTEL_EXPORTER_OTLP_PROTOCOL: 'http/protobuf',
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: `http://127.0.0.1:${collectorPort}/v1/traces`,
    OTEL_BSP_SCHEDULE_DELAY: '100',
  },
  stdio: ['ignore', 'ignore', 'pipe'],
});

let stderr = '';
app.stderr.setEncoding('utf8');
app.stderr.on('data', (chunk) => { stderr += chunk; });

try {
  await waitForPort(appPort, app, () => stderr);
  const response = await fetch(`http://127.0.0.1:${appPort}/api/v1/cases`, {
    headers: { 'X-Tenant-Id': 'otel-smoke-tenant' },
  });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { items: [], total: 0 });
  assert.match(downstreamTraceparent ?? '', /^00-[0-9a-f]{32}-[0-9a-f]{16}-0[0-3]$/);

  const trace = await Promise.race([
    exported,
    new Promise((_, reject) => {
      const timer = setTimeout(() => reject(new Error('No OTLP trace payload reached the test collector')), 15000);
      timer.unref();
    }),
  ]);
  assert.match(trace.contentType ?? '', /application\/json/);
  const otlp = JSON.parse(trace.payload.toString('utf8'));
  const resourceSpans = otlp.resourceSpans ?? [];
  const spans = resourceSpans.flatMap((resourceSpan) => (resourceSpan.scopeSpans ?? []).flatMap((scope) => scope.spans ?? []));
  assert.ok(spans.length >= 3, `Expected server, Express, and outbound HTTP spans; received ${spans.length}`);
  assert.equal(new Set(spans.map((span) => span.traceId)).size, 1, 'Gateway and outbound HTTP spans did not share one trace ID');
  const serviceName = resourceSpans.flatMap((resourceSpan) => resourceSpan.resource?.attributes ?? [])
    .find((attribute) => attribute.key === 'service.name')?.value?.stringValue;
  assert.equal(serviceName, 'opsbridge-api-gateway-smoke');

  const metricsResponse = await fetch(`http://127.0.0.1:${appPort}/metrics`);
  const metrics = await metricsResponse.text();
  assert.match(metrics, /opsbridge_gateway_requests_total\{/);
  assert.match(metrics, /route="\/api\/v1\/cases"/);
  assert.match(metrics, /opsbridge_gateway_request_duration_seconds_bucket\{/);
  console.log(`OpenTelemetry smoke passed: propagated traceparent to compliance and exported ${spans.length} related span(s) over OTLP/HTTP.`);
} finally {
  await stop(app).catch(() => {});
  await new Promise((resolve) => collector.close(resolve));
  await new Promise((resolve) => downstream.close(resolve));
}
