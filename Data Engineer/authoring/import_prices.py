"""Attach a small price slice from a versioned, CC0-declared public dataset."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import exchange_calendars as xcals
import httpx
import pandas as pd

from net_new.dataset import Dataset

SOURCE = "https://www.kaggle.com/datasets/andrewmvd/sp-500-stocks"
METADATA = "https://www.kaggle.com/api/v1/datasets/view/andrewmvd/sp-500-stocks"


def attach(root: Path, cache: Path, version: int) -> dict:
    dataset = Dataset(root)
    if dataset.manifest.kind != "historical":
        raise ValueError("Market prices require a historical corpus")
    if dataset.manifest.prices:
        raise ValueError("Corpus already contains prices; create a new corpus revision")
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / f"sp500-v{version}.zip"
    snapshot = cache / "metadata.json"
    if not snapshot.exists():
        response = httpx.get(METADATA, timeout=30, follow_redirects=True)
        response.raise_for_status()
        snapshot.write_bytes(response.content)
    info = json.loads(snapshot.read_text())
    if info.get("licenseName") != "CC0: Public Domain":
        raise ValueError("Source license declaration changed; review before importing")
    url = (
        "https://www.kaggle.com/api/v1/datasets/download/andrewmvd/sp-500-stocks"
        f"?datasetVersionNumber={version}"
    )
    if not archive.exists():
        temporary = archive.with_suffix(".partial")
        with httpx.stream("GET", url, follow_redirects=True, timeout=90) as response:
            response.raise_for_status()
            with temporary.open("wb") as stream:
                for chunk in response.iter_bytes():
                    stream.write(chunk)
        temporary.replace(archive)
    calendar = xcals.get_calendar("XNYS")
    first = calendar.previous_session(
        calendar.date_to_session(str(dataset.manifest.replay_start), direction="next")
    )
    last = calendar.next_session(
        calendar.date_to_session(str(dataset.manifest.replay_end), direction="previous")
    )
    schedule = calendar.schedule.loc[first:last]
    parts = []
    with zipfile.ZipFile(archive) as source, source.open("sp500_stocks.csv") as stream:
        for chunk in pd.read_csv(io.TextIOWrapper(stream), chunksize=100_000):
            selected = chunk.loc[
                chunk.Symbol.isin(dataset.tickers)
                & chunk.Date.between(str(first.date()), str(last.date()))
            ]
            if not selected.empty:
                parts.append(selected)
    if not parts:
        raise ValueError("No matching tickers/dates in the public dataset")
    prices = pd.concat(parts).sort_values(["Symbol", "Date"])
    expected = {str(day.date()) for day in schedule.index}
    for ticker in dataset.tickers:
        rows = prices.loc[prices.Symbol == ticker]
        if set(rows.Date) != expected or rows.Date.duplicated().any():
            missing = sorted(expected - set(rows.Date))
            raise ValueError(f"Incomplete daily prices for {ticker}; missing sessions: {missing}")
        if rows["Adj Close"].isna().any() or (rows["Adj Close"] <= 0).any():
            raise ValueError(f"Missing or invalid adjusted closes for {ticker}")
    raw_path = root / "prices-source-slice.csv"
    prices.to_csv(raw_path, index=False)
    normalized = pd.DataFrame(
        {
            "ticker": prices.Symbol,
            "date": prices.Date,
            "close": prices["Adj Close"],
            "session_close": [schedule.loc[day, "close"].isoformat() for day in prices.Date],
        }
    )
    normalized.to_csv(root / "prices.csv", index=False)
    price_info = {
        "path": "prices.csv",
        "source": f"Kaggle · AndrewMVD S&P 500 Stocks v{version}",
        "source_url": SOURCE,
        "redistribution_basis": "Dataset publisher declares CC0: Public Domain; "
        "declaration preserved in prices-provenance.json.",
        "adjustment": "Source Adj Close field; retrospective adjusted prices. "
        "Not a point-in-time total-return or abnormal-return series.",
        "currency": "USD",
        "kind": "market",
    }
    provenance = {
        "source": SOURCE,
        "download_url": url,
        "dataset_version": version,
        "declared_license": info["licenseName"],
        "publisher": "AndrewMVD",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "slice_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "prices_sha256": hashlib.sha256((root / "prices.csv").read_bytes()).hexdigest(),
        "calendar": "exchange_calendars XNYS; regular US equity sessions including early closes",
        "calendar_version": xcals.__version__,
        "metadata_snapshot": info,
        "limitations": "The public snapshot's adjustment formula and upstream collection "
        "are not fully documented. Selected companies are a convenience sample. "
        "Do not infer point-in-time S&P membership or causal stock returns. "
        "This records the publisher's license declaration, not an independent legal opinion.",
    }
    (root / "prices-provenance.json").write_text(json.dumps(provenance, indent=2))
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["prices"] = price_info
    manifest["description"] = (
        "SEC filings with a public historical adjusted-price slice. "
        "Actual model-run cache and reviewed example labels remain pending."
    )
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2))
    Dataset(root)
    return {
        "rows": len(normalized),
        "tickers": dataset.tickers,
        "version": version,
        "first": str(first.date()),
        "last": str(last.date()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path("data/prices-source"))
    parser.add_argument("--version", type=int, default=1000)
    args = parser.parse_args()
    print(json.dumps(attach(args.dataset, args.cache, args.version), indent=2))


if __name__ == "__main__":
    main()
