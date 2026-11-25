package com.opsbridge;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class VoiceConsentClientTest {
    private MockRestServiceServer server;
    private VoiceConsentClient client;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder();
        server = MockRestServiceServer.bindTo(builder).build();
        client = new VoiceConsentClient(builder, "https://compliance.test", "internal-token");
    }

    @Test
    void acceptsOnlyTenantScopedEligibleContactFromTrustedComplianceApi() {
        server.expect(requestTo("https://compliance.test/api/v1/voice/contacts/eligibility?phoneNumber=%2B12025550100"))
                .andExpect(method(HttpMethod.GET))
                .andExpect(header("X-Tenant-Id", "tenant-a"))
                .andExpect(header("X-Internal-Service-Token", "internal-token"))
                .andRespond(withSuccess("{\"eligible\":true,\"reason\":\"eligible\"}", MediaType.APPLICATION_JSON));

        client.requireEligible("tenant-a", "+12025550100");
        server.verify();
    }

    @Test
    void blocksWhenConsentIsMissingOrSuppressed() {
        server.expect(requestTo("https://compliance.test/api/v1/voice/contacts/eligibility?phoneNumber=%2B12025550100"))
                .andRespond(withSuccess("{\"eligible\":false,\"reason\":\"suppressed\"}", MediaType.APPLICATION_JSON));

        var exception = assertThrows(ResponseStatusException.class, () -> client.requireEligible("tenant-a", "+12025550100"));
        org.junit.jupiter.api.Assertions.assertEquals(403, exception.getStatusCode().value());
        server.verify();
    }

    @Test
    void failsClosedWhenComplianceApiCannotBeReached() {
        server.expect(requestTo("https://compliance.test/api/v1/voice/contacts/eligibility?phoneNumber=%2B12025550100"))
                .andRespond(request -> { throw new java.io.IOException("offline"); });

        var exception = assertThrows(ResponseStatusException.class, () -> client.requireEligible("tenant-a", "+12025550100"));
        org.junit.jupiter.api.Assertions.assertEquals(503, exception.getStatusCode().value());
        server.verify();
    }
}
