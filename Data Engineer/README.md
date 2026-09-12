# Data Engineer take-home — What's net new?

At Argus, data engineers build and operate data pipelines, with an initial focus
on evaluating AI outputs, detecting quality regressions, and making changes
measurable. This exercise focuses on that quality and operations work within a
supplied pipeline.

An investor selects a company and a period on its price chart. The supplied
application surfaces nearby 8-K disclosures and explains what was announced,
what changed from earlier filings, and the evidence supporting that comparison.
We want to know how reliably it does this, whether changes improve it, and how
we would notice degradation when most outputs receive no human review.

You receive the complete local pipeline, source documents, development reference
examples, and a baseline run. Model inference is available through a funded
LiteLLM endpoint. Everything else runs locally and can be inspected or modified.

## Your task

Build a repeatable evaluation and monitoring layer around this workflow.

1. **Establish baseline quality.** Compare the supplied outputs with the labeled
   development cases. Choose and justify metrics suited to investor usefulness.
   Account for unsupported claims, missed developments, novelty judgments and
   evidence. Trace conclusions to concrete cases, including failures.
2. **Make changes measurable.** Identify consequential design choices in the
   implementation and explain which you would investigate and why. Your harness
   should support comparing a fixed baseline and another run. If you experiment,
   state your hypothesis, measure the change on the same cases, and describe
   regressions and operational trade-offs. A credible negative result is useful.
3. **Demonstrate monitoring.** Treat the historical replay as arriving batches
   with no fresh human labels. Implement checks, justify alert thresholds, and
   explain what remains invisible. If no batch crosses a justified threshold,
   say so; do not manufacture an alert.
4. **Assess transfer to another company.** Freeze your selected configuration,
   then run it on the supplied holdout company. Report observable behavior,
   failures, costs and limits of your conclusions without claiming labeled
   accuracy you have not measured. We retain its labels for assessment. If you
   change your approach after inspecting holdout results, disclose that and call
   the subsequent run exploratory.

A measured improvement is encouraged, not required for a strong submission.
Evaluation and monitoring are required. Creating a large annotation set, building
an ingestion system, or redesigning the investor app is not the assignment.

## How to use the references

The development set contains nine AMD/CrowdStrike disclosures and expected
findings with current and earlier source evidence. It is a source-checked,
non-exhaustive reference set, not a string-matching answer key. Correct wording,
finding count, and grouping may vary. Use the facts, periods, novelty distinctions,
and evidence to define agreement. A supported extra finding can be valid even
when absent from the references; explain how you handle it. Flag reference errors
or ambiguity with source evidence rather than silently changing labels to fit a run.

"Previously known" means available in the supplied earlier documents at the
filing's acceptance timestamp. Annual and quarterly reports and earlier 8-Ks
provide history. The corpus is not all public news. Multiple relevant filings or
no supported match are valid; a nearby disclosure does not establish what caused
a stock-price move. Missing and failed outputs are not the same as successful
outputs containing no findings.

Reference wording is not shown as pipeline output. View development examples
separately with `reference_app.py`. The frozen partition is in
`references/split.json`; private holdout labels are not included in your materials.
The small company sample cannot establish broad production accuracy.

## Deliverables

- Working evaluation and monitoring code with reproducible commands.
- Case-level evidence behind your aggregate results, and any proposed reference
  corrections or additional labels.
- A short `FINDINGS.md`: what you measured and why; baseline results and important
  failures; any experiments and trade-offs; what you would alert on and at what
  thresholds; transfer results and uncertainty; and next steps with more time.
- Identify the reference version, baseline/run paths, selected configuration,
  dependencies, and approximate time spent.

We assess evaluation judgment, evidence, reproducibility, and operational
usefulness. We do not prescribe a metric, judge model, or evaluation framework.
A fluent summary, valid JSON, or a successful run does not prove correctness.

**Suggested effort: four hours.** You have the weekend to submit and may spend
longer. Extensions count toward assessment. AI assistance is welcome; briefly
describe how you used it in `FINDINGS.md`. In the follow-up walkthrough, we will
use your code, evidence, and results to discuss your decisions and their limits.
Prioritize a defensible, working core.
Optional extensions include measured pipeline improvements, a monitoring
visualization, or comparisons with historical market reactions to similar news.

## Setup

Unzip `candidate-code.zip` into a working directory. Unzip `candidate-data.zip`
into that same directory so `data/pilot/manifest.json` and
`data/holdout/manifest.json` exist. Verify archive hashes against `SHA256SUMS`.

```sh
uv sync --frozen
uv run streamlit run streamlit_app.py
# Separate reference viewer; run in another terminal.
uv run streamlit run reference_app.py --server.port 8502
uv run pytest -q
```

Your private candidate `.env` contains `ARGUS_INFERENCE_URL`,
`ARGUS_INFERENCE_KEY`, and `ARGUS_MODEL`. Use `.env.candidate.example` as a template
and provide your own `SEC_USER_AGENT` name/contact for downloads. Do not commit
credentials. Candidates receive a LiteLLM virtual key, never the provider key.
The template uses the deployed candidate endpoint and `anthropic-fast-v1`;
`inference-status` lists all six available aliases.

```sh
# Inspect the source corpus.
uv run python -m net_new.cli inspect --dataset data/pilot

# Reproduce the supplied baseline without any model access.
uv run python -m net_new.cli replay --dataset data/pilot \
  --provider cache --cache data/pilot/baseline --output runs/baseline-replay

# Generate another run using your candidate inference access.
uv run --env-file .env python -m net_new.cli replay --dataset data/pilot \
  --provider litellm --output runs/experiment-01

# Join cases and outputs. This supplies no matching algorithm or accuracy score.
uv run python -m net_new.compare --dataset data/pilot \
  --references references/development.jsonl --run runs/experiment-01 \
  --output runs/experiment-01/aligned.jsonl

# Final transfer run after freezing your selected configuration.
uv run --env-file .env python -m net_new.cli replay --dataset data/holdout \
  --provider litellm --output runs/holdout-final
```

For offline baseline replay, use the unmodified starter checkout; cache validation
rejects changed pipeline code/configuration or data. Keep that baseline run when
experimenting. `--activate` can display a complete model run in the investor app;
its output directory must be inside the dataset. Use `ARGUS_DATASET=data/holdout`
to open holdout outputs in the app. The UI never executes a model automatically.

The downloader is provided for additional exploration. For example, to reproduce
the holdout source corpus (not its labels):

```sh
uv run --env-file .env python -m net_new.cli download --ticker NVDA \
  --start 2024-08-28 --end 2024-11-21 --output data/nvda-extra
```

The public price snapshot has gaps, including MSFT and AAPL in the tested 2024
period. Missing prices produce an error, not invented values; downloaded source
filings remain usable. Source coverage and price provenance accompany each corpus.

See [DATA_CONTRACT.md](DATA_CONTRACT.md) for input/output formats and
[references/README.md](references/README.md) for reference and alignment conventions.
`data/demo` is a fictional unit-test fixture only; it is never an investor-data
fallback or part of the scored development/holdout set.

## Preparation status

A package containing `PREFLIGHT_ONLY.md` is an internal setup rehearsal, not the
candidate handoff: it does not yet include a real baseline model run. The release
builder refuses to produce a handoff package until a complete matching model
baseline is supplied. References have an explicit single-reviewer status; they
have not received independent human adjudication.

## Inspect inference access and choose a model

```sh
uv run --env-file .env python -m net_new.cli inference-status
uv run --env-file .env python -m net_new.cli inference-status --json
uv run --env-file .env python -m net_new.cli replay --dataset data/pilot --provider litellm --model gemini-fast-v1 --output runs/gemini-fast-01
```

Choose an alias returned by `inference-status`. `--model` overrides `ARGUS_MODEL`
for that run and is recorded in its configuration. Cache replay cannot change
models. Request IDs, catalog version, reported model and available cost metadata
are saved locally; a returned alias alone does not verify the provider model.
The allowance is a soft cap: recorded spend can lag and in-flight calls can
overshoot. Exhaustion requires an operator top-up.
