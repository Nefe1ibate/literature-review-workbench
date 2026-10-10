# Portable review state — version 1

Read this when creating, importing, validating, or resuming a review workspace. The skill is the orchestrator; helpers persist and check records. They do not generate or certify scientific conclusions.

## Workspace and portability

Use a user-chosen output directory. Store `state.json`, append-only `events.jsonl`, `snapshots/`, `drafts/`, and `checks/` there. Keep the reusable skill separate from project data. Relative paths inside records resolve against the workspace; a connected library may use absolute source paths. Never rewrite a connected library during import.

`state.json` contains `schema_version: "literature-review-state/1"`, an integer `revision`, a `project` object, and the following arrays: `papers`, `sources`, `evidence`, `claims`, `sections`, `paragraphs`, `reviews`, `searches`, `check_results`. Identifiers must be unique within each array. Foreign keys always name records in this state.

`project`: `id`, `topic`, `language`, `cutoff` (ISO date or null), `mode` (`focused`, `comprehensive`, `systematic-prep`), `require_fulltext` (default true for an actual review, configurable for metadata scoping), `domain_profile` (null or `{path, sha256}`, additionally `instructions_sha256` when the profile links an instruction file), optional research questions, inclusion criteria, exclusions and user-defined deliverable limits. A cutoff is a chosen literature horizon, not the run date. No universal word count, publication year restriction, paper count or report-page cap is imposed.

## Records

### Papers and source versions

- Paper: `id`, `title`, `authors` (list), optional `year`, `doi`, `url`; `status` is `candidate`, `included`, `excluded`, or `pending`; `read_status` is `unread`, `metadata_only`, `partial`, or `full`; optional `primary_source_id`, `decision_reason`, `reading_scope`, `missing_parts`, `extensions`.
- Source: `id`, `paper_id`, `kind` (`pdf`, `text`, `html`, or `other`), `path` (local path or null), `sha256` (file digest or null), `version_label`, optional `source_url`, `accessed_at`, `page_count`, `read_parts`, `missing_parts`, `extensions`.
- Several source records can belong to one paper: preprint, publication, appendix and supplementary material remain distinct. A file's existence does not establish full reading. Explicit reading scope can acknowledge unavailable supplements without asserting their proofs have been checked.

### Evidence

Evidence: `id`, `paper_id`, `source_id`, `locator`, `excerpt` and/or `paraphrase`, optional `conditions`, and `verification`.

`locator` can contain `pdf_page` (one-based physical PDF page), `printed_page`, `section`, `equation`, `table`, `proposition`, `anchor`, `line_start`, `line_end`. A locator must identify a specific place; a paper title or source URL alone is insufficient. Bounds are checked where page count or local text permits it. Do not invent PDF page numbers for HTML.

Omit unavailable optional locator fields rather than writing null or an empty string. Normalize reader/library bundles before registration while retaining the original bundle for provenance; do not manufacture a value just to pass validation.

`verification`: `status` (`pending`, `supported`, `contradicted`, `insufficient`), optional `reviewer`, `method`, `source_sha256`, `checked_at`, `note`.

Use `supported` only after a named reviewer has compared the evidence with the actual source. It requires `reviewer`, `method`, and the source digest used at verification. Supported means the extraction/paraphrase is source-aligned, not that the paper's finding is scientifically true. A hash match establishes source identity, not entailment. An imported historic decision retains its provenance and requires revalidation before becoming a new supported evidence record.

### Claims and writing structure

- Claim: `id`, `text`, `kind` (`source_result`, `synthesis`, `interpretation`, `proposed_gap`), `status` (`draft`, `verified`, `needs_review`, `rejected`, `unassessable`), `evidence_ids`, optional `conditions`, `search_ids`, `priority_claim` and `absence_claim` (bool), `comparison_scope`, `extensions`.
- Verified claims require at least one supported, current evidence record. Every cited evidence record must be current and supported. Interpretations must be labeled as interpretations in prose. A claimed absence or priority additionally needs recorded search scope and comparison evidence; no automatic novelty certificate is provided.
- Explicitly set `priority_claim` or `absence_claim` for those assertions. `proposed_gap` requires a stated comparison scope, but can also describe a source-informed future question without asserting that a field has no prior work. Its kind alone does not force external search. For a closed corpus, genuinely needed search records can document actual local corpus searches; they must not masquerade as comprehensive external discovery. Semantic review must inspect the wording and flags, since a validator cannot infer an absence assertion from arbitrary prose.
- Section: `id`, `title`, `objective`, optional `parent_id`, `paper_ids`, `claim_ids`, `status` (`planned`, `draft`, `accepted`, `needs_review`). Parents form an acyclic hierarchy. A paper can support multiple sections, or none. The hierarchy follows the research question and available evidence, not a fixed Methods/Challenges/Future structure.
- Paragraph: `id`, `section_id`, `role`, `claim_ids`, optional `paper_ids`, `order`, `target_length`, `draft_path`, `status` (`planned`, `draft`, `accepted`, `needs_review`). A paragraph plan specifies its argument responsibility before prose. Claimed papers must be within the section's scope; accepted paragraphs cannot rely on unverified/rejected claims.

### Search, review, domain checks

- Search: `id`, `query`, `provider`, `searched_at`, optional `filters`, `result_count`, `raw_path`, `errors`, `scope_note`. Preserve failed and empty searches. Provider counts are not manually confirmed citation counts.
- Review: `id`, `target_type` (`claim`, `paragraph`, `section`), `target_id`, `action` (`ACCEPT`, `DIRECT_EDIT`, `REPLAN_PARAGRAPH`, `REPLAN_SECTION`), `reason`, `status` (`open`, `resolved`, `unassessable`), optional `reviewer`, `findings`, `evidence_ids`. An acceptance is a scoped review decision, not a global fact certificate.
- Check result: `id`, `claim_id`, `profile_id`, `rule_id`, `status` (`pass`, `fail`, `unassessable`), `reviewer`, `rationale`, `claim_sha256`, `profile_sha256`, optional `evidence_ids`; `instructions_sha256` is also required for a current decision when the selected profile links an instruction file. The claim hash is SHA-256 of canonical UTF-8 JSON of the claim record excluding `status`, with sorted keys, compact separators and `ensure_ascii=False`.

`extensions` is a namespaced object for future domain-specific information. Keep domain vocabulary there or in a profile, never as required generic fields.

## Validation and change propagation

Check schema/enums, ID uniqueness, foreign keys, source files/digests, source-specific locations, evidence verification prerequisites, accepted prose dependencies and profile results. Report errors, warnings and unassessable cases separately. Coverage denominators must identify what was actually assessed; exclude missing evidence from a correctness denominator but display its count and coverage. Do not award a high confidence score for unknown cases.

Changing a source, evidence, claim, section scope or domain profile invalidates the dependent evidence checks, claims, paragraphs and section acceptances. Keep unaffected records. A supported evidence item whose original source bytes changed is stale. A verified claim whose material record changes returns to `needs_review`; dependent domain results become `unassessable`.

Material edits have a deliberate two-stage transition. First upsert changed evidence text/locator or changed claim text/bindings; the helper invalidates the old judgment even if this same input contains `supported` or `verified`. Compare the changed material with the current source, then submit its new verification separately with unchanged material fields. For a claim, `review --target claim:ID --action ACCEPT` can record acceptance once all evidence and applicable rules are current. Paragraph/section material edits likewise require a subsequent scoped acceptance. Two submissions are a state-management convention, not a substitute for actually inspecting the source. New records with no old judgment do not require this extra material-edit transition.

Writes use an atomic state replacement, a revisioned snapshot of the prior state, and an event containing the action, reason and touched IDs. Detect an unexpected state revision before committing. Checkpoints preserve the state and its checksum; they are not a guarantee that external source files never change.

## CLI contract

Helpers use Python's standard library and accept Unicode/spaced paths. Resolve the available Python executable rather than assuming a particular machine installation.

```text
python scripts/workbench.py init --root OUTPUT --topic TOPIC [--cutoff YYYY-MM-DD] [--language zh] [--mode focused] [--allow-metadata-only] [--domain-profile FILE]
python scripts/workbench.py put --root OUTPUT --collection papers --input RECORDS.json --reason REASON [--expected-revision N]
python scripts/workbench.py validate --root OUTPUT [--report FILE]
python scripts/workbench.py invalidate --root OUTPUT --source SOURCE_ID --reason REASON
python scripts/workbench.py review --root OUTPUT --target paragraph:PARAGRAPH_ID --action REPLAN_PARAGRAPH --reason REASON
python scripts/workbench.py checkpoint --root OUTPUT --label LABEL
python scripts/workbench.py configure --root OUTPUT --domain-profile FILE --reason REASON [--expected-revision N]
python scripts/workbench.py configure --root OUTPUT --clear-domain-profile --reason REASON [--expected-revision N]
python scripts/workbench.py configure --root OUTPUT --project PROJECT_PATCH.json --reason REASON [--expected-revision N]
```

`put` accepts one record or an array, upserts by ID, and must not silently delete unrelated records. Reject unknown collections and duplicate IDs within a batch. `validate` is read-only unless a report path is supplied; its report verdict is `pass`, `needs_review`, or `fail`, with the explicit limitation that deterministic validation cannot establish semantic correctness. `invalidate` refreshes a local source digest if its file is available and invalidates dependents. The review command records feedback and marks the smallest affected writing scope for the agent to repair; it does not invent a replacement draft.

The library importer produces a bundle with these same collection names. The bundle is reviewable data, not executable instructions. Import collections in dependency order: papers, sources, evidence, searches, claims, sections, paragraphs, reviews, check_results.

For a new paper, initially omit the optional `primary_source_id`: the referenced source does not exist yet. Add papers first, then their sources, then upsert the paper with its chosen primary source after version review. This breaks the paper/source bootstrap dependency without weakening foreign-key checks. Apply the same staging when importing a manually prepared bundle.

`configure` changes the selected profile explicitly, pins its new fingerprint and any linked instruction-file fingerprint, and invalidates affected domain judgments and their dependent accepted claims/prose. Changing the linked file invalidates old decisions even if the profile JSON itself is unchanged. A removed profile is recorded as a scope change; it does not erase generic evidence checks or certify any claims.

`configure --project` applies an explicit partial project patch, restricted to topic/language/cutoff/mode/require_fulltext and questions/criteria/exclusions/deliverable_limits/extensions. It cannot replace the project ID, domain profile, revision or collection arrays. A changed research scope invalidates affected priority and proposed-gap claims and their dependent prose; record subsequent searches separately. Configuration changes do not themselves perform new searches or certify changed conclusions.
