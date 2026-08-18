# Phase 1: Foundation & Git Broker Setup — Checklist

- [ ] Verify the target Spring Boot version across all 16 microservices.
- [ ] Map the exact Spring Cloud Release Train version required (e.g., 2023.0.x for Spring Boot 3.2).
- [ ] Add `<dependencyManagement>` for `spring-cloud-dependencies` to `CommonLibrary` or individual `pom.xml` files.
- [ ] Inject `spring-cloud-starter-contract-verifier` into all Producer test scopes.
- [ ] Inject `spring-cloud-starter-contract-stub-runner` into all Consumer test scopes.
- [ ] Configure the `spring-cloud-contract-maven-plugin` in Consumer `pom.xml` files with the `<contractsRepositoryUrl>` pointing to the Git repo.
- [ ] Verify the Git repository is accessible via the CLI (`git ls-remote https://github.com/parthu-reddy/FoodDeliveryContracts.git`).
- [ ] Document the environment variables needed for CI/CD Git authentication (e.g., `GIT_TOKEN`).
