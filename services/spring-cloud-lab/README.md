# Spring Cloud Circuit Breaker lab

An isolated Spring Cloud Circuit Breaker + Resilience4j exercise. `/v1/resilience/call` calls a local synthetic provider through a circuit breaker and returns a safe fallback when the provider fails. `/v1/resilience/dependency` is the simulator; set `DEMO_SIMULATE_FAILURE=true` to make it return 503. Repeated calls open the breaker according to the configured four-call window. Actuator health and metrics are exposed for observation.

Run with the `spring-cloud-lab` Docker Compose profile. This service has no applicant data, provider credentials, or access to the core API. It demonstrates failure isolation/fallback; it is not a full service-discovery or production resilience configuration.

The Spring Cloud BOM is pinned to the release train compatible with Spring Boot 3.4.x, as listed on the [official Spring Cloud release page](https://spring.io/projects/spring-cloud/).
