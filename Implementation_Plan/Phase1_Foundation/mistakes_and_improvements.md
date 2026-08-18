# Phase 1: Foundation - Mistakes and Improvements

## Mistakes & Pitfalls Encountered
1. **Manual Bash Commands over Programmatic Validation**:
   - *Mistake*: Relying on `grep` and `find` to validate XML/YAML changes across multiple microservices. This led to missed files, false positives, and incomplete migrations.
   - *Improvement*: Always use strict AST-based programmatic scripts (e.g., Python `xml.etree.ElementTree` for `pom.xml`, and `yaml.safe_load` for `application.yml`) to enforce exact validation criteria.

2. **Missing Experimental Flags for ByteBuddy**:
   - *Mistake*: When compiling and running tests on modern JDK versions (Java 26), Mockito/ByteBuddy failed because it doesn't officially support the JVM yet.
   - *Improvement*: Include `<argLine>-Dnet.bytebuddy.experimental=true</argLine>` in the `maven-surefire-plugin` configuration for projects running on newer/beta JDK versions, or ensure JVM args are properly set during `mvn clean test`.

3. **Incomplete Dependency Inclusions**:
   - *Mistake*: Added `spring-cloud-starter-contract-verifier` but forgot `spring-cloud-starter-contract-stub-runner` in some POM files.
   - *Improvement*: Maintain a single source of truth for contract-testing dependencies and programmatically ensure all POM files match it exactly.

## Agent/Process Improvements
- **Strict Validation Plans**: Never execute a mass script without a documented, verified, and exact programmatic `validation.md` script.
- **Fail-fast Testing**: Instead of editing all services and hoping they compile, test the foundation on 1 or 2 services to uncover hidden issues (like the ByteBuddy error or missing test directories) before scaling to all 16 microservices.
