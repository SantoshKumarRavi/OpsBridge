package com.opsbridge;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class VoicePolicyConfigurationTest {
    @Autowired
    private VoicePolicyProperties properties;

    @Test
    void bindsDemoTenantPolicyFromApplicationConfiguration() {
        var policy = properties.tenants().get("demo-tenant");

        assertTrue(policy != null);
        assertEquals("Asia/Kolkata", policy.timeZone());
        assertEquals("09:00", policy.allowedStart().toString());
        assertEquals("17:00", policy.allowedEnd().toString());
    }
}
