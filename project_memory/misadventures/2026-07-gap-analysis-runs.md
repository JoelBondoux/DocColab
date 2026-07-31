# Superseded gap-analysis runs

Several automated runs on 2026-07-26 and 2026-07-27 operated from an incorrect
working directory, produced unsupported conclusions, or wrote unrelated test
configuration. Their raw transcripts and generated run records were removed
because they were stale telemetry rather than durable project knowledge.

The durable lessons are:

- verify the repository root before acting;
- keep analysis tasks read-only unless implementation is explicitly requested;
- derive testing status from executable checks, not orchestration metadata;
- store reviewed decisions and summaries in the SSOT, never raw transcripts,
  credentials, personal contact handles, or private document content.

`docs/GAP_ANALYSIS.md` is the superseding evidence-backed assessment.
