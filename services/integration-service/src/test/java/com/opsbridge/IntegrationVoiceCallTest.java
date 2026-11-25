package com.opsbridge;

import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalTime;
import java.time.ZoneOffset;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import org.springframework.web.server.ResponseStatusException;

class IntegrationVoiceCallTest {
    private IntegrationController controller(VoiceConsentClient consentClient, VapiClient vapiClient) {
        var properties = new VoicePolicyProperties(Map.of("tenant-a",
                new VoicePolicyProperties.TenantPolicy("UTC", LocalTime.MIDNIGHT, LocalTime.of(23, 59))));
        var clock = Clock.fixed(Instant.parse("2026-11-20T12:00:00Z"), ZoneOffset.UTC);
        return new IntegrationController(mock(VodexClient.class), vapiClient,
                new VoiceCallPolicy(properties, clock), consentClient);
    }

    @Test
    void complianceDenialStopsBeforeVapiCall() {
        var consentClient = mock(VoiceConsentClient.class);
        var vapiClient = mock(VapiClient.class);
        doThrow(new ResponseStatusException(org.springframework.http.HttpStatus.FORBIDDEN, "not eligible"))
                .when(consentClient).requireEligible("tenant-a", "+12025550100");
        var controller = controller(consentClient, vapiClient);

        assertThrows(ResponseStatusException.class, () -> controller.startVoiceCall(
                new IntegrationController.VoiceCall("+12025550100"), "tenant-a"));
        verify(consentClient).requireEligible("tenant-a", "+12025550100");
        verifyNoInteractions(vapiClient);
    }

    @Test
    void vapiIsInvokedOnlyAfterLocalWindowAndComplianceEligibilityPass() {
        var consentClient = mock(VoiceConsentClient.class);
        var vapiClient = mock(VapiClient.class);
        var controller = controller(consentClient, vapiClient);

        controller.startVoiceCall(new IntegrationController.VoiceCall("+12025550100"), "tenant-a");

        verify(consentClient).requireEligible("tenant-a", "+12025550100");
        verify(vapiClient).startCall("tenant-a", "+12025550100");
    }
}
