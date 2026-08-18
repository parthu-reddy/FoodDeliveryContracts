# Phase 1: Foundation & Git Broker Setup — Plan

## Objective
Establish the foundational infrastructure for Consumer-Driven Contract (CDC) Testing across all 16 microservices. This involves setting up the central Git repository as the Contract Broker and configuring the Spring Boot build files to utilize the `spring-cloud-starter-contract-*` libraries.

## 1. Git Broker Setup
- **Repository Location:** `https://github.com/parthu-reddy/FoodDeliveryContracts.git`
- **Structure within Git:**
  Unlike Maven where contracts are stored in `.jar` files, the Git approach requires a specific folder structure for Spring Cloud Contract to resolve stubs correctly:
  ```
  META-INF/
    groupId/
      artifactId/
        version/
          contracts/
            (groovy files go here)
  ```
- **Action:** We must configure the Consumer projects to push to this structure, and Producer projects to read from it.

## 2. Dependency Management
All microservices use Spring Boot. We need to add the Spring Cloud Contract BOM (Bill of Materials) to ensure version consistency.

### 2.1 Producer Services (The ones providing APIs/Events)
Add the verifier plugin to the `pom.xml`:
```xml
<dependency>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-starter-contract-verifier</artifactId>
    <scope>test</scope>
</dependency>
```

### 2.2 Consumer Services (The ones calling APIs/Listening to Events)
Add the stub-runner dependency to the `pom.xml`:
```xml
<dependency>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-starter-contract-stub-runner</artifactId>
    <scope>test</scope>
</dependency>
```

## 3. Global Configuration Properties
Create a standard configuration block that will be used in the `application-test.yml` of all Producer services:
```yaml
stubrunner:
  stubsMode: REMOTE
  repositoryRoot: git://https://github.com/parthu-reddy/FoodDeliveryContracts.git
  ids: 
    - com.fooddelivery:restaurant-service:+:stubs
```

## 4. Edge Cases to Consider
1. **Authentication:** CI/CD runners (like Jenkins/GitHub Actions) will need SSH keys or PATs (Personal Access Tokens) injected as environment variables to clone the Git repository during the `mvn test` phase. Local developer machines will use their existing Git credentials.
2. **Version Pinning:** We must pin the Spring Cloud Contract version to match the Spring Boot version used in the project (e.g., Spring Boot 3.2.x requires Spring Cloud 2023.0.x). We cannot assume a random version.
