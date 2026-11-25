package com.opsbridge.cloudlab;

import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.client.circuitbreaker.CircuitBreakerFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;

@RestController
@RequestMapping("/v1/resilience")
public class ResilienceDemoController {
    private final CircuitBreakerFactory<?, ?> circuitBreakers;
    private final RestClient restClient;
    private final String dependencyUrl;
    private final boolean simulateFailure;

    public ResilienceDemoController(CircuitBreakerFactory<?, ?> circuitBreakers,
                                    RestClient.Builder restClientBuilder,
                                    @Value("${demo.dependency-url:http://localhost:8014/v1/resilience/dependency}") String dependencyUrl,
                                    @Value("${demo.simulate-failure:false}") boolean simulateFailure) {
        this.circuitBreakers = circuitBreakers;
        this.restClient = restClientBuilder.build();
        this.dependencyUrl = dependencyUrl;
        this.simulateFailure = simulateFailure;
    }

    @GetMapping("/dependency")
    public Map<String, String> dependency() {
        if (simulateFailure) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Synthetic dependency outage");
        }
        return Map.of("service", "screening-provider-simulator", "status", "available");
    }

    @GetMapping("/call")
    public Map<String, String> callDependency() {
        return circuitBreakers.create("screening-provider").run(
                () -> restClient.get().uri(dependencyUrl).retrieve().body(Map.class),
                failure -> Map.of("service", "screening-provider", "status", "fallback", "reason", "dependency unavailable; retry later"));
    }
}
