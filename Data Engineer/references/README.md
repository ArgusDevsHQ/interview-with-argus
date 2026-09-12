# Reference and comparison conventions

`development.jsonl` holds one case per disclosure. Case IDs combine ticker and
SEC accession, and finding IDs are stable within reference version 1.0.0.
`split.json` freezes the company partition, case IDs, source fingerprints and
reference-file hashes. The holdout hash is a commitment to a private file; it
contains no answers.

A case specifies all current filing/exhibit IDs and strictly earlier available
history. Findings contain expected facts, comparison, acceptable classifications,
source quotes, acceptable variations and interpretation notes. Evidence quotes
are anchored to complete original HTML documents, not pipeline chunks: changing
chunking or retrieval does not change reference truth. The loader verifies
whitespace-normalized quote presence, source eligibility, timestamps, IDs and
corpus fingerprints. These are integrity checks, not a factual accuracy grader.

The references do not claim completeness. `other_supported_topics` identifies
some additional valid coverage. Additional output requires source review; do not
turn unmatched findings into automatic false positives. Similarly, an empty
reference list would not prove that a document contains nothing substantive.

Financial results for a new period can be described as newly reported information
or as a change from the preceding period. Several fixtures therefore allow both
`new` and `changed` conditional on a correct explanation. That tolerance does not
make `repeated` or `uncertain` interchangeable, or allow a next-quarter forecast
to be mislabeled as a revision of the previous quarter's guidance. Preserve the
period, units, sign, GAAP/non-GAAP basis, and plan-versus-completed distinction.

The supplied alignment command joins whole cases, never finding rows. Its
`output_state` is `completed`, `error`, or `missing`, and retains the original
record. It rejects duplicate and unexpected case IDs. Finding matching,
metrics, aggregation, uncertainty, judge validation and monitoring are candidate
work. There is deliberately no default score to optimize.

If you believe a reference is wrong or incomplete, record the case/finding ID,
your proposed correction, source evidence and effect on the results. Preserve
original results for comparison. Do not silently rewrite frozen labels.

Review status: original sources checked by the authoring assistant; independent
human adjudication has not occurred. This limitation is part of the reference
contract. Model outputs were not used to select these labels or the split.
