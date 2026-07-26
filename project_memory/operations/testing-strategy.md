# Testing Strategy Playbook

> Managed by AtlasMind. Regenerated from `project_memory/index/testing-config.json` on each
> scaffold run. Hand edits to this file are overwritten — change the Settings → Testing matrix instead.

**Detected stack:** Python · archetype: api
**Active methodologies:** 4 / 23

## TDD

Test-Driven Development — red-green-refactor loop

- **When to apply:** Any project where correctness matters and requirements can be expressed as assertions before the code is written. Especially valuable for greenfield features and critical business logic.
- **Key tools:** Jest, Vitest, Mocha, pytest, JUnit, RSpec, Go testing
- **Trade-offs:** Requires discipline to write the test first; initial velocity feels slower before the refactor payoff. Poorly scoped tests can become brittle.
- **Set up (Python):** pip install pytest  •  run: pytest
- **Starter file:** `tests/test_example.py`

## Unit Testing

Isolated function and class-level tests

- **When to apply:** All projects. Start here. Fast, cheap, and gives precise regression signals. Should be the largest layer of your test pyramid.
- **Key tools:** Jest, Vitest, Mocha, pytest, JUnit, NUnit, xUnit, Go testing, Minitest
- **Trade-offs:** Tests of implementation details (not behaviour) become expensive to maintain. Mocking boundaries can give false confidence at integration points.
- **Set up (Python):** pip install pytest  •  run: pytest
- **Starter file:** `tests/test_example.py`

## Continuous / Shift-Left

Automated testing embedded throughout CI/CD — tests run on every commit, earliest possible feedback

- **When to apply:** Any project with a CI/CD pipeline. Essential for teams delivering frequent releases or practising trunk-based development. Shift-left means pushing tests earlier: linting, type checks, and unit tests on pre-commit; integration and E2E on PR; performance and security on merge.
- **Key tools:** GitHub Actions, GitLab CI, Jenkins, CircleCI, Azure DevOps, Buildkite, Husky / pre-commit hooks, Test Impact Analysis (Vitest, Jest)
- **Trade-offs:** Requires significant upfront investment in pipeline configuration and test suite speed. Slow suites become a bottleneck on developer velocity. Shallow-but-fast suites give false safety if coverage is insufficient.
- **Starter file:** _guidance only for this methodology on the detected language — see Key tools above._

## Security

SAST / DAST and dependency vulnerability scanning

- **When to apply:** Any application handling authentication, payments, PII, or sensitive data. Should be part of CI for all production software.
- **Key tools:** Snyk, OWASP ZAP, Semgrep, Trivy, CodeQL, Dependabot, npm audit, OWASP Dependency-Check
- **Trade-offs:** SAST tools produce false positives that need triage. DAST requires a running environment. Both add CI time and require a process for managing findings.
- **Set up (Python):** pip install bandit pip-audit  •  run: bandit -r . && pip-audit
- **Starter file:** _guidance only for this methodology on the detected language — see Key tools above._
