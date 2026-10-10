# Literature Review Workbench

[中文](README.md) | English

A locally installable Codex skill for creating, updating, and auditing source-grounded literature reviews. It maintains paper, source-version, evidence, claim, section, paragraph, and review records, with read-only library import and optional domain verification profiles.

This is an independent workflow inspired by DAS, not the official DAS generator or a benchmark-equivalent reproduction. Pinned provenance and method correspondence are included in `references/`. Helpers check structure, fingerprints, and dependencies; actual reading, citation support, and scholarly judgments require Codex or a researcher.

## Install

Requires Python 3.10+ and a Codex environment with local skills, file access, and command execution. Helpers use only the standard library and require no API keys or third-party packages. Model access, external discovery, PDF parsing, and document export use capabilities available in your environment; no particular MCP service is required.

On Windows PowerShell, macOS, or Linux:

```sh
git clone https://github.com/Nefe1ibate/literature-review-workbench.git
cd literature-review-workbench
python -B install.py
```

Use `python3` if that is your interpreter name, or `py -3` on Windows. Without Git, use **Code → Download ZIP**, extract the complete repository, and run the installer there.

The default destination is `~/.agents/skills/literature-review-workbench`, following [official Codex documentation](https://learn.chatgpt.com/docs/build-skills). Installation copies bundled files without network access, config changes, or overwriting an existing installation.

For legacy or custom discovery directories:

```sh
python -B install.py --skills-dir ~/.codex/skills
```

For project-only installation, run from your project:

```sh
python -B /path/to/literature-review-workbench/install.py --skills-dir .agents/skills
```

Manual installation: copy the entire `skills/literature-review-workbench` directory, including `agents`, `assets`, `references`, and `scripts`. Avoid duplicate installations across discovery paths. Restart Codex if it does not detect the skill.

## Use

Attach your papers, draft review, or library, then ask:

```text
Use $literature-review-workbench to develop a literature review around my research question.
Establish the scope and discovery plan, maintain evidence records, and plan sections and paragraphs before writing.
Distinguish source results, interpretation, synthesis, and proposed gaps.
Keep reading status, source locations, and unknowns visible. Save a checkpoint for resuming later.
```

Specify a closed corpus when external discovery is unwanted. For open reviews, use available literature search tools. Set the research question, cutoff, and deliverables explicitly; the skill imposes no universal paper count, year range, taxonomy, or page limit. Independent review is optional and requires actual independent contexts; record limitations if unavailable.

## Check tools and initialize a review

From the repository root:

```sh
python -B tests/test_distribution.py
python -B skills/literature-review-workbench/scripts/workbench.py --help
python -B skills/literature-review-workbench/scripts/import_library.py --help
python -B skills/literature-review-workbench/scripts/workbench.py init --root ../my-literature-review --topic "My research topic"
python -B skills/literature-review-workbench/scripts/workbench.py validate --root ../my-literature-review --report ../my-literature-review/checks/validation.json
python -B skills/literature-review-workbench/scripts/workbench.py checkpoint --root ../my-literature-review --label initial
```

Review directories contain `state.json`, `events.jsonl`, `snapshots/`, `drafts/`, and `checks/`. Passing tests or initializing an empty review does not establish scientific verification. An empty review may return `needs_review`; inspect the findings.

Read [state-contract.md](skills/literature-review-workbench/references/state-contract.md) for commands, schemas, dependency order, and revision guards, and [workflow.md](skills/literature-review-workbench/references/workflow.md) for sustained projects.

## Connect a library or domain profile

Copy and customize [library-config.example.json](skills/literature-review-workbench/assets/library-config.example.json). Relative paths resolve against the config directory. The example `../topic-library` is a placeholder; no literature library is bundled.

```sh
python -B skills/literature-review-workbench/scripts/import_library.py --config /path/to/library-config.json --output /path/to/review-output/library-bundle.json
```

Output must be outside the connected library. Import is read-only; historical support needs revalidation. Import collections in order: papers, sources, evidence, searches, claims, sections, paragraphs, reviews, check_results. See [library-adapters.md](skills/literature-review-workbench/references/library-adapters.md).

If appropriate, copy and customize [domain-profile.example.json](skills/literature-review-workbench/assets/domain-profile.example.json), then apply it:

```sh
python -B skills/literature-review-workbench/scripts/workbench.py configure --root ../my-literature-review --domain-profile /path/to/domain-profile.json --reason "Apply relevant domain checks"
```

Profiles execute no code and do not replace actual review. See [domain-profiles.md](skills/literature-review-workbench/references/domain-profiles.md).

## Update, uninstall, and license

Run `git pull --ff-only` in the downloaded repository. Back up the installed skill outside all discovery locations and reinstall. Existing destinations are rejected to protect edits. Uninstall by removing only the installed skill folder; retain your library and review workspaces separately.

Local code and documentation use the [MIT License](LICENSE). Linked papers, websites, and upstream projects retain their own licenses and are not bundled. Keep personal configurations, papers, review records, and credentials outside this public repository.
