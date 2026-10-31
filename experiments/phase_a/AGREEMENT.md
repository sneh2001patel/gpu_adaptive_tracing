# Phase A pilot: inter-coder agreement (30 issues)

Date: 2026-10-28. Coders:
- **Coder 1** (Claude, an LLM): codebook v0, [pilot_coding.csv](pilot_coding.csv).
- **Coder 2** (SP, human): codebook v1, [coder_sheet_ans.csv](coder_sheet_ans.csv). Coder 2 read each GitHub thread and assigned every code without AI help, and did not see coder 1's codes.

Computed by [agreement.py](agreement.py); full output in [agreement_output.md](agreement_output.md).

## AI-use record

- Coder 2 later had an AI model rewrite the notes "in a more uniform way", producing [second_coder_sheet.csv](second_coder_sheet.csv).
- That pass also changed **109 code cells in 25 of 30 issues**. Some changes are verifiably wrong. For example, it dropped the fix PR for vllm#7619: PR #7822 was merged and closes #7619, but the issue was recoded from `fixed_pr` to `unclear`.
- `second_coder_sheet.csv` is therefore **archived and not used**: it is not an independent human coding.
- For reference, the AI-revised sheet gives cause_category κ 0.35 and resolution κ 0.57. Run `python agreement.py second_coder_sheet.csv` to reproduce this.
- **Coder 1 is an LLM.** The figures below are human-vs-LLM agreement. A reportable reliability figure needs two human coders, or a disclosed human-plus-LLM design (see Next).

## Method notes

- **v0 → v1 mapping for coder 1:** five coder-1 cells were re-expressed in v1 vocabulary. Each change only restates what coder 1's own v0 note already said, and is listed in `V0_TO_V1` in the script:
  - vllm#9565 → `model_or_algorithm_implementation`;
  - vllm#36943 → `host_counters`;
  - sglang#14665 → `per_step_microbenchmark;trace_unspecified`;
  - vllm#21278 → `llm_assistant`;
  - vllm#20316 → `fixed_pr_stale_closed`.
- **Coder 2 normalization:** `C2_NORMALIZE` in the script maps a few non-codebook spellings. All of them occur only in the archived AI-revised sheet; coder 2's own sheet uses codebook values throughout.
- **Excluded fields:** `reporter_is_maintainer` and `scope_unit` are new in v1 and are not compared.
- **Disclosure:** coder 1 saw coder 2's answers before the coder-1 mapping was applied. The mapping is restricted to coder 1's own written notes to limit contamination, but the paper must state this.
- **Field coverage:** only `include` is compared on all 30 issues. Other fields are compared on the 17 issues both coders included. With n = 17, every κ below has a wide uncertainty band. Read them as signals of which definitions are unclear, not as reportable reliability.
- **Multi-valued fields:** reported as exact-set agreement and mean Jaccard overlap. Single-value κ uses each coder's first listed value.

## Results

| Field | n | % agree | κ | Reading (Landis & Koch) |
|---|---|---|---|---|
| include | 30 | 83% | 0.63 | substantial |
| symptom (first value) | 17 | 71% | 0.62 | substantial |
| baseline (first value) | 17 | 88% | 0.84 | almost perfect |
| multi_gpu | 17 | 100% | 1.00 | perfect |
| profiler_by | 17 | 88% | 0.55 | moderate |
| profiler_role | 17 | 88% | 0.56 | moderate |
| cause_category (first value) | 17 | 71% | 0.64 | substantial |
| cause_confirmed_by | 17 | 100% | 1.00 | perfect |
| resolution | 17 | 94% | 0.91 | almost perfect |
| repro_candidate | 17 | 76% | 0.55 | moderate |

Multi-valued fields (n = 17):

| Field | Exact-set agreement | Mean Jaccard overlap |
|---|---|---|
| evidence | 10/17 | 0.73 |
| cause_category | 10/17 | 0.68 |
| symptom | 8/17 | 0.64 |
| baseline | 11/17 | 0.75 |
| evidence_requested | 14/17 | 0.82 |

**Overall:**
- Reliable already: the outcome fields (`cause_confirmed_by`, `resolution`, `multi_gpu`, `baseline`).
- Weaker: the judgement-heavy fields (the inclusion boundary, profiler attribution, primary cause, and reproduction screening).
- Published studies report κ ≥ 0.77 (Cao et al.) and ≥ 0.87 (Liu et al.). Our weaker fields need tighter rules before the main sample.

## What the disagreements show, and proposed v2 rules

The proposed rules come from inspecting the disagreements.

1. **Inclusion boundary (5 of 30 disagree).**
   - Issues that disagree: vllm#8457, #7518 (coder 2 includes, coder 1 excludes); vllm#23739, #44858, #5274 (coder 1 includes, coder 2 excludes).
   - Cases:
     - #8457: an optimization proposal whose only numbers are microbenchmarks of the proposed change;
     - #7518: a measurement-confusion question (coder 2 itself noted "could arguably be excluded");
     - #23739: a profiler-visibility question without a slowdown number;
     - #44858: a cache-policy proposal;
     - #5274: a startup OOM.
   - *Rule:* include when the thread contains a **measured** shortfall, or a stall or OOM **during serving or inference**.
     - Exclude failures that occur only at initialization (vllm#5274) as `not_performance`.
     - Exclude proposals whose only number is a microbenchmark of the proposed change itself (vllm#8457) as `feature_request`.
     - Exclude measurement-method questions and profiler or metrics questions with no performance number (vllm#23739) as `usage_question`.
     - vllm#7518 needs adjudication. The prefix-caching speedup was real; the question was where it showed up.
   - Add a worked example of each type to [CODING_GUIDE.md](CODING_GUIDE.md).
2. **Version comparisons.**
   - Coder 1 coded `bisect` inconsistently: present for vllm#6240, #31961 and sglang#14665; missing for vllm#9413, #36943 and #5523. Coder 2 was consistent.
   - *Rule:* rename the value to `version_comparison`, and apply it to any between-version comparison shown in the thread.
3. **Tool attribution by inference.**
   - Coder 1 coded vllm#2150 as `torch_profiler` from the visual style of an unnamed memory visualization.
   - *Rule:* if the tool is not named in text, code `trace_unspecified`. A note may record what the screenshot looks like.
   - Adjudicate vllm#2150 `profiler_role` (coder 1 `decisive`, coder 2 `none`) and sglang#14665 (coder 1 `decisive`, coder 2 `supporting`) under this rule.
4. **`profiler_by` when the reporter is a maintainer (vllm#7619).**
   - *Rule:* `profiler_by` records the person's role in the thread (reporter / responder). Project membership is recorded only in `reporter_is_maintainer`.
   - Rename the values to `reporter`, `responder_maintainer`, `responder_other`, `none`.
5. **Single vs multiple causes.**
   - Coder 1 listed several causes where coder 2 listed one: vllm#2150, #31961, #4917, sglang#14665.
   - *Rule:* `cause_primary`, a single value naming what the fix or explanation addresses, plus an optional `cause_secondary`.
   - sglang#14665 needs adjudication: coder 1 `cpu_overhead;kernel_backend_selection`, coder 2 `decode_attention_kernel`. The fix PR #15009 converts NumPy indices to Torch tensors in FA3 block-table preparation.
6. **`cause_category = other`.**
   - Used by coder 2 for sglang#922 and vllm#7619, where coder 1 chose `prefill_heavy_input` and `memory_management`.
   - *Rule:* `other` is allowed only when no listed category fits, and the note must name the proposed category, for example `other: execution_mode`. Repeated `other` notes become new v2 categories.
7. **Reproduction screen.**
   - Coder 1 marked old-version issues `maybe` (`version_too_old`); coder 2 marked them `yes` (vllm#4917, #7619).
   - *Rule:* decide in advance whether pinning an old vLLM release is acceptable. If it is, version age is not a blocker; record the version in notes.
8. **Linked-PR check.**
   - Coder 2 checked PR merge state and GitHub `author_association`, which coder 1's thread copies did not include.
   - *Rule:* for every closed issue, check the cross-referenced PRs for one that closes the issue, and record it in `fix_ref`, for example `#7822 merged`.
   - The thread-fetch script should capture `author_association` and each linked PR's merge state and closing references.
9. **AI-use protocol (from the AI-use record above).**
   - Coders assign every code themselves.
   - An AI tool may only polish note wording, after the code columns are frozen, and the original notes are kept.
   - Any AI use is logged per round.

## Next

1. **Adjudicate:** both coders go through the disagreement list in [agreement_output.md](agreement_output.md) and agree a resolved code for each. That resolved file becomes the pilot's final coding.
2. **Codebook v2:** apply rules 1–9 above.
3. **Second human coder:** recruit one, for example a labmate, for the fresh round. Coder 1 being an LLM means the pilot κ is human-vs-LLM. The paper can report LLM-assisted coding only with a human–human reliability figure alongside it.
4. **Agreement on fresh issues:** measure agreement on a **fresh** sample of about 20 issues, never the same 30, because coders now know each other's reasoning. Proceed to the main sample once the judgement fields reach κ ≥ 0.7.
