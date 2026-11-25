package com.opsbridge;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class VapiClientTest {
    private MockRestServiceServer server;
    private VapiClient client;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder();
        server = MockRestServiceServer.bindTo(builder).build();
        client = new VapiClient(builder, "test-key", "phone-1", "assistant-1", "https://vapi.test/");
    }

    @Test
    void sendsTenantMetadataAndCallConfigurationToVapi() {
        server.expect(requestTo("https://vapi.test/call/phone"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("Authorization", "Bearer test-key"))
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(content().json("""
                        {"phoneNumberId":"phone-1","assistantId":"assistant-1",
                         "customer":{"number":"+12025550100"},
                         "metadata":{"tenantId":"tenant-a","source":"opsbridge"}}
                        """))
                .andRespond(withSuccess("{\"id\":\"call-1\",\"status\":\"queued\"}", MediaType.APPLICATION_JSON));

        var response = client.startCall("tenant-a", "+12025550100");

        assertEquals("call-1", response.get("id"));
        server.verify();
    }
}
