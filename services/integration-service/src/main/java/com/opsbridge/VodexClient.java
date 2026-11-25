package com.opsbridge;

import jakarta.validation.Valid;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Component
public class VodexClient {
    private final RestClient client;
    private final String apiKey;
    private final String accountUrl;
    private final String baseUrl;

    public VodexClient(
            RestClient.Builder builder,
            @Value("${opsbridge.vodex.api-key:}") String apiKey,
            @Value("${opsbridge.vodex.account-url:}") String accountUrl,
            @Value("${opsbridge.vodex.base-url:https://api.vodex.ai}") String baseUrl) {
        this.client = builder.build();
        this.apiKey = apiKey;
        this.accountUrl = accountUrl;
        this.baseUrl = baseUrl.replaceAll("/+$", "");
    }

    public boolean isConfigured() {
        return !apiKey.isBlank() && !accountUrl.isBlank();
    }

    public Map<String, Object> triggerCall(TriggerCallRequest input) {
        requireConfigured();
        if (!input.consentForCalls()) {
            throw new IllegalArgumentException("Explicit consent for calling is required.");
        }

        Map<String, Object> body = new HashMap<>();
        body.put("callList", input.callList());
        body.put("projectId", input.projectId());
        body.put("consentForCalls", true);
        if (input.campaignName() != null && !input.campaignName().isBlank()) {
            body.put("campaignName", input.campaignName());
        }

        Map<?, ?> response = client.post()
                .uri(baseUrl + "/api/v1/trigger-call")
                .contentType(MediaType.APPLICATION_JSON)
                .header("Authorization", apiKey)
                .header("dburl", accountUrl)
                .body(body)
                .retrieve()
                .body(Map.class);
        return response == null ? Map.of("status", "accepted") : copyResponse(response);
    }

    public Map<String, Object> getTranscript(String callUuid) {
        requireConfigured();
        Map<?, ?> response = client.get()
                .uri(baseUrl + "/analyze/transcript/{callUuid}", callUuid)
                .header("Authorization", apiKey)
                .retrieve()
                .body(Map.class);
        return response == null ? Map.of() : copyResponse(response);
    }

    private Map<String, Object> copyResponse(Map<?, ?> response) {
        Map<String, Object> copy = new HashMap<>();
        response.forEach((key, value) -> copy.put(String.valueOf(key), value));
        return copy;
    }

    private void requireConfigured() {
        if (!isConfigured()) {
            throw new IllegalStateException("Vodex API key and account URL are required.");
        }
    }

    public record Contact(
            @NotBlank String firstName,
            @NotBlank String lastName,
            @NotBlank String phone) { }

    public record TriggerCallRequest(
            @NotEmpty List<@Valid Contact> callList,
            @NotBlank String projectId,
            @AssertTrue(message = "Explicit consent for calls is required.") boolean consentForCalls,
            String campaignName) { }
}
