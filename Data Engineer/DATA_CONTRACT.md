# Dataset and run contracts

## Corpus

`manifest.json` is validated by `net_new.dataset.Manifest`. It identifies the
dataset, fictional/historical status, replay dates, documents, optional prices,
and optional default cache directory. Document paths are relative to the corpus
root and cannot escape it. Loading verifies document SHA256 checksums.

Each document has a unique `id`, `filing_id` shared by a primary and its exhibits,
`ticker`, `company`, `form`, `role`, timezone-aware `available_at`, `path`,
`source_url`, and `sha256`. Exhibits share their parent filing's acceptance time.
Documents with identical timestamps are not assumed to precede one another.

Replay includes 8-K and 8-K/A primaries whose availability falls within the
inclusive date interval in America/New_York. Earlier annual/quarterly reports,
amendments, and 8-Ks remain available as background. Later periodic reports enter
history only after their availability time. The initial historical cutoff is
explicit: this is not an exhaustive record of everything previously public.

The starter retrieves prior text directly from source history. Earlier model
claims never become authoritative facts. All source documents are available for
human annotation, including filings for which the model emitted nothing.

`assets.json` in downloaded corpora inventories image and non-HTML exhibits.
The starter text parser does not OCR images or PDFs. Raw SEC HTML is retained
unchanged; some absolute image references still point to SEC. Downloaded assets
are available alongside it. Unresolved assets must be reviewed before release.

## Daily prices

CSV columns:

```csv
ticker,date,close,session_close
ASTER-DEMO,2024-09-03,100,2024-09-03T20:00:00Z
```

`date` is the exchange's trading date. `session_close` is that session's actual
close timestamp, including a timezone. Populate it from an exchange calendar;
do not assume 16:00 for early closes. One row per ticker/session, sorted by date.
Include a preceding session to calculate the first selected day's close-to-close
move. Include the following session to map the final after-hours filing.

The manifest records source, source URL, redistribution basis, currency, and
adjustment policy. Historical companies cannot be paired with fictional prices.
The app displays percentage price change, not abnormal returns or causal impact.
Select an adjustment basis that does not mistake stock splits for economic moves.

For the initial temporal candidate rule, associate each filing with the first
supplied trading close at or after its availability. A selected multi-day window
includes filings mapped to any session in it. No match is a valid result. This
simple rule is transparent and may have relevance limitations worth evaluating.

## Pipeline input and output

`build_input(dataset, filing, config)` exposes all eligible history document IDs,
the included current chunks, retrieved prior chunks, and total chunk counts.
Chunks have stable IDs tied to source hashes and parsed-text offsets. The starter
uses a bounded current context and lexical prior retrieval. It deliberately uses
an ordinary baseline implementation, without planted faults or injected errors.

`Prediction` contains `findings` and `limitations`. Each finding has a title,
announcement, change description, classification (`new`, `changed`, `repeated`,
or `uncertain`), and current/prior citations. Each citation names a document,
chunk, and quote. Schema validation is not factual validation; checking whether
claims and citations deserve trust is part of the candidate's work.

## Run artifacts

Every run writes a new directory:

- `run.json`: dataset fingerprint, config, implementation/prompt hashes, exact
  prompt, expected filing IDs, execution mode, status, timestamps, and error count.
- `records.jsonl`: one attempted result per replay filing, input hash, complete
  retrieved input, prediction or error type, generation latency, model metadata,
  usage, and raw model response when applicable.

No API keys or SDK error bodies are persisted. API errors remain visible as
error records; an error is not an empty successful result. The replay continues
after a model failure and exits nonzero if any calls failed. Parse/cache failures
mark the run failed and preserve its partial output and expected filing IDs.

Cache replay requires matching dataset, implementation/config, and per-filing
input hashes. Missing or stale cache is an error, never an implicit paid call.
Cached records identify their source run and preserve original generation
latency; do not interpret that latency as cache-serving latency.

`extractive-preview` is a deterministic interface smoke test and has no model
token usage. It emits conservative illustrative output, not benchmark results.
Real cached model runs use `litellm` or `openai` and preserve their metadata.

## Reference fixtures and case alignment

`net_new.references.ReferenceCase` defines versioned, source-anchored reference
cases; see `references/README.md`. Gold is stored separately from model runs and
is never a provider or cache fallback. `reference_app.py` displays development
references. `streamlit_app.py` displays the selected model run or source-only
content when no model run is installed.

`InvestorPrediction` extends `Prediction` with `headline` and `overview`.
Real baseline caches may use `litellm` or `openai`; the full pipeline stays local
in both modes. Only inference crosses the LiteLLM endpoint. A completed model
run can be activated, while manually authored reference content cannot.

`python -m net_new.compare` aligns by ticker/accession and preserves missing,
failed and completed outputs. It validates the corpus fingerprint against both
references and the run. It performs no semantic matching and computes no score.
