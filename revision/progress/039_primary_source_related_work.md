# Step 039: Primary-source related-work matrix

Date: 2026-10-28.

## What was done

- Downloaded 13 papers into [litterature_review/papers/](../../litterature_review/papers/); provenance is in that folder's README.
- Read each one in full. Pivot Tracing's reference list was skimmed; its main text was read in full.
- Recorded section-referenced notes in [literature_reading_notes_039.md](../audit/literature_reading_notes_039.md).
- Condensed the notes into [related_work_matrix.md](../related_work_matrix.md):
  - a comparison matrix;
  - what is already established;
  - a conditional candidate gap;
  - required corrections to the ICSE draft and bibliography;
  - design implications.

## Not obtained

The ACM Digital Library returned an HTTP 403 bot check to scripted download, so three papers were not obtained and are not cited for any claim:
- Zhou et al., ICS '22 (named by Reviewer B);
- Darche & Dagenais, TACO;
- Darvishi et al., ICSE-NIER '24.

## Main findings

1. **Anomaly-triggered escalation to detailed GPU tracing for LLM inference exists.** LatencyPrism §3.2.3 and StriaTrace §5.3.2 both do it, so the old controller formulation is not novel as a mechanism.
2. **BPW names circular evaluation and defines a remedy.** It explicitly identifies predicted-label circularity and uses prediction-independent references with pre-fixed thresholds. Our reference design should adopt it.
3. **No paper read evaluates when a bounded heavy GPU capture has collected sufficient evidence.** The candidate gap stays conditional until ICS '22 and ICSE-NIER '24 are read.
4. **Liu et al. already provide a general LLM-inference-engine bug taxonomy.** Phase A must be scoped to performance issues and to the diagnostic evidence developers collect.
5. **Eight corrections are needed in the draft and bibliography.** They cover:
   - Astraea's "budget";
   - TraStrainer's "CPU and memory pressure";
   - the "no prior work" claim;
   - the Pivot Tracing and Hindsight characterizations;
   - the Hindsight venue and DOI, the Pivot Tracing URL, the HPCToolkit venue, and the Astraea venue.

## Scope of this step

Literature work only. No scientific results, GPU use, source or test changes. Neither the paper `.tex` nor the `.bib` was edited; the corrections are listed for the rewrite.

## Next

- Obtain the three ACM PDFs through a browser or institutional access and read them.
- Then update the matrix's §3 gap before drafting any novelty sentence.
- Then start the Phase A query and codebook pilot.
