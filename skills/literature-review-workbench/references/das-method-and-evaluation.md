# DAS concepts and evaluation boundaries

Read this reference when planning a review, defining an audit, repairing a draft, or explaining what the workbench inherits from DAS. 中文使用提示：通用流程可以接入任何学科；专题规则和文献库通过工作台的扩展接口接入，不把某一学科的判断写入核心流程。

## Provenance and implementation status

This is an independent Codex workflow informed by the DAS paper and its released evaluation materials. It is not an official DAS implementation or an experimentally validated reproduction. As inspected on 2026-10-08, repository commit `24fa88b3eee004f0926b978717ba4a716f79661a` contains evaluation implementations; `DAS/` contains only a release-status README. No upstream code was installed or executed, and no literature lake was downloaded.

The reference records ideas and an adapted audit, not the authors' complete prompts or software. Exact source URLs, access times, and SHA-256 hashes of fetched bytes are in [das-provenance.json](das-provenance.json). Treat the upstream release statement as dated; recheck before claiming that later generation code exists. [Pinned core release statement](https://github.com/ZhikaiXu24/DAS/blob/24fa88b3eee004f0926b978717ba4a716f79661a/DAS/README.md).

## Method carried into the workbench

DAS separates reusable paper understanding from the topic-specific manuscript and keeps literature, organization, writing, and assembly states. Organization follows the discovered candidates; papers can serve multiple sections or be rejected. Paragraph responsibilities precede claims and citations, and claims precede prose. Defects trigger a bounded repair of the affected state and its dependents. These are the useful transferable mechanisms. [Upstream method overview](https://github.com/ZhikaiXu24/DAS/blob/24fa88b3eee004f0926b978717ba4a716f79661a/README.md#-das-method).

Keep four independently inspectable assets in this skill:

- **Literature:** source versions, acquisition provenance, searches, screening decisions, and reusable reading records.
- **Organization:** research questions, classification principles, section objectives, and paper-to-section assignments.
- **Writing:** paragraph responsibilities, claims, evidence bindings, drafts, and review decisions.
- **Assembly:** bibliography, figures or tables when useful, cross-references, exported artifacts, and their checks.

The size of the library and number of software agents are implementation choices. A small local corpus and one Codex agent can maintain these states. Do not import the benchmark's candidate count, page target, citation target, model, or timing budget into an ordinary user request.

## Evidence access by stage

Use the following as the workbench's explicit evidence contract. Its extra source audit is a deliberate extension, not a claim about the unpublished DAS generator.

| Stage | Evidence available | Permitted conclusion and required record |
|---|---|---|
| Discovery | Bibliographic records, search results, titles and abstracts | Candidate relevance and retrieval provenance; no detailed technical conclusion |
| Reading | Actual accessible source and supplements, with version identity | Paper-level findings and limitations with page, section, equation, table, or other stable locator; record inaccessible parts |
| Organization | Screened candidates and reusable reading records | Classification and routing with reasons; do not infer a missing research branch is nonexistent |
| Claim planning | Assigned reading records and focused source passages | Atomic claims, citation roles, assumptions, and evidence gaps; separate author findings from the reviewer's interpretation |
| Drafting | Approved claim plan, linked passages and surrounding draft | Realize the plan in prose; any new substantive claim returns to evidence planning |
| Rules check | Identifiers, record fields, links, citation syntax and artifact structure | Structural errors and consistency only; passing does not establish truth |
| Discourse review | Manuscript, section objectives and claim plan | Organization, progression and citation placement; scientific support requires the next row |
| Source audit | The exact source portions needed for each claim, plus specialist rules when loaded | Assess support, contradiction, missing conditions and misattribution; log inspected evidence and residual uncertainty |
| Assembly review | Exported document, bibliography and all inspected pages or assets | Artifact completeness and visible readability; record sampling and unavailable formats |

The paper's Appendix C.4 explicitly limits its manuscript Reviewer: it does not read source papers and therefore does not establish source-level entailment. Appendix B.2 also describes disabled formula recognition and removal of some trailing appendix/reference material before metadata extraction. A cached summary is consequently not sufficient for auditing an exact numerical result, theorem, formula, or a condition found only in an appendix. [Paper, Appendices B.2 and C.4](https://arxiv.org/html/2608.18034v1).

## Keep three kinds of checks separate

1. **Deterministic checks** inspect observable invariants: record links, citation identifiers, required fields, file existence, hashes and export consistency. An evidence locator existing proves that it is traceable, not that the passage supports the claim.
2. **Source-aware semantic checks** compare a bounded claim with accessible original evidence and its qualifications. A specialist adapter can require additional checks, such as design assumptions, proof conditions or outcome definitions.
3. **Quality judgments** score citation use, synthesis, discourse and presentation. They are evaluator opinions under a declared input and rubric. They neither measure a hallucination probability nor certify academic correctness.

Never collapse these into a single “verified” flag. Preserve the observed check result, its scope, and the audit evidence. Reuse an earlier result only if the source version, claim, applicable rules and relevant dependencies remain compatible.

## Missing evidence and bounded repair

Absence of reviewer evidence is an **unassessable** result, distinct from a demonstrated unsupported or contradicted claim. Missing metadata, an inaccessible PDF, unreadable extraction, or an uninspected appendix cannot by itself prove fabrication. Conversely, discoverability of a citation cannot upgrade a claim to supported.

For each semantic audit, separately report claims inspected, supported, partially supported, contradicted or otherwise demonstrably defective, and unassessable. Preserve the reason and missing source for each unassessable item. Review urgency may remain high even when a numerical error rate cannot be computed. Do not place unassessable items in either the supported or defective denominator.

Choose the smallest repair that addresses the defect:

| Defect | Repair | Recheck |
|---|---|---|
| Wording or local transition | Revise the paragraph using existing approved claims | Changed claim wording, local citations and adjacent transition |
| Missing condition, wrong evidence or changed assertion | Replan the claim and its paragraph; obtain evidence if needed | Changed claim, bindings, paragraph and dependent comparisons |
| Redundant paragraph responsibilities or broken progression | Replan the subsection | Its claims, prose, transitions and affected synthesis |
| Changed corpus, source version or organizing principle | Update affected literature/organization records | All claims, tables and conclusions that depend on those changes |

Keep a snapshot and unresolved findings when a configured retry budget is exhausted. A complete draft may be retained for the user, but unresolved material findings remain visible. A retry limit is not a passing result.

## Adapted four-family, sixteen-item audit

Use the following checklist as `adapted-workbench-v1`. Short labels map to the corresponding upstream criteria; the questions below are this skill's operational adaptation. [Upstream metric protocol](https://github.com/ZhikaiXu24/DAS/blob/24fa88b3eee004f0926b978717ba4a716f79661a/DAS-Bench/benchmark/evaluation_protocol.md).

| Family | Item | Audit question |
|---|---|---|
| BSC: scholarly citations | BSC1 Support | Does the inspected original evidence support the precise claim and stated scope? |
| BSC | BSC2 Attribution | Are findings, methods, data and limitations assigned to the right source and version? |
| BSC | BSC3 Joint synthesis | Does a citation group contribute to an explicit comparison or common claim, with each source's role clear? |
| BSC | BSC4 Distribution | Are relevant sections adequately cited without unexplained concentration, repeated bundles or mechanical stacks? |
| TSQ: research organization | TSQ1 Coverage | Are the review's declared questions and main directions substantively covered within its documented corpus? |
| TSQ | TSQ2 Boundaries | Is the organizing principle defensible, with distinctions and legitimate overlaps explained? |
| TSQ | TSQ3 Sequence | Do sections have separate functions and form a coherent path through the research problem? |
| TSQ | TSQ4 Insights | Do comparisons, limitations, gaps and prospects follow from the reviewed evidence? |
| HDQ: discourse | HDQ1 Alignment | Does each paragraph and subsection serve its parent objective? |
| HDQ | HDQ2 Progression | Does discussion develop mechanisms, evidence, comparison and implications in a sensible order? |
| HDQ | HDQ3 Specificity | Are assertions concrete about relevant methods, assumptions, context, results and limits? |
| HDQ | HDQ4 Integration | Does local prose synthesize related work rather than merely enumerate papers? |
| MAR: assembled artifact | MAR1 References | Are citations and bibliography readable, mutually consistent and traceable? |
| MAR | MAR2 Visuals | Where useful and requested, do tables and figures express meaningful comparisons and connect to the text? |
| MAR | MAR3 Presentation | Is the inspected final format readable, with stable headings, mathematics and layout? |
| MAR | MAR4 Completion | Does the requested artifact contain its expected, finished components? |

For each applicable item, record positive evidence, the strongest verified limitation, inspected locations, evidence availability and a rationale before scoring. Use 1 for absent/unusable performance, 2 for demonstrated serious defects, 3 for usable work with material weaknesses, 4 for strong work with localized weaknesses, and 5 for consistently strong work across adequately inspected regions. These anchors are an adapted review convention, not a substitute for criterion-specific judgment.

If required input is missing, use `score: null` with `unassessable`; if an item is outside the user's deliverable, use `score: null` with `not_applicable`. A narrative review need not be scored as if it were a systematic review or a compiled journal manuscript. Do not demand visuals merely to raise a number. This adaptation is intentionally unsuitable for direct comparison with published DAS scores.

Compute a family mean only over its declared scored items and show the denominator. With incomplete applicable items, label any aggregate a **partial adapted assessment** and list omissions. Reserve an all-sixteen-item adapted mean for sixteen valid scores under this profile. Never relabel it “official DAS-Eval,” impute missing scores, or convert it into a hallucination rate.

## What the released evaluators actually assess

**BSC:** the code builds sampled claim contexts, complete citation groups and compact evidence cards derived from abstracts and metadata. Its paper-content judge is restricted to those cards; citation-distribution statistics are computed separately. A hard-coded arXiv-year filter restricts the reference map to 2020–2026. Missing substantive evidence is kept separate from established defects. The prompt includes a neutral-score convention for limited evidence and restrictions on awarding high scores. Those are upstream calibration choices; the workbench instead exposes unassessable semantic judgments explicitly. [Pinned BSC implementation](https://github.com/ZhikaiXu24/DAS/blob/24fa88b3eee004f0926b978717ba4a716f79661a/DAS-Bench/evaluation/eval_bsc.py).

**TSQ/HDQ:** the active evaluation path sends a full PDF in hosted mode or rendered pages in local mode. A configured local image limit can send only the first pages, with a warning. The source also contains Markdown-audit/cap helpers; their existence does not prove that the active path supplied a deterministic audit to its judge. Distinguish a parsing artifact from a visible or semantic defect. [Pinned TSQ/HDQ implementation](https://github.com/ZhikaiXu24/DAS/blob/24fa88b3eee004f0926b978717ba4a716f79661a/DAS-Bench/evaluation/eval_tsq_hdq.py).

**MAR:** the judge examines rendered pages for artifact presentation and expressly excludes scientific correctness. By default it inspects all pages up to a budget of 50; longer documents are sampled across front, middle and back. A good first page does not establish quality elsewhere. Record the actual pages seen when performing an analogous audit. [Pinned MAR implementation](https://github.com/ZhikaiXu24/DAS/blob/24fa88b3eee004f0926b978717ba4a716f79661a/DAS-Bench/evaluation/eval_mar.py).

The released preprocessing script disables formula recognition and configures MinerU resources; it is not a portable dependency of this skill. Its runner continues after some stage failures, so process completion alone does not establish valid evaluation output. [Preprocessor](https://github.com/ZhikaiXu24/DAS/blob/24fa88b3eee004f0926b978717ba4a716f79661a/DAS-Bench/evaluation/eval_prepare.py), [runner](https://github.com/ZhikaiXu24/DAS/blob/24fa88b3eee004f0926b978717ba4a716f79661a/DAS-Bench/evaluation/run_eval_all.sh).

The protocol document says frozen evaluator prompts were not released, while the pinned Python files contain judge prompts. Preserve this documentation discrepancy; describe what was inspected rather than claiming a complete, internally synchronized reproduction package.

## General-purpose extension boundary

A library adapter supplies normalized source identity, version, local/remote pointers and locator provenance. A domain-rule adapter supplies additional applicable checks and the evidence needed to satisfy them. Neither may silently promote imported reading notes to newly audited original evidence.

Support older literature, non-arXiv articles, books and other sources when relevant to the user's scope. Do not inherit the upstream evaluator's date/provider filters. Attach the library snapshot and adapter identity/version to the run so an update can identify affected conclusions. The library supplies accumulated research; documented fresh searches still determine what recent or missing work must be added.

