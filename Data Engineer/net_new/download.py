"""Download another company's corpus using the supplied collectors."""

import json
from datetime import date
from pathlib import Path

from authoring.fetch_sec import SEC, collect
from authoring.import_prices import attach

from .dataset import Dataset


def download(
    tickers: list[str],
    start: date,
    end: date,
    output: Path,
    agent: str,
    price_cache: Path,
    price_version: int,
) -> dict:
    if start > end:
        raise ValueError("Start date must be on or before end date")
    if not agent:
        raise ValueError("Set SEC_USER_AGENT to your organization and contact email")
    requested = sorted({t.strip().upper() for t in tickers if t.strip()})
    if not requested:
        raise ValueError("Specify at least one ticker")
    if not (output / "manifest.json").exists():
        sec = SEC(agent)
        catalog = json.loads(sec.get("https://www.sec.gov/files/company_tickers.json"))
        lookup = {r["ticker"].upper(): str(r["cik_str"]) for r in catalog.values()}
        unknown = set(requested) - lookup.keys()
        if unknown:
            raise ValueError("Unknown SEC tickers: " + ", ".join(sorted(unknown)))
        collect(output, {t: lookup[t] for t in requested}, start, end, agent)
    dataset = Dataset(output)
    if (
        dataset.tickers != requested
        or dataset.manifest.replay_start != start
        or dataset.manifest.replay_end != end
    ):
        raise ValueError("Output contains a different company/date selection; use a new directory")
    if not dataset.replay_filings():
        raise ValueError("No 8-K filings in this period; choose a wider date range")
    if not dataset.manifest.prices:
        attach(output, price_cache, price_version)
    return {
        "dataset": str(output.resolve()),
        "companies": requested,
        "replay_filings": len(dataset.replay_filings()),
    }
