# Step 042: Pilot inter-coder agreement

Date: 2026-10-28.

## What was done

- Received coder 2's independent codes (SP, codebook v1) for the 30 pilot issues.
- **AI-use record (same day):** coder 2 later had an AI model rewrite the notes (`second_coder_sheet.csv`); that pass also changed 109 code cells in 25 issues, some verifiably wrongly. It is archived and not used. Figures below are on coder 2's own sheet, `coder_sheet_ans.csv`. Coder 1 is an LLM, so these are human-vs-LLM figures.
- Mapped coder 1's v0 codes to v1. The mapping is documented and restricted to coder 1's own notes.
- Computed Cohen's κ and set-overlap agreement with [agreement.py](../phase_a/agreement.py).
- Analysed the disagreements and wrote [AGREEMENT.md](../phase_a/AGREEMENT.md).

## Results

These are pilot figures and n is small.

| Field | κ |
|---|---|
| include (30 issues) | 0.63 |
| baseline | 0.84 |
| resolution | 0.91 |
| cause_confirmed_by | 1.00 |
| multi_gpu | 1.00 |
| symptom | 0.62 |
| cause_category | 0.64 |
| profiler_by | 0.55 |
| profiler_role | 0.56 |
| repro_candidate | 0.55 |

The non-inclusion fields cover the 17 issues both coders included.

The disagreements produced nine rules for codebook v2 (see AGREEMENT.md). Beyond the seven below, they add a rule that `other` must name a proposed category, and an AI-use protocol (coders assign every code; AI may only polish notes after codes are frozen). The seven cover:
- the inclusion boundary;
- `bisect`, renamed `version_comparison` (coder 1 was inconsistent);
- no tool attribution by inference;
- `profiler_by` defined by role in the thread;
- a primary-cause field;
- the old-version reproduction rule;
- capturing PR merge state and `author_association`.

## Caveats

- Coder 1 saw coder 2's answers before mapping. This is mitigated by restricting the mapping to coder 1's own notes, and is disclosed.
- n = 17 for most fields, so κ is unstable.
- The same 30 issues cannot be reused to measure v2 reliability.

## Scope of this step

CPU only. No GPU use, paper, bib or source changes.

## Next

1. Adjudicate the disagreements.
2. Write codebook v2.
3. Recruit a second human coder.
4. Measure agreement on a fresh sample of about 20 issues.
