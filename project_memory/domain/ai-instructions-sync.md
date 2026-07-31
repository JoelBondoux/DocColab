# AI Instructions (unified)

> Two-way synced on 2026-07-26. Reconciled superset across all detected AI assistants.
> AtlasMind mirrors this set into each tool's instruction file inside a managed block.

## Shared Project Instructions (managed by AtlasMind)

> Unified across all detected AI assistants. Re-run AtlasMind → Settings → AI Instructions →
> "Align all instruction sets" to refresh. Content inside this block is overwritten on each sync.

### safety

- Default to the safest reasonable behavior.

### documentation

- Keep project knowledge structured, current, and reviewable.

### approval

- Prefer explicit approvals and traceable automation for risky work.

### versioning

- Treat documentation, versioning, and release hygiene as part of correctness.

### bug classification

- Safety and security regressions are correctness bugs, not polish work.

### architecture

- Long-term project context belongs in the SSOT under project_memory/.

### credentials

- Provider credentials live in SecretStorage, not in project memory or source.

### branching

- Use short-lived branches from protected `main`; merge only through reviewed, green pull requests.
