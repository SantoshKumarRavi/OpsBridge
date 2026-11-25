package com.opsbridge.discovery.provider;

import static org.junit.jupiter.api.Assertions.assertEquals;
import org.junit.jupiter.api.Test;

class ProviderControllerTest {
    @Test
    void exposesInstanceIdentityAndCentralConfigurationForLoadBalancingDemo() {
        var controller = new ProviderController(
                "synthetic-provider", "provider-test-1", 8082, "configured by config server");

        var result = controller.instance();

        assertEquals("synthetic-provider", result.get("service"));
        assertEquals("provider-test-1", result.get("instanceId"));
        assertEquals(8082, result.get("port"));
        assertEquals("configured by config server", result.get("message"));
    }
}
