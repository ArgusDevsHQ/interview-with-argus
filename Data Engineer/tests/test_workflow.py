from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from net_new.dataset import Dataset, Document, local_file
from net_new.pipeline import build_input, config, load_records, run_replay

DEMO = Path(__file__).resolve().parents[1] / "data" / "demo"


@pytest.fixture
def dataset():
    return Dataset(DEMO)


def test_history_excludes_future_and_current_exhibits(dataset):
    filing = next(d for d in dataset.replay_filings() if d.filing_id == "guidance")
    context = build_input(dataset, filing, config("extractive-preview"))
    assert set(context["eligible_history_document_ids"]) == {"annual", "quarterly"}
    assert set(context["current_document_ids"]) == {"guidance", "guidance-release"}
    assert "future-quarterly" not in json.dumps(context)
    assert "$120 million" not in json.dumps(context)


def test_prior_8k_is_known_even_without_prior_pipeline_run(dataset):
    filing = next(d for d in dataset.replay_filings() if d.filing_id == "repeat")
    assert {"guidance", "guidance-release"} <= {d.id for d in dataset.history(filing)}


def test_company_histories_do_not_mix(dataset):
    filing = dataset.replay_filings()[0]
    other = dataset.documents[0].model_copy(update={"id": "other", "ticker": "OTHER"})
    dataset.documents.append(other)
    assert "other" not in {d.id for d in dataset.history(filing)}


def test_equal_timestamp_is_not_assumed_prior(dataset):
    filing = dataset.replay_filings()[0]
    same_time = dataset.documents[0].model_copy(
        update={
            "id": "simultaneous",
            "filing_id": "simultaneous",
            "available_at": filing.available_at,
        }
    )
    dataset.documents.append(same_time)
    assert "simultaneous" not in {d.id for d in dataset.history(filing)}


def test_after_hours_and_weekend_map_to_next_trading_close(dataset):
    filings = {d.filing_id: d for d in dataset.replay_filings()}
    assert dataset.effective_session(filings["guidance"]) == date(2024, 9, 4)
    assert dataset.effective_session(filings["ceo"]) == date(2024, 9, 9)
    assert dataset.filings_for_window("ASTER-DEMO", date(2024, 9, 11), date(2024, 9, 13)) == []


def test_early_close_uses_supplied_timestamp(dataset):
    filing = dataset.replay_filings()[0].model_copy(
        update={
            "available_at": datetime(2024, 9, 5, 18, tzinfo=UTC),
        }
    )
    dataset.prices = [
        p.model_copy(update={"session_close": datetime(2024, 9, 5, 17, tzinfo=UTC)})
        if p.date == date(2024, 9, 5)
        else p
        for p in dataset.prices
    ]
    assert dataset.effective_session(filing) == date(2024, 9, 6)


def test_naive_source_timestamp_rejected(dataset):
    data = dataset.documents[0].model_dump()
    data["available_at"] = "2024-03-01T15:00:00"
    with pytest.raises(ValueError, match="timezone"):
        Document.model_validate(data)


def test_paths_cannot_escape_corpus(tmp_path):
    with pytest.raises(ValueError, match="escapes"):
        local_file(tmp_path, "../outside.html")


def test_source_tampering_is_detected(tmp_path):
    shutil.copytree(DEMO, tmp_path / "corpus")
    (tmp_path / "corpus/documents/annual.html").write_text("changed")
    with pytest.raises(ValueError, match="checksum"):
        Dataset(tmp_path / "corpus")


def test_cache_reproduces_outputs_without_calling_provider(dataset, tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    run_replay(dataset, "extractive-preview", first)

    def forbidden(*args, **kwargs):
        pytest.fail("Cache replay attempted generation")

    monkeypatch.setattr("net_new.pipeline.preview_prediction", forbidden)
    monkeypatch.setattr("net_new.pipeline.fresh_prediction", forbidden)
    metadata = run_replay(dataset, "cache", second, cache=first)
    original, cached = load_records(first), load_records(second)
    assert metadata["status"] == "completed"
    assert [r["prediction"] for r in original] == [r["prediction"] for r in cached]
    assert all(r["cache_hit"] for r in cached)


def test_missing_cache_is_error_not_empty_success(dataset, tmp_path):
    first = tmp_path / "first"
    run_replay(dataset, "extractive-preview", first)
    records = load_records(first)
    (first / "records.jsonl").write_text("\n".join(json.dumps(r) for r in records[1:]))
    with pytest.raises(ValueError, match="Missing or stale"):
        run_replay(dataset, "cache", tmp_path / "missing", cache=first)
    assert json.loads((tmp_path / "missing/run.json").read_text())["status"] == "failed"


def test_changed_dataset_rejects_cache(dataset, tmp_path):
    first = tmp_path / "first"
    run_replay(dataset, "extractive-preview", first)
    dataset.manifest.description = "A different dataset revision"
    with pytest.raises(ValueError, match="does not match"):
        run_replay(dataset, "cache", tmp_path / "stale", cache=first)


def test_failed_model_calls_are_preserved_and_later_filings_continue(
    dataset, tmp_path, monkeypatch
):
    calls = []

    def fails_once(context):
        from net_new.pipeline import Prediction

        calls.append(context["filing_id"])
        if len(calls) == 1:
            raise RuntimeError("example error body must not be persisted")
        return Prediction(findings=[], limitations="Test fixture")

    monkeypatch.setattr("net_new.pipeline.preview_prediction", fails_once)
    meta = run_replay(dataset, "extractive-preview", tmp_path / "run")
    records = load_records(tmp_path / "run")
    assert meta["status"] == "completed_with_errors" and meta["errors"] == 1
    assert len(records) == len(dataset.replay_filings())
    assert records[0]["status"] == "error" and records[0]["prediction"] is None
    assert records[-1]["status"] == "completed"
    assert "example error body" not in (tmp_path / "run/records.jsonl").read_text()
    assert "guidance" in records[1]["input"]["eligible_history_document_ids"]
