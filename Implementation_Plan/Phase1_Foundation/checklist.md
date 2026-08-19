# Phase 1: Foundation & Git Broker Setup - Checklist

**Status: COMPLETE** (verified 2026-08-19)

- [x] Verify the target Spring Boot version across all microservices. -> Spring Boot **3.3.0**.
- [x] Map the exact Spring Cloud Release Train version. -> **2023.0.2**; SCC plugin **4.1.2**, verifier 4.1.3.
- [x] Add `<dependencyManagement>` for `spring-cloud-dependencies`. -> in `CommonLibrary/pom.xml`.
- [x] Inject `spring-cloud-starter-contract-verifier` into all Producer test scopes. -> present in **17/17** services.
- [x] Inject `spring-cloud-starter-contract-stub-runner` into all Consumer test scopes. -> present in **17/17** services.
- [x] Verify the Git repository is reachable. -> `git ls-remote` against the GitHub broker succeeds;
      the local `file://` clone also clones cleanly.
- [x] Point every service at one broker URL. -> all 26 occurrences across three surfaces
      (YAML `stubrunner.repositoryRoot`, pom `contractsRepositoryUrl`, `@AutoConfigureStubRunner`)
      resolve to the local workspace clone. Enforced by `validate_broker_url.py`.

## Deliberately NOT done

- [ ] ~~Configure `<contractsRepositoryUrl>` in Consumer poms~~ - **rejected, by design.**
      The Maven plugin decodes `%20` and then fails with `Illegal character in path at index 40`,
      so a workspace path containing a space cannot be used there. Producers read their own
      `src/test/resources/contracts` instead. Note `git clone` and the *runtime* stub runner both
      accept the encoded form - only the Maven plugin does not.

## Moved out of this phase

- `GIT_TOKEN` / CI authentication -> tracked in **Phase 8**, where it is actually exercised.
  It currently exists only as prose in plan files: no `.env.example`, no CI secret, no workflow wiring.
