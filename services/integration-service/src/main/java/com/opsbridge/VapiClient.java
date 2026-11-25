package com.opsbridge;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;

@Component
public class VapiClient {
    private final RestClient client;
    private final String apiKey;
    private final String phoneNumberId;
    private final String assistantId;
    private final String baseUrl;

    public VapiClient(RestClient.Builder builder,
                      @Value("${opsbridge.vapi.api-key:}") String apiKey,
                      @Value("${opsbridge.vapi.phone-number-id:}") String phoneNumberId,
                      @Value("${opsbridge.vapi.assistant-id:}") String assistantId,
                      @Value("${opsbridge.vapi.base-url:https://api.vapi.ai}") String baseUrl) {
        this.client = builder.build();
        this.apiKey = apiKey;
        this.phoneNumberId = phoneNumberId;
        this.assistantId = assistantId;
        this.baseUrl = baseUrl.replaceAll("/+$", "");
    }

    public Map<?, ?> startCall(String tenantId, String customerNumber) {
        if (apiKey.isBlank() || phoneNumberId.isBlank() || assistantId.isBlank()) {
            throw new IllegalStateException("Vapi API key, phone number ID, and assistant ID are required.");
        }
        var body = Map.of(
                "phoneNumberId", phoneNumberId,
                "assistantId", assistantId,
                "customer", Map.of("number", customerNumber),
                "metadata", Map.of("tenantId", tenantId, "source", "opsbridge"));
        Map<?, ?> result = client.post()
                .uri(baseUrl + "/call/phone")
                .contentType(MediaType.APPLICATION_JSON)
                .header("Authorization", "Bearer " + apiKey)
                .body(body)
                .retrieve()
                .body(Map.class);
        return result == null ? Map.of("provider", "vapi", "status", "accepted") : result;
    }
}
