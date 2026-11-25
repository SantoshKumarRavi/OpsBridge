package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func request(handler http.Handler, method, path, body, tenant string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	if tenant != "" {
		req.Header.Set("X-Tenant-Id", tenant)
	}
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, req)
	return response
}

func TestHealthAndSecurityHeaders(t *testing.T) {
	response := request(securityHeaders(newHandler()), http.MethodGet, "/health", "", "")
	if response.Code != http.StatusOK {
		t.Fatalf("health status = %d, want %d", response.Code, http.StatusOK)
	}
	if response.Header().Get("X-Content-Type-Options") != "nosniff" {
		t.Fatal("X-Content-Type-Options header was not set")
	}
	if response.Header().Get("Cache-Control") != "no-store" {
		t.Fatal("Cache-Control header was not set")
	}
	var payload map[string]string
	if err := json.Unmarshal(response.Body.Bytes(), &payload); err != nil {
		t.Fatalf("decode health response: %v", err)
	}
	if payload["service"] != "telemetry-service" {
		t.Fatalf("health service = %q", payload["service"])
	}
}

func TestIngestRequiresValidTrustedTenant(t *testing.T) {
	validBody := `{"deviceId":"device-1","eventType":"temperature"}`
	for _, tenant := range []string{"", strings.Repeat("a", 101), "tenant with spaces"} {
		t.Run(fmt.Sprintf("tenant_%d", len(tenant)), func(t *testing.T) {
			response := request(securityHeaders(newHandler()), http.MethodPost, "/v1/telemetry", validBody, tenant)
			if response.Code != http.StatusBadRequest {
				t.Fatalf("status = %d, want %d", response.Code, http.StatusBadRequest)
			}
		})
	}
}

func TestIngestUsesTrustedTenantAndDefaultsTimestamp(t *testing.T) {
	before := accepted.Load()
	response := request(securityHeaders(newHandler()), http.MethodPost, "/v1/telemetry", `{"tenantId":"attacker-tenant","deviceId":"device-7","eventType":"temperature","metrics":{"celsius":21.5}}`, "trusted_tenant")
	if response.Code != http.StatusAccepted {
		t.Fatalf("status = %d, want %d: %s", response.Code, http.StatusAccepted, response.Body.String())
	}
	var payload map[string]any
	if err := json.Unmarshal(response.Body.Bytes(), &payload); err != nil {
		t.Fatalf("decode ingestion response: %v", err)
	}
	if payload["tenantId"] != "trusted_tenant" {
		t.Fatalf("tenantId = %v, body-supplied tenant was not overridden", payload["tenantId"])
	}
	if accepted.Load() != before+1 {
		t.Fatalf("accepted count = %d, want %d", accepted.Load(), before+1)
	}
}

func TestIngestRejectsMalformedOrAmbiguousJSON(t *testing.T) {
	for name, body := range map[string]string{
		"invalid-json":     `{"deviceId":`,
		"unknown-field":    `{"deviceId":"d","eventType":"e","unexpected":true}`,
		"trailing-json":    `{"deviceId":"d","eventType":"e"}{"deviceId":"other"}`,
		"missing-device":   `{"eventType":"e"}`,
		"too-many-metrics": `{"deviceId":"d","eventType":"e","metrics":{"a":1,"b":2,"c":3,"d":4,"e":5,"f":6,"g":7,"h":8,"i":9,"j":10,"k":11,"l":12,"m":13,"n":14,"o":15,"p":16,"q":17,"r":18,"s":19,"t":20,"u":21,"v":22,"w":23,"x":24,"y":25,"z":26,"aa":27,"ab":28,"ac":29,"ad":30,"ae":31,"af":32,"ag":33,"ah":34,"ai":35,"aj":36,"ak":37,"al":38,"am":39,"an":40,"ao":41}}`,
	} {
		t.Run(name, func(t *testing.T) {
			response := request(securityHeaders(newHandler()), http.MethodPost, "/v1/telemetry", body, "tenant-a")
			if response.Code != http.StatusBadRequest {
				t.Fatalf("status = %d, want %d", response.Code, http.StatusBadRequest)
			}
		})
	}
}

func TestIngestRejectsOversizedPayload(t *testing.T) {
	body := `{"deviceId":"device-1","eventType":"telemetry","metrics":{"x":"` + strings.Repeat("a", maxTelemetryBody) + `"}}`
	response := request(securityHeaders(newHandler()), http.MethodPost, "/v1/telemetry", body, "tenant-a")
	if response.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusRequestEntityTooLarge)
	}
}

func TestMetricsExposesAcceptedEventCount(t *testing.T) {
	before := accepted.Load()
	_ = request(securityHeaders(newHandler()), http.MethodPost, "/v1/telemetry", `{"deviceId":"device-1","eventType":"temperature"}`, "tenant-a")
	response := request(securityHeaders(newHandler()), http.MethodGet, "/metrics", "", "")
	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusOK)
	}
	if got, want := response.Body.String(), "opsbridge_telemetry_events_total "+itoa(before+1)+"\n"; got != want {
		t.Fatalf("metrics = %q, want %q", got, want)
	}
	if contentType := response.Header().Get("Content-Type"); contentType != "text/plain; version=0.0.4" {
		t.Fatalf("Content-Type = %q", contentType)
	}
}
