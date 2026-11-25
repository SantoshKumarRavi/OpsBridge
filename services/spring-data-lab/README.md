# Spring Data screening lab

Independent Spring Boot/MVC + Spring Data JPA/Hibernate + Maven microservice using H2. It teaches dependency injection, repository abstractions, transactions, indexes, SQL schema evolution, and JUnit 5 without becoming a second canonical OpsBridge case database.

The screening endpoint accepts only **synthetic PEP/sanctions flags** supplied by the caller. It demonstrates an illustrative risk score and routes flagged results to manual review; it does not perform identity verification or query KYC/AML/sanctions/adverse-media providers. It is not a compliance decision. Never use real personal information or present this as a real screening service.

Run its service-policy unit test with `mvn -f services/spring-data-lab/pom.xml test`. The test passes locally and GitHub Actions is configured to run it on pushes and pull requests. It verifies the synthetic flag remains advisory and is routed to manual review; it does not exercise the database or HTTP endpoint.
