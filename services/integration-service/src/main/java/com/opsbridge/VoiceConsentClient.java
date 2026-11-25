package com.opsbridge;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.client.RestClient;

@Component
public class VoiceConsentClient {
    private final RestClient client;
    private final String internalToken;

    public VoiceConsentClient(RestClient.Builder builder,
                              @Value("${opsbridge.compliance.base-url:http://localhost:8001}") String baseUrl,
                              @Value("${opsbridge.security.internal-token:}") String internalToken) {
        this.client = builder.baseUrl(baseUrl.replaceAll("/+$", "")).build();
        this.internalToken = internalToken;
    }

    public void requireEligible(String tenantId, String phoneNumber) {
        Eligibility result;
        try {
            var request = client.get().uri("/api/v1/voice/contacts/eligibility?phoneNumber={phoneNumber}", phoneNumber)
                    .header("X-Tenant-Id", tenantId);
            if (!internalToken.isBlank()) request.header("X-Internal-Service-Token", internalToken);
            result = request.retrieve().body(Eligibility.class);
        } catch (RuntimeException exception) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                    "Voice eligibility could not be verified; outbound calling is blocked.", exception);
        }
        if (result == null || !result.eligible()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "This contact is not eligible for outbound calls.");
        }
    }

    public record Eligibility(boolean eligible, String reason) { }
}
