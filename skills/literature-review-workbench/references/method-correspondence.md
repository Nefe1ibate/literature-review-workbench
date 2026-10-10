# Method correspondence and validation boundary

Use this when explaining fidelity to DAS or planning an effectiveness evaluation. The paper describes an engineering method and reports experiments; its state equations are not a proof that every review will be factually correct or publication-ready. The core method is substantially described in Section 3 and Appendix C, but executable generation materials referenced in C.7 are not present in the public repository at the pinned inspected commit.

| Mechanism | DAS location | Workbench implementation | Relationship |
|---|---|---|---|
| Persistent reusable paper understanding | 3.2.1, B | Paper/source/evidence records and library adapters | Retains the concept; uses a user-selected corpus rather than DAS-2M. |
| Candidate-grounded organization | 3.2.2, C.2 | Section objectives, paper routing, and scope checks | Retains the concept; no fixed Methods taxonomy or candidate quota. |
| Paragraph responsibility before claim/prose | 3.2.3, C.3 | Paragraph plans and linked claim/evidence records | Retains the dependency; Codex performs planning and drafting. |
| Limited, role-relevant state views | C.1 | Referenced records and narrow worker assignments | Guidance rather than an enforced runtime sandbox between LLM roles. |
| Deterministic checks | 3.2.3, C.4 | Standard-library consistency/fingerprint/dependency validator | Independent implementation; does not reproduce all upstream LaTeX rules. |
| Four scoped review/repair actions | 3.2.4, C.4 | Review records and affected-state invalidation | Retains the action structure; Codex implements the actual prose repair. |
| Original-source verification | C.3–C.4 | Named source inspection with locator/version and conditions | Extends the workflow; not equivalent to the manuscript-only Reviewer. |
| Artifact assembly and quality rubric | C.5, E | Requested outputs and adapted four-family checklist | Uses available output tools; does not recreate the image-generation system or official benchmark. |
| Version-aware repeatability | State design in 3.1–3.2 | Revisions, snapshots, events, source/profile hashes, selective rechecking | Workbench design; no claim of byte-identical text generation. |
| Domain and maintained-library interfaces | Workbench requirement | External profiles, namespaced fields, read-only adapters | Added for portability; not an upstream feature-equivalence claim. |

Primary references: [DAS paper](https://arxiv.org/html/2608.18034v1), [pinned generator release statement](https://github.com/ZhikaiXu24/DAS/blob/24fa88b3eee004f0926b978717ba4a716f79661a/DAS/README.md). Versioned source inspection is recorded in `das-provenance.json`.

## Three different validation questions

1. **Method fidelity:** Can a reviewer map the workflow's important decisions to the paper, identify substitutions, and explain missing executable detail? This table supports inspection; it does not make an independent implementation identical to the authors' system.
2. **Operational correctness:** Do records, source changes, unresolved evidence, rule changes and repairs behave as specified? Helper tests and isolated forward use address these observable properties. They do not measure review quality.
3. **Review effectiveness:** Does this skill produce better reviews for the intended tasks? This requires real-source evaluations, a suitable comparison condition, and inspection of outputs. Neither the authors' scores nor our unit tests answer it for this implementation.

Do not describe a completed helper test or synthetic exercise as an empirical demonstration of higher-quality scholarly reviews. At initial delivery, real-corpus comparative effectiveness remains unvalidated.

## A proportionate real-review evaluation

When the user requests effectiveness testing, select manageable tasks across relevant disciplines and freeze the questions, accessible corpus, source versions, model, output requirements and approximate effort budget. Compare ordinary Codex use with workbench use; state differences that cannot be controlled. An additional open-discovery test can examine literature coverage, but must log search providers and dates.

Blind the method identity where feasible. Have reviewers inspect substantive coverage, paragraph progression, cross-paper synthesis, retained conditions, attribution and original-source support. A reference review or expert-maintained inclusion set can inform coverage without being assumed exhaustive. Count missing sources, unassessable claims and inspected denominators separately. Record localized corrections needed and material disagreements, not just a mean score.

Repeat selected cases to assess variability; numerical thresholds should fit the use case and sample, not be chosen after seeing results. A small pilot provides bounded evidence. Wider domain generalization and superiority over the authors' DAS implementation require additional evidence. Treat later full upstream releases as new versioned inputs, compare them with this mapping, and revalidate changed components.
