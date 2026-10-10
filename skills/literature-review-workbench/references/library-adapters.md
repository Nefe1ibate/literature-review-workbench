# Connecting a maintained literature library

Use a read-only connection rather than copying a whole topic collection into this skill. The adapter reads local ledgers and source files, then exports a normalized bundle into a separate review workspace. It uses Python's standard library; no network, model API, database, or configuration-supplied program is run.

```text
python scripts/import_library.py --config library-config.json --output review-workspace/library-bundle.json
```

The output must be outside the connected `library_root`, including through an existing symbolic link. Relative config paths (`library_root`, ledger `path`, `papers_path`, `sources_path`) resolve against the config directory. Relative file paths contained in ledger records resolve against `library_root`. The input ledgers and files are never rewritten. An explicitly named output may be replaced atomically.

## Mapped ledgers

Set `schema_version` to `literature-library-config/1`, `adapter` to `mapped-ledger`, and supply `library_root` plus `collections`. See `assets/library-config.example.json` for a starting configuration. Each collection has:

- `path`: ledger filename;
- `format`: `json`, `jsonl`, or `csv` (otherwise inferred from extension);
- optional `records_key`: dotted path to a JSON array inside a wrapper;
- optional `mapping`: target field to source dotted path, alternative path list, or `{"constant": value}`. A target such as `locator.pdf_page` creates a nested object. Without mapping, records already use the portable state contract.

Available collection names are `papers`, `sources`, `evidence`, `searches`, `claims`, `sections`, `paragraphs`, `reviews`, and `check_results`. Only `papers` is required. Stable identifiers and foreign keys should be explicit for records that other records reference. Paper IDs can be generated from DOI or normalized bibliographic identity when absent. Authors may be arrays or strings separated by semicolons or `and`; commas are preserved inside personal names. Map precise authors as arrays when ambiguity matters.

The importer normalizes DOI URLs and merges records sharing a DOI, preserving aliases and metadata conflicts in import history. It keeps separate source versions. Title/year disagreement under one DOI is a warning requiring a bibliographic decision, not a silently resolved version claim. Different records that reuse one paper ID without a shared DOI, or conflicting source IDs, are rejected. Absence of DOI does not justify merging differently titled records.

Source files receive a current SHA-256 digest when locally available. A historic digest mismatch and a missing source file are reported; the historic digest remains in provenance. Local existence never means the file was read. A `full` reading status requires an explicit `reading_scope`; otherwise it is demoted to `partial`. Human completion text that cannot be mapped safely is preserved in `extensions.library_import`.

All imported evidence is `pending`, all imported claims are `needs_review`, and prior paragraph/section acceptances or specialized checks are not current. This deliberately preserves reusable work while requiring its source and relevance to be checked for the new review. Original snippets, conditions, locators, and historic verification decisions remain available. Do not treat this normalization as semantic source verification.

## Reading-report library format

For a library organized as a reading-status ledger, source manifest and per-paper evidence files, use:

```json
{
  "schema_version": "literature-library-config/1",
  "adapter": "reading-report-library",
  "library_root": "../maintained-library",
  "reading_report": {
    "papers_path": "../maintained-library/evidence/reading_status.json",
    "sources_path": "../maintained-library/evidence/source_manifest.json"
  }
}
```

The reading ledger uses `id`, bibliographic fields, and optional `evidence_file` / report paths. The manifest uses `paper_id`, `path`, optional `sha256`, `pages`, and acquisition metadata. Per-paper details may have `bibliography`, `version` / `provenance` / `sources`, explicit `full_read` / `reading` / `fulltext` / read-range records, and `exact_page_claims`, `claims`, `key_claims`, or `evidence`. These are format aliases, not disciplinary rules.

Explicit historic completion plus recorded scope is retained as a historic reading status; unstructured claims of completion remain partial or metadata-only. The adapter retains the first physical PDF page in the portable locator and the complete historic multi-page record in extensions. It does not convert print pages into physical PDF pages. Source versions are linked only by explicit path, digest, or unambiguous source alias. Ambiguous source associations receive an unavailable placeholder source and a warning, so later review can repair them without guessing a pagination mapping. A missing evidence file does not stop import of accessible records.

## Loading and updating a review

The bundle is not a whole workspace: it contains collection arrays and `import_metadata`, without a project or revision. Inspect its warnings. Use `workbench.py init` for a new project, then pass each collection array to `put` in the dependency order in `references/state-contract.md`. Extract arrays with a small local JSON operation; do not pass the entire bundle as one record. The preferred primary-source ID is retained as `extensions.library_import.historic_primary_source_id` during import, because sources do not yet exist when the engine first loads papers. After source import and version review, it can be restored with a paper upsert. Excluded/pending records are kept for audit and future scope changes.

On library updates, export a fresh bundle and compare `input_fingerprints`, source digests and record identities. Upsert only the changed records with a reason and expected workspace revision. Re-importing untouched evidence would correctly reset its historical verification; avoid doing this unnecessarily. The importer does not synchronize writes back to the source library. A future adapter should emit this same contract and provenance, maintain its own tests, and leave specialist checks to an external domain profile.

Run workspace validation after import. A missing locator or source can prevent use in accepted prose; fixing the warning requires actual source work. A successful importer exit says only that a bundle was written.
