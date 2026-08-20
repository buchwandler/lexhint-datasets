---
schema_version: 1
object_type: plan
file_version: v2
task_id: task-0001
plan_id: plan-v1
version: 1
plan_version: 1
status: accepted
created_at: "2026-08-20T14:36:42Z"
created_by:
  actor_type: agent
  actor_name: nahrstaedt
  tool: null
  session_id: null
  host: wsl
  pid: 3241115
  actor_id: null
  role: null
  harness_id: null
  command_pid: null
  pid_scope: null
supersedes: null
question_refs: []
criteria:
  - id: ac-0001
    text:
      Validation opens artifacts through Lexhint.Lexicon and read_artifact_status,
      uses only generic PRAGMA quick_check for SQLite integrity, and has no schema-4
      or senses.word assumptions.
    mandatory: true
  - id: ac-0002
    text:
      datasets.toml defines enabled cs, de, en, es, fr, it, and pt languages plus
      lexical, runtime, and rich variants with canonical capabilities and configurable
      validation probes or thresholds.
    mandatory: true
  - id: ac-0003
    text:
      The validator checks full coverage, language, schema, configured capabilities,
      lexical behavior, capability behavior, configured count thresholds, and expected
      capability errors for absent operations.
    mandatory: true
  - id: ac-0004
    text:
      Packaging accepts multiple language and variant artifacts, rejects duplicate
      slots and provenance or compatibility mismatches, and emits asset names containing
      language, variant, schema, and dataset version.
    mandatory: true
  - id: ac-0005
    text:
      A release is represented by one datasets-v2.json artifacts array containing
      actual Lexhint metadata, capability-aware counts, frequency provenance, source
      provenance, checksums, sizes, and build metadata.
    mandatory: true
  - id: ac-0006
    text:
      Packaging writes one complete sorted SHA256SUMS file, deterministic gzip output
      with stable member metadata, attribution, and language-neutral release notes without
      per-artifact overwrites.
    mandatory: true
  - id: ac-0007
    text:
      Official publish mode requires and verifies an upstream source SHA-256, and
      the workflow builds all artifacts from one verified local source while keeping
      publish false by default and refusing existing release tags.
    mandatory: true
  - id: ac-0008
    text:
      The GitHub Actions workflow is data-driven for all configured languages and
      variants, validates and assembles a single release candidate, and publishes only
      after complete manifest, checksum, attribution, and asset checks pass.
    mandatory: true
  - id: ac-0009
    text:
      Lexhint provides a tested dictionary project API and CLI that creates fresh
      subset artifacts only when target capabilities are a subset of a full source,
      preserving provenance and runtime behavior.
    mandatory: true
  - id: ac-0010
    text:
      The dataset workflow uses one rich build per language followed by Lexhint-owned
      runtime and lexical projections, and projection tests cover equivalence with direct
      fixture builds.
    mandatory: true
  - id: ac-0011
    text:
      Tests use tiny local Lexhint fixtures to cover lexical, runtime, and rich
      artifacts, manifest aggregation, duplicate and mismatch rejection, missing optional
      counts, checksums, stable gzip metadata, release notes, source pinning, and capability
      behavior.
    mandatory: true
  - id: ac-0012
    text:
      README.md and DATA_SOURCES.md document variants, supported languages, v2 manifests,
      naming, local validation, staging and publishing, source and frequency provenance,
      and attribution boundaries; generated SQLite files remain untracked.
    mandatory: true
todos:
  - id: plan-todo-0001
    text:
      Define datasets.toml and shared configuration/loading models for supported
      languages, variants, probes, thresholds, source policy, and canonical capability
      tuples.
    done: false
    created_at: "2026-08-20T14:36:42Z"
    updated_at: "2026-08-20T14:36:42Z"
    source: plan
    mandatory: true
    status: open
    active_at: null
    blocked_reason: null
    done_at: null
    skipped_at: null
    completed_by: null
    completed_in_harness: null
    skipped_by: null
    evidence: []
    artifact_refs: []
    change_refs: []
    command_refs: []
    source_plan_id: null
    source_question_ids: []
    validation_hint:
      Run dataset configuration unit tests and inspect every configured
      language and variant.
  - id: plan-todo-0002
    text:
      Rewrite scripts/validate.py around Lexhint public artifact APIs, generic integrity
      checks, configurable probes and thresholds, capability behavior, and structured
      JSON diagnostics.
    done: false
    created_at: "2026-08-20T14:36:42Z"
    updated_at: "2026-08-20T14:36:42Z"
    source: plan
    mandatory: true
    status: open
    active_at: null
    blocked_reason: null
    done_at: null
    skipped_at: null
    completed_by: null
    completed_in_harness: null
    skipped_by: null
    evidence: []
    artifact_refs: []
    change_refs: []
    command_refs: []
    source_plan_id: null
    source_question_ids: []
    validation_hint:
      Run validator tests against tiny lexical, runtime, and rich schema-7
      fixtures.
  - id: plan-todo-0003
    text:
      Refactor packaging into per-artifact and release assembly flows, including
      capability-aware status counts, deterministic gzip, v2 manifest, provenance invariants,
      checksums, attribution, and generated release notes.
    done: false
    created_at: "2026-08-20T14:36:42Z"
    updated_at: "2026-08-20T14:36:42Z"
    source: plan
    mandatory: true
    status: open
    active_at: null
    blocked_reason: null
    done_at: null
    skipped_at: null
    completed_by: null
    completed_in_harness: null
    skipped_by: null
    evidence: []
    artifact_refs: []
    change_refs: []
    command_refs: []
    source_plan_id: null
    source_question_ids: []
    validation_hint:
      Run packaging tests covering three variants, multiple languages,
      duplicate slots, mismatches, checksums, and generated notes.
  - id: plan-todo-0004
    text:
      Add source acquisition and SHA-256 verification utilities and enforce pinned
      source provenance for publish mode.
    done: false
    created_at: "2026-08-20T14:36:42Z"
    updated_at: "2026-08-20T14:36:42Z"
    source: plan
    mandatory: true
    status: open
    active_at: null
    blocked_reason: null
    done_at: null
    skipped_at: null
    completed_by: null
    completed_in_harness: null
    skipped_by: null
    evidence: []
    artifact_refs: []
    change_refs: []
    command_refs: []
    source_plan_id: null
    source_question_ids: []
    validation_hint:
      Run source verification tests for matching, missing, and mismatched
      hashes.
  - id: plan-todo-0005
    text:
      Add Lexhint-owned project_artifact API and dictionary project CLI, with fresh
      target schema creation, subset validation, copied provenance, atomic output, integrity
      checks, and tests.
    done: false
    created_at: "2026-08-20T14:36:42Z"
    updated_at: "2026-08-20T14:36:42Z"
    source: plan
    mandatory: true
    status: open
    active_at: null
    blocked_reason: null
    done_at: null
    skipped_at: null
    completed_by: null
    completed_in_harness: null
    skipped_by: null
    evidence: []
    artifact_refs: []
    change_refs: []
    command_refs: []
    source_plan_id: null
    source_question_ids: []
    validation_hint:
      Run the Lexhint test suite and projection tests against the rich
      fixture.
  - id: plan-todo-0006
    text:
      Rewrite .github/workflows/build-release.yml for configuration-driven multi-language
      and multi-variant builds, rich-first projections, release assembly, source verification,
      staging artifacts, and guarded publishing.
    done: false
    created_at: "2026-08-20T14:36:42Z"
    updated_at: "2026-08-20T14:36:42Z"
    source: plan
    mandatory: true
    status: open
    active_at: null
    blocked_reason: null
    done_at: null
    skipped_at: null
    completed_by: null
    completed_in_harness: null
    skipped_by: null
    evidence: []
    artifact_refs: []
    change_refs: []
    command_refs: []
    source_plan_id: null
    source_question_ids: []
    validation_hint:
      Parse the workflow and inspect that all build, validation, assembly,
      checksum, and publish gates are present.
  - id: plan-todo-0007
    text:
      Add dataset tests and Lexhint regression tests using tiny local fixtures,
      with no production-source download in CI.
    done: false
    created_at: "2026-08-20T14:36:42Z"
    updated_at: "2026-08-20T14:36:42Z"
    source: plan
    mandatory: true
    status: open
    active_at: null
    blocked_reason: null
    done_at: null
    skipped_at: null
    completed_by: null
    completed_in_harness: null
    skipped_by: null
    evidence: []
    artifact_refs: []
    change_refs: []
    command_refs: []
    source_plan_id: null
    source_question_ids: []
    validation_hint: Run python -m pytest -q tests and python -m pytest -q ../lexhint/tests.
  - id: plan-todo-0008
    text:
      Update README.md and DATA_SOURCES.md with the new release contract, supported
      language and variant matrix, provenance policy, local workflows, and licensing
      guidance.
    done: false
    created_at: "2026-08-20T14:36:42Z"
    updated_at: "2026-08-20T14:36:42Z"
    source: plan
    mandatory: true
    status: open
    active_at: null
    blocked_reason: null
    done_at: null
    skipped_at: null
    completed_by: null
    completed_in_harness: null
    skipped_by: null
    evidence: []
    artifact_refs: []
    change_refs: []
    command_refs: []
    source_plan_id: null
    source_question_ids: []
    validation_hint:
      Inspect documentation examples against the implemented CLI and
      manifest fields.
  - id: plan-todo-0009
    text:
      Reconcile generated-file ignores and verify no generated SQLite database is
      added to Git.
    done: false
    created_at: "2026-08-20T14:36:42Z"
    updated_at: "2026-08-20T14:36:42Z"
    source: plan
    mandatory: true
    status: open
    active_at: null
    blocked_reason: null
    done_at: null
    skipped_at: null
    completed_by: null
    completed_in_harness: null
    skipped_by: null
    evidence: []
    artifact_refs: []
    change_refs: []
    command_refs: []
    source_plan_id: null
    source_question_ids: []
    validation_hint:
      Run git status --short and confirm generated database paths are
      ignored or absent.
  - id: plan-todo-0010
    text:
      Run focused and full validation, resolve regressions, and record evidence
      for every acceptance criterion before finishing implementation.
    done: false
    created_at: "2026-08-20T14:36:42Z"
    updated_at: "2026-08-20T14:36:42Z"
    source: plan
    mandatory: true
    status: open
    active_at: null
    blocked_reason: null
    done_at: null
    skipped_at: null
    completed_by: null
    completed_in_harness: null
    skipped_by: null
    evidence: []
    artifact_refs: []
    change_refs: []
    command_refs: []
    source_plan_id: null
    source_question_ids: []
    validation_hint:
      Run the listed pytest and compileall commands plus workflow/configuration
      checks.
generation_reason: initial
based_on_question_ids: []
based_on_answer_hash: null
supersedes_plan_id: null
approved_at: "2026-08-20T18:48:28Z"
approved_by:
  actor_type: user
  actor_name: nahrstaedt
  tool: manual
  session_id: null
  host: null
  pid: null
  actor_id: null
  role: null
  harness_id: null
  command_pid: null
  pid_scope: null
approval_note: "User approved in harness: approve."
approval_source: explicit_chat
approved_plan_hash: 84d5fa71234755d7e061b2129e9922852b6f022fcdbcd704506cf46fab618c0a
goal:
  Implement the schema-7, multi-language, capability-specific Lexhint dataset
  release pipeline described in 01_todo.md.
files:
  - "@datasets.toml"
  - "@scripts/validate.py"
  - "@scripts/package_release.py"
  - "@scripts/package_dataset.py"
  - "@scripts/download_source.py"
  - "@.github/workflows/build-release.yml"
  - "@README.md"
  - "@DATA_SOURCES.md"
  - "@tests/"
  - "@../lexhint/lexhint/"
  - "@../lexhint/tests/"
test_commands:
  - python -m pytest -q tests
  - python -m pytest -q ../lexhint/tests
  - python -m compileall -q scripts tests
expected_outputs:
  - Dataset tests pass without downloading production dictionary data.
  - Lexhint regression and projection tests pass.
  - Python compilation completes successfully.
todos_waived_reason: null
---

# Lexhint datasets multi-language release pipeline

## Summary

Implement the complete mandatory release pipeline in `01_todo.md`. The repository will move from the English-only schema-4 MVP to a schema-7-compatible, data-driven catalog of lexical, runtime, and rich artifacts for all currently supported languages. Lexhint remains the owner of artifact semantics and schema, while this repository owns build orchestration, validation policy, packaging, provenance, manifests, attribution, and publication safeguards.

The implementation includes the recommended Lexhint-owned rich-to-subset projection so each language scans the source once for the expensive rich build. The optional future one-pass source router for all languages is not included because `01_todo.md` explicitly defers it until release operation demonstrates that source scanning remains the bottleneck.

## Implementation Changes

- Add `datasets.toml` and shared configuration logic for cs, de, en, es, fr, it, and pt, with the three stable public variants: lexical, runtime, and rich.
- Replace direct schema-specific SQL validation with `Lexicon.from_path`, `read_artifact_status`, `PRAGMA quick_check`, configurable probes, thresholds, and capability-operation checks.
- Split artifact packaging from release assembly. Package each artifact with stable naming, deterministic gzip, Lexhint metadata, capability-aware counts, frequency provenance, and checksums, then aggregate all records into one v2 manifest.
- Add duplicate-slot, language, capability, coverage, schema, Lexhint commit, source, and checksum invariants. Require verified source hashes for publication mode and preserve dictionary and frequency provenance.
- Add `scripts/download_source.py`, retaining a compatibility wrapper for `scripts/package_dataset.py` if useful to existing callers while making `package_release.py` the documented entry point.
- Rewrite the workflow around a prepared build matrix, one verified source, rich-first per-language builds, Lexhint projections, validation, one release assembly job, staging artifacts, and guarded immutable GitHub Release publication.
- Add Lexhint `project_artifact` functionality and `lexhint dictionary project` CLI support using fresh schema creation and atomic output replacement, with tests proving capability subset and behavior equivalence.
- Add fixture-based tests for all variants and release invariants. Update README and DATA_SOURCES with the v2 contract, naming, local commands, staging policy, provenance, and licensing boundary.

## Tests

- `python -m pytest -q tests` using tiny local fixtures and no network access.
- `python -m pytest -q ../lexhint/tests` including projection and CLI regression coverage.
- `python -m compileall -q scripts tests`.
- Parse or otherwise structurally inspect the GitHub Actions workflow and verify all required inputs and guarded publish steps.
- Run a local release-candidate packaging flow, inspect `datasets-v2.json`, and verify `sha256sum -c dist/SHA256SUMS`.
- Check `git status --short` and ignore rules to confirm generated SQLite files are not committed.

## Assumptions

- The sibling checkout at `../lexhint` is the Lexhint implementation used for companion API and CLI changes, and the workflow continues to install the requested Lexhint ref.
- Current Lexhint schema 7, supported languages, capability order, profiles, and public status APIs are the compatibility contract.
- Official standard variants use the default pinned FrequencyWords enrichment; frequency is recorded as provenance rather than a release-axis variant.
- Language-specific semantic and dictionary probes remain configurable and are only enabled as release gates when fixture or staging data confirms them.
- The user intends the mandatory definition of done and recommended projection phase, while accepting the explicitly deferred optional multi-language single-pass optimization.

## Out of Scope

- A future single-pass Lexhint builder that routes one raw source stream into all seven language databases, which `01_todo.md` marks as optional and subsequent to stable releases.
- Implementing the future Lexhint installer or changing Lexhint runtime consumer selection behavior.
- Publishing real production datasets or committing generated SQLite artifacts.
- Inferring legal terms or replacing upstream attribution requirements.

## Plan input checklist before upsert

- [x] I ran `taskledger plan check --file plan.md`.
- [x] Every acceptance criterion uses `text`, not `description`.
- [x] Todo mappings use supported keys only: `id`, `id_hint`, `text`, `mandatory`, `validation_hint`, `worker_step`.
- [x] File references are plan-level `files:` entries or are mentioned in todo text/body; todo-level `files:` is not captured.
- [x] The Markdown body explains enough context for implementation handoff.
