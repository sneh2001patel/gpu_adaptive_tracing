# Step 040: The three ACM papers, and the gap update

Date: 2026-10-28.

## What was done

- Read the three papers the author downloaded manually (scripted access had been blocked), each in full including appendices and references:
  - Zhou et al., ICS '22 (named by Reviewer B);
  - Darvishi et al., ICSE-NIER '24;
  - Darche & Dagenais, ACM TOPC 11(2) 2024.
- Appended section-referenced notes to [literature_reading_notes_039.md](../audit/literature_reading_notes_039.md).
- Updated [related_work_matrix.md](../related_work_matrix.md) with:
  - three matrix rows;
  - two established points (§2 items 7–8);
  - the revised gap (§3);
  - three more draft and bibliography corrections (§4);
  - a new repetition-sampling comparator arm and fidelity metric (§5).

## Findings

1. **ICS '22 (Reviewer B's paper)** adapts *when PC samples are synchronized* (epochs end on a call-path conflict). It re-profiles already-seen kernel sequences only at random enabling rate E, and judges this by attribution fidelity against a full serialized profile (§5.3–5.5, Eq. 1, Table 2).
   - It is the closest prior art for "repeated evidence ⇒ collect less" in GPU profiling.
   - It does not trigger on anomalies, decide that a diagnosis is supported, or stop a serving capture.
   - It should be cited, and its policy added as a comparator arm.
2. **ICSE-NIER '24** proposes "adaptive tracing" at an SE venue: kernel tracing that becomes detailed on behavioral shifts (§3). It reports 77.1% fewer events against a 5.8% miss rate (§4), with no stopping rule. This further confirms the escalation mechanism is prior art and that the problem is in scope for SE.
   - Search snippets had said 92.7% / 20.4%; the PDF says 91.3% / 20.9%. Use the PDF numbers.
3. **Darche & Dagenais** do device-side kernel instrumentation (AMD, LLVM IR) for tuning small programs (§4.3, §5.1).
   - Our draft wrongly calls nsys "the same class" of tracing.
   - Our bib lists the wrong journal (TACO instead of TOPC).
4. **The candidate gap holds among the 16 papers read**, with narrower wording: when a bounded heavy GPU capture during a live serving incident has enough evidence to support a diagnosis, compared across stopping rules (now including probabilistic re-sampling) against independent references. "No prior work" phrasing remains disallowed.

## Scope of this step

Literature only. No paper, bib, source, test or GPU changes.

## Next

- Optionally obtain and read Pythia (SoCC '19) and Zhang et al. 2020.
- Start the Phase A query and codebook pilot.
