<!-- atlasmind:testing-protocols:start -->
## Testing Protocols (managed by AtlasMind)

> Auto-generated from `project_memory/index/testing-config.json`. Do not edit by hand —
> changes are overwritten on the next sync. Update the matrix in the AtlasMind Settings → Testing page instead.

This project enforces **4** testing methodologies. When writing or verifying tests, follow the applicable protocols below and report the checks, assertions, or verification artifacts you produced before concluding.

### TDD

- **What:** Test-Driven Development — red-green-refactor loop
- **When to apply:** Any project where correctness matters and requirements can be expressed as assertions before the code is written. Especially valuable for greenfield features and critical business logic.
- **Key tools:** Jest, Vitest, Mocha, pytest, JUnit, RSpec, Go testing
- **Primary owner:** Test Developer

### Unit Testing

- **What:** Isolated function and class-level tests
- **When to apply:** All projects. Start here. Fast, cheap, and gives precise regression signals. Should be the largest layer of your test pyramid.
- **Key tools:** Jest, Vitest, Mocha, pytest, JUnit, NUnit, xUnit, Go testing, Minitest
- **Primary owner:** Test Developer

### Continuous / Shift-Left

- **What:** Automated testing embedded throughout CI/CD — tests run on every commit, earliest possible feedback
- **When to apply:** Any project with a CI/CD pipeline. Essential for teams delivering frequent releases or practising trunk-based development. Shift-left means pushing tests earlier: linting, type checks, and unit tests on pre-commit; integration and E2E on PR; performance and security on merge.
- **Key tools:** GitHub Actions, GitLab CI, Jenkins, CircleCI, Azure DevOps, Buildkite, Husky / pre-commit hooks, Test Impact Analysis (Vitest, Jest)
- **Primary owner:** Test Developer

### Security

- **What:** SAST / DAST and dependency vulnerability scanning
- **When to apply:** Any application handling authentication, payments, PII, or sensitive data. Should be part of CI for all production software.
- **Key tools:** Snyk, OWASP ZAP, Semgrep, Trivy, CodeQL, Dependabot, npm audit, OWASP Dependency-Check
- **Primary owner:** Test Developer
<!-- atlasmind:testing-protocols:end -->

<!-- atlasmind:shared-instructions:start -->
## Directives

- **Safety:** Default to the safest reasonable behavior.
- **Documentation:** Keep project knowledge structured, current, and reviewable.
- **Approval:** Prefer explicit approvals and traceable automation for risky work.
- **Versioning:** Treat documentation, versioning, and release hygiene as part of correctness.
- **Bug Classification:** Safety and security regressions are correctness bugs, not polish work.
- **Architecture:** Long-term project context belongs in the SSOT under project_memory/.
- **Credentials:** Provider credentials live in SecretStorage, not in project memory or source.
- **Branching:** 'develop' is the routine integration branch and 'master' is the protected release-ready branch.
<!-- atlasmind:shared-instructions:end -->
