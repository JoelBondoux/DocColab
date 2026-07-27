# Delivery Pipeline

> Maintained by AtlasMind (Project Dashboard → Delivery). This is the human-readable
> mirror of `delivery.json`; edit either and the other is kept in sync from the dashboard.

A **stage** is one environment your software runs in. A **promotion** ("push") moves a
build from one stage to the next — safely, with a backup taken first and the listed
checks required to pass before anything changes.

## Stages

### 1. Local — `local`

Your own machine. Where you write and run code day to day. Data here is disposable — nothing your users see lives at this stage.

- **Branch:** — (working tree)
- **Hosting:** localhost
- **Config source:** — (location only — secret values stay in your secret store)
- **Data:** No application database
- **Backup before promotion:** not required

### 2. Staging — `staging`

A production-like rehearsal environment. Changes land here first so they can be tested against realistic data and settings before any real users are affected.

- **Branch:** `main`
- **Hosting:** —
- **Config source:** — (location only — secret values stay in your secret store)
- **Data:** No application database
- **Backup before promotion:** not required

### 3. Production (planned) — `production` 🔒 protected

Planned PyPI package distribution. This stage is not active until trusted
publishing and an automated release workflow are configured.

- **Branch:** `main`
- **Hosting:** PyPI (planned)
- **Config source:** — (location only — secret values stay in your secret store)
- **Data:** No application database
- **Backup before promotion:** not required

## Promotions

### Local → Staging

Every promotion runs the same guarded sequence:

1. **Preflight gate** — the required checks below must all pass, or the promotion aborts.
2. **Backup** — optional for this target.
3. **Promote** — the build is merged/tagged forward. AtlasMind never force-pushes.
4. **Verify** — the target is health-checked after deploy.

- **Required checks:** `Working tree clean`, `Lint passes`, `Tests pass`
- **Required CI status checks:** `Dependency review`
- **Promotion mechanism:** direct merge/tag
- **Approval:** not required
- **Version bump required:** yes
- **Changelog entry required:** yes

### Staging → Production

Every promotion runs the same guarded sequence:

1. **Preflight gate** — the required checks below must all pass, or the promotion aborts.
2. **Backup** — optional for this target.
3. **Promote** — the build is merged/tagged forward. AtlasMind never force-pushes.
4. **Verify** — the target is health-checked after deploy.

- **Required checks:** `Working tree clean`, `Lint passes`, `Tests pass`
- **Required CI status checks:** `Dependency review`
- **Promotion mechanism:** direct merge/tag
- **Approval:** a human must sign off before anything runs
- **Version bump required:** yes
- **Changelog entry required:** yes

---

_Last updated: 2026-07-27T00:05:32.884Z._
