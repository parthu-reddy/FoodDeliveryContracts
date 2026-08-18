# Phase 6: CI/CD Pipeline Enforcement & Governance — Checklist

- [ ] Generate a GitHub Personal Access Token (PAT) with `repo` permissions for the `FoodDeliveryContracts` repository.
- [ ] Add the PAT to your CI/CD secrets manager (e.g., GitHub Actions Secrets, Jenkins Credentials).
- [ ] Update all Producer `pom.xml` files to inject `${env.GIT_TOKEN}` into `<contractsRepositoryUrl>`.
- [ ] Update all Consumer `application-test.yml` files to inject `${GIT_TOKEN}` into `stubrunner.repositoryRoot`.
- [ ] Modify the Producer CI/CD pipeline yaml to execute `mvn clean deploy` (or the specific push-stubs goal) only on the `develop` and `main` branches.
- [ ] Verify that Consumer CI/CD pipelines successfully download the stubs during `mvn clean test` without authentication errors.
- [ ] Implement a test failure scenario: intentionally break a contract in `WalletService` on a feature branch and ensure the CI pipeline blocks the merge.
