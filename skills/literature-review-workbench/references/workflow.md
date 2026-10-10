# Source-grounded review workflow

Use this for creating or substantially updating a review. It is a decision framework, not a mandatory fixed number of stages or agents. Scale work to the user's assignment and evidence access. The state contract defines machine-readable records; the domain profile supplies optional specialized questions.

## Establish the review experiment

Record the topic, questions, intended audience, output language and form, literature horizon, and inclusion/exclusion logic. Distinguish a focused conceptual synthesis, a comprehensive narrative review, and preparation for a systematic review. `systematic-prep` records searches and decisions; it does not automatically satisfy a discipline's reporting standard.

Load any supplied model, protocol, draft, or research notes as background. These can define the user's research problem but cannot establish external findings or priority. Save the research questions and comparison dimensions in the workspace. If the user has specified a local library or domain profile, connect it before rediscovering the same materials. Keep the original library unchanged unless its maintenance is explicitly part of the request.

A library's model/protocol copies may be historical snapshots. Before assessing a conflict or the current contribution, compare them with the user's designated working files and any newer materials referenced in accessible chats. A date in the filename is not a reliable content-version identifier. Register current bytes as new sources, retain historical copies and a difference log, and distinguish the external literature cutoff from the date of internal research updates. Do not silently rewrite prior evidence or infer that a conflict remains unresolved merely because it exists in an old snapshot. Chat summaries identify leads; inspect the actual revised artifact before transferring its claimed result.

A later scope change is explicit project state. Preserve the previous cutoff and decisions in the event history; distinguish newly included papers from new versions of existing papers. No fixed publication-year floor, citation target, or domain-specific chapter structure applies.

## Discover and acquire

Use the available academic search capability for discovery and primary author, publisher, repository, or institution sources for confirmation. If a paper-search skill is available and appropriate, use it; the workbench has no mandatory search provider. Open reviews combine database queries, backward references, forward citations, and issue-specific searches. Respect a user-imposed closed corpus.

Log actual queries, provider/date/filters, failures, empty results, and material access limits. Deduplicate first by DOI, then normalized title/author/version evidence. A working paper and publication generally share a paper record with separate source records; do not collapse materially different studies merely because their titles resemble each other.

Download accessible primary texts and relevant supplements into the requested corpus or review workspace, or reuse existing local copies. Register source URLs, versions, access dates, fingerprints, and completeness. Do not treat an abstract as an accessible full paper. Mark unresolved acquisition as pending and continue independent work. Initial exclusions may be based on obvious topic mismatch; substantive inclusion and comparison require the reading appropriate to the review's scope.

## Read and build paper cards

Prepare a structured card, small enough to retrieve repeatedly but connected to original text:

- identity and version; question and role in the research history;
- actual reading coverage and unavailable parts;
- mechanism or conceptual account; key definitions and assumptions;
- data, observation design, methods, target objects, results, and scope;
- relevant derivations or empirical comparisons; limitations and alternative explanations;
- evidence IDs and exact source locations;
- provisional role: core comparison, methodological support, historical context, boundary discussion, or exclusion with reason.

Use only dimensions meaningful in the discipline. A humanities paper need not have an estimator; a theoretical paper need not have data. Domain extensions can supply specialized fields. Preserve equations, tables, footnotes and appendices when they carry the claim. Automated extraction assists navigation; compare pivotal quotations, formulas, numerical results and proof steps with original pages. Record physical PDF page and printed page separately where available. For HTML/text, use section, anchor, equation or line references rather than inventing PDF pages.

Before setting evidence to `supported`, a named reviewer must inspect the cited location and its needed context against the specific source fingerprint. Record conditions that limit the paraphrase. This checks that the source says what the evidence record claims; it does not prove that the source itself is correct. A source's internal mathematical or causal correctness can require additional domain review.

Imported notes retain provenance and help prioritize reading. Their historical status alone cannot establish a new claim's support. If full reading is required but supplements are missing, state which conclusions are consequently unverifiable.

## Construct the argument from the candidate set

Build an outline after examining the candidate cards. Possible organizing principles include historical changes, competing mechanisms, data/identification distinctions, unresolved problems, or methods. Select what explains the user's question; do not assume the computer-science structure of the DAS experiments transfers to every discipline.

For each section specify its purpose, comparison dimensions, candidate papers, and claims. Reverse-route papers to sections; a paper may have several roles or none. Check thin sections and route mismatches before writing. Avoid one paragraph per paper when the question requires a cross-paper comparison.

For each paragraph specify its argumentative responsibility, needed claims, supporting papers/evidence, transition, and an approximate length if useful. Claim plans distinguish:

- **source result:** attributes a finding to a particular work and version;
- **interpretation:** an explicitly labeled reading of that work;
- **synthesis:** compares or combines works while preserving their different conditions;
- **proposed gap:** a scoped claim about an unresolved issue or the user's possible contribution.

A newness or absence claim needs search records and comparison scope. Prefer a qualified, inspectable boundary to an unbounded claim such as “no prior work.” Do not transfer applicability between settings without evidence or a stated inference. Keep the user's proposed contribution separate from established external results.

Mark actual priority or absence assertions with `priority_claim` or `absence_claim`. A source-informed future research question is not automatically an assertion that the literature lacks such a study; preserve that distinction. When the review is closed-corpus, a local search log can substantiate a claim limited to those materials without requiring an unauthorized external search.

## Draft and review in two layers

Draft from accepted evidence and planned claims, using stable paper IDs and a bibliography that can be rendered in the requested citation style. If a passage discusses a pending result, mark the uncertainty in prose rather than representing it as established. Check that the final citation actually points to the relevant paper/version and that the cited work supports the adjacent sentence.

**Source layer:** inspect claim support, conditions, attribution, conflicting evidence, evidence completeness, and relevant domain checks. Central comparisons, priority claims, delicate proofs, and high-impact numerical or causal claims deserve independent review when resources permit. The reviewer needs the originals and the claim context; prose-only evaluation cannot settle source correctness.

**Writing layer:** assess the adapted DAS dimensions in `das-method-and-evaluation.md` when useful: coverage, organization, development, synthesis, limitations and argument. Use evidence-aware findings, not a single opaque quality score. An unavailable criterion is `unassessable`, not an implicit neutral or passing score. If using numerical ratings, identify the rubric version, assessed denominator and missing-input count. Do not call these official DAS-Bench results.

Run the deterministic validator as a third, narrower check. It tests record consistency and recorded prerequisites, not whether prose logically follows from a theorem or whether the review missed a literature.

When independent review is used, follow [the version and context discipline](independent-review.md). A review of individual papers does not automatically clear their assembled cross-paper argument. Bind a final receipt to retained manuscript bytes and the selected profile; after material edits, perform a scoped recheck before carrying an acceptance forward.

## Repair the smallest affected scope

Map findings to actions:

| Action | Use when | Repair |
|---|---|---|
| `ACCEPT` | The requested scope meets its evidence and writing criteria | Record the decision and assessed inputs. |
| `DIRECT_EDIT` | A localized wording, citation or qualification fix resolves the finding | Amend the passage; recheck changed factual claims. |
| `REPLAN_PARAGRAPH` | The paragraph's responsibility or support is incoherent | Rebuild its claim plan and draft; check transitions. |
| `REPLAN_SECTION` | The section objective, routing or argument is defective | Revisit section/paragraph plans; retain unaffected work. |

Do not globally regenerate a review for a local correction. A changed source or claim invalidates dependent support and accepted prose. A changed section scope can invalidate paragraph routing even if paper bytes stay the same. Profile changes require current applicable rule checks. Keep previous snapshots and reasons for changes.

Choose review effort proportional to the assignment and user constraints. Continue repairs while meaningful progress is possible. If missing originals, unresolved disagreements, or a user-imposed budget prevents resolution, deliver the usable scope with explicit outstanding findings; do not invent a passing judgment or stall unrelated work.

## Assemble and preserve a reusable result

Reconcile duplicated arguments, vocabulary, citation style, dates, and conflicting version-specific findings. Deliver the requested editable review; add per-paper reports, PDF, bibliography library, or detailed evidence tables according to the request. Reports can condense explanation without misrepresenting reading coverage.

When exporting mathematical prose, check that the renderer recognizes the actual formula delimiters used in the source. Zero renderer errors can also mean that formulas were never parsed. Compare rendered equations and the exported content with the editable manuscript, then inspect the requested pages for clipping, bare markup and missing text; keep this export check separate from scientific review.

Preserve a reading index and an evidence/claim trace, searches and decisions, unresolved findings, and a final checkpoint. The completion note identifies source-verification coverage separately from structural validation and prose assessment. A future update loads this state, checks changed fingerprints, searches for material additions when the scope is open, and repairs affected claims without treating previous acceptance as permanent.
