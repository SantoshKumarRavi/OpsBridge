package main

import (
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"os"
	"regexp"
	"strings"
	"sync/atomic"
	"time"
)

const maxTelemetryBody = 128 * 1024

var (
	accepted       atomic.Uint64
	tenantIDFormat = regexp.MustCompile(`^[A-Za-z0-9_-]{1,100}$`)
)

type TelemetryEvent struct {
	EventID    string             `json:"eventId"`
	TenantID   string             `json:"tenantId"`
	DeviceID   string             `json:"deviceId"`
	EventType  string             `json:"eventType"`
	OccurredAt time.Time          `json:"occurredAt"`
	Metrics    map[string]float64 `json:"metrics"`
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8090"
	}

	server := &http.Server{
		Addr:              ":" + port,
		Handler:           securityHeaders(newHandler()),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	slog.Info("telemetry service listening", "port", port)
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		slog.Error("server failed", "error", err)
		os.Exit(1)
	}
}

func newHandler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", health)
	mux.HandleFunc("GET /metrics", metrics)
	mux.HandleFunc("POST /v1/telemetry", ingest)
	return mux
}

func health(w http.ResponseWriter, _ *http.Request) {
	write(w, http.StatusOK, map[string]any{"status": "ok", "service": "telemetry-service"})
}

func metrics(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	_, _ = w.Write([]byte("opsbridge_telemetry_events_total " + itoa(accepted.Load()) + "\n"))
}

func ingest(w http.ResponseWriter, r *http.Request) {
	tenant := strings.TrimSpace(r.Header.Get("X-Tenant-Id"))
	if !tenantIDFormat.MatchString(tenant) {
		write(w, http.StatusBadRequest, map[string]string{"error": "Trusted tenant context is required."})
		return
	}

	r.Body = http.MaxBytesReader(w, r.Body, maxTelemetryBody)
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	var event TelemetryEvent
	if err := decoder.Decode(&event); err != nil {
		writeDecodeError(w, err)
		return
	}
	if err := decoder.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
		writeDecodeError(w, err)
		return
	}

	if event.DeviceID == "" || event.EventType == "" || len(event.Metrics) > 40 {
		write(w, http.StatusBadRequest, map[string]string{"error": "deviceId, eventType, and at most 40 metric values are required."})
		return
	}

	// Identity comes from the trusted gateway header, never the submitted event body.
	event.TenantID = tenant
	if event.OccurredAt.IsZero() {
		event.OccurredAt = time.Now().UTC()
	}
	accepted.Add(1)
	write(w, http.StatusAccepted, map[string]any{
		"accepted": true,
		"tenantId": tenant,
		"deviceId": event.DeviceID,
		"queued":   false,
		"message":  "Telemetry accepted into the service ingestion buffer.",
	})
}

func writeDecodeError(w http.ResponseWriter, err error) {
	var tooLarge *http.MaxBytesError
	if errors.As(err, &tooLarge) {
		write(w, http.StatusRequestEntityTooLarge, map[string]string{"error": "Telemetry payload exceeds the size limit."})
		return
	}
	write(w, http.StatusBadRequest, map[string]string{"error": "Invalid telemetry event."})
}

func write(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func securityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Cache-Control", "no-store")
		next.ServeHTTP(w, r)
	})
}

func itoa(value uint64) string {
	if value == 0 {
		return "0"
	}
	var digits [20]byte
	index := len(digits)
	for value > 0 {
		index--
		digits[index] = byte('0' + value%10)
		value /= 10
	}
	return string(digits[index:])
}
