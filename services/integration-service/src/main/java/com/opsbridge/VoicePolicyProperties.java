package com.opsbridge;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.LocalTime;
import java.util.Map;

@ConfigurationProperties(prefix = "opsbridge.voice")
public record VoicePolicyProperties(Map<String, TenantPolicy> tenants) {
    public VoicePolicyProperties {
        tenants = tenants == null ? Map.of() : Map.copyOf(tenants);
    }

    public record TenantPolicy(String timeZone, LocalTime allowedStart, LocalTime allowedEnd) { }
}
