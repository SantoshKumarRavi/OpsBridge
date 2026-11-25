import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errors = new Rate('case_list_errors');
export const options = {
  vus: Number(__ENV.VUS || 5),
  duration: __ENV.DURATION || '30s',
  thresholds: { http_req_failed: ['rate<0.01'], http_req_duration: ['p(95)<750'], case_list_errors: ['rate<0.01'] },
};

export default function () {
  const headers = { 'X-Tenant-Id': __ENV.TENANT_ID || 'demo-tenant' };
  if (__ENV.API_TOKEN) headers.Authorization = `Bearer ${__ENV.API_TOKEN}`;
  const response = http.get(`${__ENV.API_URL || 'http://localhost:8080/api/v1'}/cases?limit=25`, { headers });
  const ok = check(response, { 'case list returns success': (r) => r.status === 200 });
  errors.add(!ok);
  sleep(1);
}
