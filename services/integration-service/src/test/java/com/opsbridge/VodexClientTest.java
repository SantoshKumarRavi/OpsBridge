package com.opsbridge;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.headerDoesNotExist;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class VodexClientTest {
    private MockRestServiceServer server;
    private VodexClient client;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder();
        server = MockRestServiceServer.bindTo(builder).build();
        client = new VodexClient(builder, "test-api-key", "account-dburl", "https://vodex.test/");
    }

    @Test
    void triggersCallsWithVodexHeadersAndExplicitConsent() {
        server.expect(requestTo("https://vodex.test/api/v1/trigger-call"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("Authorization", "test-api-key"))
                .andExpect(header("dburl", "account-dburl"))
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(content().json("""
                        {
                          "projectId":"project-123",
                          "consentForCalls":true,
                          "campaignName":"onboarding-demo",
                          "callList":[{"firstName":"Asha","lastName":"Rao","phone":"+911234567890"}]
                        }
                        """))
                .andRespond(withSuccess("""
                        {"success":true,"data":{"callsTriggered":1,"callIds":["call-789"]}}
                        """, MediaType.APPLICATION_JSON));

        var result = client.triggerCall(new VodexClient.TriggerCallRequest(
                List.of(new VodexClient.Contact("Asha", "Rao", "+911234567890")),
                "project-123",
                true,
                "onboarding-demo"));

        assertEquals(Boolean.TRUE, result.get("success"));
        server.verify();
    }

    @Test
    void refusesToTriggerCallsWithoutConsentBeforeMakingARequest() {
        var input = new VodexClient.TriggerCallRequest(
                List.of(new VodexClient.Contact("Asha", "Rao", "+911234567890")),
                "project-123",
                false,
                null);

        assertThrows(IllegalArgumentException.class, () -> client.triggerCall(input));
        server.verify();
    }

    @Test
    void fetchesCallTranscriptUsingOnlyTheAuthorizationHeader() {
        server.expect(requestTo("https://vodex.test/analyze/transcript/call-789"))
                .andExpect(method(HttpMethod.GET))
                .andExpect(header("Authorization", "test-api-key"))
                .andExpect(headerDoesNotExist("dburl"))
                .andRespond(withSuccess("""
                        {"call_uuid":"call-789","transcript":"Hello there"}
                        """, MediaType.APPLICATION_JSON));

        var result = client.getTranscript("call-789");

        assertEquals("Hello there", result.get("transcript"));
        server.verify();
    }

    @Test
    void failsClosedWhenVodexCredentialsAreMissing() {
        VodexClient unconfigured = new VodexClient(RestClient.builder(), "", "", "https://vodex.test");
        var input = new VodexClient.TriggerCallRequest(
                List.of(new VodexClient.Contact("Asha", "Rao", "+911234567890")),
                "project-123",
                true,
                null);

        assertThrows(IllegalStateException.class, () -> unconfigured.triggerCall(input));
    }
}
