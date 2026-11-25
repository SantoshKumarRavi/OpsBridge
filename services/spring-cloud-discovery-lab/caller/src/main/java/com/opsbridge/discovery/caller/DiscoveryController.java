package com.opsbridge.discovery.caller;

import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.client.ServiceInstance;
import org.springframework.cloud.client.discovery.DiscoveryClient;
import org.springframework.cloud.client.loadbalancer.LoadBalanced;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

@RestController
public class DiscoveryController {
    private final RestClient.Builder restClientBuilder;
    private final DiscoveryClient discoveryClient;
    private final String providerServiceId;

    public DiscoveryController(
            @LoadBalanced RestClient.Builder restClientBuilder,
            DiscoveryClient discoveryClient,
            @Value("${discovery.provider-service-id:synthetic-provider}") String providerServiceId) {
        this.restClientBuilder = restClientBuilder;
        this.discoveryClient = discoveryClient;
        this.providerServiceId = providerServiceId;
    }

    @GetMapping("/v1/discovery/call")
    public Map<String, Object> callProvider() {
        Map<?, ?> response = restClientBuilder.build()
                .get()
                .uri("http://" + providerServiceId + "/v1/provider/instance")
                .retrieve()
                .body(Map.class);
        return Map.of("discoveredService", providerServiceId, "provider", response);
    }

    @GetMapping("/v1/discovery/instances")
    public List<Map<String, Object>> instances() {
        return discoveryClient.getInstances(providerServiceId).stream()
                .map(this::describe)
                .toList();
    }

    private Map<String, Object> describe(ServiceInstance instance) {
        return Map.of(
                "serviceId", instance.getServiceId(),
                "instanceId", instance.getInstanceId() == null ? "unknown" : instance.getInstanceId(),
                "host", instance.getHost(),
                "port", instance.getPort());
    }
}
