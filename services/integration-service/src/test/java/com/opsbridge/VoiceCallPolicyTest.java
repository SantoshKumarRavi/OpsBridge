package com.opsbridge;

import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.LocalTime;
import java.util.Map;
import org.springframework.web.server.ResponseStatusException;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

class VoiceCallPolicyTest {
    private VoiceCallPolicy policyAt(String instant) {
        var tenantPolicy = new VoicePolicyProperties.TenantPolicy(
                "UTC", LocalTime.of(9, 0), LocalTime.of(17, 0));
        return new VoiceCallPolicy(
                new VoicePolicyProperties(Map.of("tenant-a", tenantPolicy)),
                Clock.fixed(Instant.parse(instant), ZoneOffset.UTC));
    }

    @Test
    void allowsWindowDuringTenantConfiguredTime() {
        assertDoesNotThrow(() -> policyAt("2026-11-20T10:00:00Z")
                .assertWindowAllowed("tenant-a"));
    }

    @Test
    void rejectsTenantWithoutConfiguredPolicy() {
        assertThrows(ResponseStatusException.class, () -> policyAt("2026-11-20T10:00:00Z")
                .assertWindowAllowed("tenant-b"));
    }

    @Test
    void rejectsCallsOutsideConfiguredWindowIncludingEndBoundary() {
        assertThrows(ResponseStatusException.class, () -> policyAt("2026-11-20T08:59:59Z")
                .assertWindowAllowed("tenant-a"));
        assertThrows(ResponseStatusException.class, () -> policyAt("2026-11-20T17:00:00Z")
                .assertWindowAllowed("tenant-a"));
    }
}
