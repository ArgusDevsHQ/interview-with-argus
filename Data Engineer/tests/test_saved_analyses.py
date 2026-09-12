import json
import shutil
from pathlib import Path

from net_new.dataset import Dataset
from saved_analyses import discover_analyses

DEMO = Path(__file__).resolve().parents[1] / "data/demo"


def test_discovery_distinguishes_preview_and_model_results_and_filters_scope(tmp_path):
    dataset = Dataset(DEMO)
    runs = tmp_path / "runs"
    for name in ["model", "other-dataset", "other-company", "incomplete"]:
        shutil.copytree(DEMO / "cache", runs / name)
        path = runs / name / "run.json"
        metadata = json.loads(path.read_text())
        metadata["config"].update(provider="openai", model="test-model")
        if name == "other-dataset":
            metadata["dataset_fingerprint"] = "different"
        path.write_text(json.dumps(metadata))
        if name == "other-company":
            rows = [
                json.loads(line)
                for line in (runs / name / "records.jsonl").read_text().splitlines()
            ]
            for row in rows:
                row["ticker"] = "OTHER"
            (runs / name / "records.jsonl").write_text("\n".join(map(json.dumps, rows)))
        if name == "incomplete":
            path.write_text("{")
    results = discover_analyses(dataset, dataset.tickers[0], runs)
    assert [a.path.name for a in results] == ["cache", "model"]
    assert results[0].name == "Supplied preview"
    assert results[0].preview
    assert results[1].name.startswith("Model analysis ·")
    assert not results[1].preview
    assert len(results[1].records) == 4


def test_investor_loader_rejects_authored_references(tmp_path):
    import pytest

    from saved_analyses import load_supplied_analysis

    shutil.copytree(DEMO, tmp_path / "corpus")
    dataset = Dataset(tmp_path / "corpus")
    path = dataset.root / "cache/run.json"
    metadata = json.loads(path.read_text())
    metadata["config"]["provider"] = "supplied-analysis"
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="Authored references"):
        load_supplied_analysis(dataset, dataset.tickers[0])
