package com.opsbridge.discovery.provider;

import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ProviderController {
    private final String serviceName;
    private final String instanceId;
    private final int port;
    private final String message;

    public ProviderController(
            @Value("${spring.application.name:synthetic-provider}") String serviceName,
            @Value("${eureka.instance.instance-id:local-provider}") String instanceId,
            @Value("${server.port:8080}") int port,
            @Value("${provider.message:Hello from a local provider instance}") String message) {
        this.serviceName = serviceName;
        this.instanceId = instanceId;
        this.port = port;
        this.message = message;
    }

    @GetMapping("/v1/provider/instance")
    public Map<String, Object> instance() {
        return Map.of(
                "service", serviceName,
                "instanceId", instanceId,
                "port", port,
                "message", message);
    }
}
