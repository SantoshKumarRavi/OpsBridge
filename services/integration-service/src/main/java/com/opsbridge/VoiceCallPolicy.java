package com.opsbridge;

import org.springframework.stereotype.Component;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.time.Clock;
import java.time.LocalTime;
import java.time.ZoneId;

@Component
public class VoiceCallPolicy {
    private final VoicePolicyProperties properties;
    private final Clock clock;

    @Autowired
    public VoiceCallPolicy(VoicePolicyProperties properties) {
        this(properties, Clock.systemUTC());
    }

    VoiceCallPolicy(VoicePolicyProperties properties, Clock clock) {
        this.properties = properties;
        this.clock = clock;
    }

    public void assertWindowAllowed(String tenantId) {
        var policy = properties.tenants().get(tenantId);
        if (policy == null) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Voice calling policy is not configured for this tenant.");
        }
        if (policy.timeZone() == null || policy.allowedStart() == null || policy.allowedEnd() == null
                || !policy.allowedStart().isBefore(policy.allowedEnd())) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Tenant voice calling window is invalid.");
        }
        ZoneId zone;
        try {
            zone = ZoneId.of(policy.timeZone());
        } catch (RuntimeException exception) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Tenant voice calling time zone is invalid.", exception);
        }

        LocalTime now = LocalTime.now(clock.withZone(zone));
        if (now.isBefore(policy.allowedStart()) || !now.isBefore(policy.allowedEnd())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Calls are outside this tenant's configured calling window.");
        }
    }

}
