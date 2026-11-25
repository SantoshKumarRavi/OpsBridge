# Spring Cloud discovery, config, and load-balancing lab

This isolated lab contains four Spring Boot applications:

- **Config Server** serves versioned-in-repository sample configuration from its classpath using the native backend.
- **Eureka registry** stores service registrations and instance heartbeats.
- **Two synthetic provider instances** register as `synthetic-provider` and return their instance identity plus centrally served configuration.
- **Discovery caller** reads registered instances and calls the provider using a virtual service URL through Spring Cloud LoadBalancer.

The example uses Spring Boot 3.5.16, Spring Cloud 2025.0.3, and targets Java 21. Spring's compatibility table pairs the 2025.0 release train with Spring Boot 3.5; Spring Boot 3.5.16 supports Java 17 through Java 25. See the [Spring Cloud release page](https://spring.io/projects/spring-cloud/) and [Spring Boot system requirements](https://docs.spring.io/spring-boot/3.5/system-requirements.html).

## Build and start

From the repository root, build all applications:

```bash
mvn -f services/spring-cloud-discovery-lab/pom.xml package
```

Then start the local topology:

```bash
docker compose -f services/spring-cloud-discovery-lab/compose.yml --profile discovery up --build
```

If Docker is unavailable, the local-process E2E script starts the four built JARs on separate local ports, checks Config Server and Eureka, verifies both providers are discovered and called through the load-balanced service ID, then stops only the processes it started:

```powershell
pwsh -File scripts/verify-spring-cloud-discovery.ps1
```

Both the PowerShell runner and the GitHub Actions Docker Compose job use `scripts/verify_spring_cloud_discovery.py` to assert the centrally served value, both registered instances, and responses from both instances through the caller.

Open the Eureka dashboard at `http://localhost:8761`. The Config Server serves the caller settings at `http://localhost:8888/discovery-caller/default` and provider settings at `http://localhost:8888/synthetic-provider/default`.

Call the discovery caller repeatedly and inspect which provider instances answered:

```bash
curl http://localhost:8090/v1/discovery/instances
curl http://localhost:8090/v1/discovery/call
```

The caller uses a load-balanced `RestClient.Builder` and the service ID, not a provider hostname or fixed IP. Docker Compose starts two provider containers so the discovered instance set and selection can be observed.

Stop the lab with:

```bash
docker compose -f services/spring-cloud-discovery-lab/compose.yml --profile discovery down
```

This topology is for local learning. The native Config Server backend is not a production configuration repository. Eureka is a registry, not a secret store; TLS, authentication, high availability, config encryption, access control, and production failure policies are intentionally outside this example. The lab is separate from the main OpsBridge request path.
