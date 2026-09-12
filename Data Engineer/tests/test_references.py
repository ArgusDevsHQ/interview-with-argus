import json
from pathlib import Path

import pytest

from net_new.dataset import Dataset
from net_new.references import align_cases, load_references, normalized_source, write_jsonl

ROOT = Path(__file__).resolve().parents[1]


def example(dataset):
    filing = next(f for f in dataset.replay_filings() if f.filing_id == "guidance")
    return {
        "reference_version": "test",
        "case_id": f"{filing.ticker}:guidance",
        "split": "development",
        "dataset_fingerprint": dataset.fingerprint,
        "filing_id": filing.filing_id,
        "ticker": filing.ticker,
        "available_at": filing.available_at.isoformat(),
        "current_document_ids": [d.id for d in dataset.current(filing)],
        "history_document_ids": [d.id for d in dataset.history(filing)],
        "title": "Guidance",
        "overview": "Test reference",
        "other_supported_topics": [],
        "limitations": ["Test only"],
        "findings": [
            {
                "finding_id": "guidance-1",
                "title": "Guidance update",
                "acceptable_classifications": ["changed"],
                "expected_facts": ["Test expectation"],
                "comparison": "Compare earlier guidance",
                "current_evidence": [
                    {
                        "document_id": "guidance-release",
                        "quote": normalized_source(dataset, "guidance-release"),
                    }
                ],
                "prior_evidence": [
                    {"document_id": "quarterly", "quote": normalized_source(dataset, "quarterly")}
                ],
                "acceptable_variations": [],
                "adjudication_notes": "Test only",
            }
        ],
    }


def test_references_use_original_sources_and_reject_future_or_fabricated_evidence(
    tmp_path, monkeypatch
):
    dataset = Dataset(ROOT / "data/demo")
    row = example(dataset)
    path = tmp_path / "references.jsonl"
    write_jsonl(path, [row])

    # Reference validation must still work when the candidate changes pipeline chunking.
    def no_parser(*args, **kwargs):
        raise AssertionError("Reference validation must not depend on pipeline parsing")

    monkeypatch.setattr("net_new.parsing.parse", no_parser)
    assert len(load_references(path, dataset)) == 1
    row["findings"][0]["prior_evidence"] = [
        {
            "document_id": "future-quarterly",
            "quote": normalized_source(dataset, "future-quarterly"),
        }
    ]
    write_jsonl(path, [row])
    with pytest.raises(ValueError, match="point-in-time"):
        load_references(path, dataset)
    row["findings"][0]["prior_evidence"] = []
    row["findings"][0]["current_evidence"][0]["quote"] = "This quote is invented."
    write_jsonl(path, [row])
    with pytest.raises(ValueError, match="quote not found"):
        load_references(path, dataset)


def test_alignment_keeps_missing_failed_and_empty_success_distinct(tmp_path):
    dataset = Dataset(ROOT / "data/demo")
    path = tmp_path / "references.jsonl"
    write_jsonl(path, [example(dataset)])
    cases = load_references(path, dataset)
    assert align_cases(cases, [])[0]["output_state"] == "missing"
    record = {
        "filing_id": "guidance",
        "ticker": cases[0].ticker,
        "status": "error",
        "prediction": None,
    }
    assert align_cases(cases, [record])[0]["output_state"] == "error"
    record.update(status="completed", prediction={"findings": []})
    result = align_cases(cases, [record])[0]
    assert result["output_state"] == "completed"
    assert result["output"]["prediction"]["findings"] == []
    assert "score" not in result
    with pytest.raises(ValueError, match="Duplicate output"):
        align_cases(cases, [record, record])


def test_frozen_development_labels_match_package_when_corpus_present():
    dataset_path = ROOT / "data/pilot"
    if not (dataset_path / "manifest.json").exists():
        pytest.skip("Unzip the data package to validate historical references")
    import hashlib

    path = ROOT / "references/development.jsonl"
    split = json.loads((ROOT / "references/split.json").read_text())
    dataset = Dataset(dataset_path)
    cases = load_references(path, dataset)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == split["development"]["reference_sha256"]
    assert [c.case_id for c in cases] == split["development"]["case_ids"]
    assert dataset.fingerprint == split["development"]["dataset_fingerprint"]
