"""Download a bounded, timestamped SEC corpus once, outside the candidate task."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

NY = ZoneInfo("America/New_York")
FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "8-K/A"}


class SEC:
    def __init__(self, agent: str):
        self.client = httpx.Client(
            headers={"User-Agent": agent, "Accept-Encoding": "identity"},
            timeout=40,
            follow_redirects=True,
        )
        self.last_request = 0.0

    def get(self, url: str, path: Path | None = None) -> bytes:
        if path and path.exists():
            return path.read_bytes()
        for attempt in range(4):
            time.sleep(max(0, 0.2 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            response = self.client.get(url)
            if response.status_code in {429, 500, 502, 503, 504}:
                time.sleep(2**attempt)
                continue
            response.raise_for_status()
            if path:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(response.content)
            return response.content
        raise RuntimeError(f"SEC request failed after retries: {url}")


def rows(columns: dict) -> list[dict]:
    return [dict(zip(columns, values)) for values in zip(*columns.values())]


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("SEC acceptance timestamp lacks timezone")
    return parsed.astimezone(UTC)


def collect(root: Path, companies: dict[str, str], start: date, end: date, agent: str) -> None:
    if (root / "manifest.json").exists():
        raise ValueError("Corpus already has a manifest; use a new output directory")
    sec = SEC(agent)
    documents, assets, coverage = [], [], []
    root.mkdir(parents=True, exist_ok=True)
    for ticker, cik in companies.items():
        metadata_url = f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
        info = json.loads(sec.get(metadata_url, root / "metadata" / f"{ticker}.json"))
        filings = rows(info["filings"]["recent"])
        for archive in info["filings"]["files"]:
            if (
                archive["filingFrom"] <= end.isoformat()
                and archive["filingTo"] >= (start - timedelta(days=800)).isoformat()
            ):
                columns = json.loads(
                    sec.get(
                        "https://data.sec.gov/submissions/" + archive["name"],
                        root / "metadata" / archive["name"],
                    )
                )
                filings.extend(rows(columns))
        unique = {f["accessionNumber"]: f for f in filings if f["form"] in FORMS}
        filings = sorted(unique.values(), key=lambda f: f["acceptanceDateTime"])
        annuals = [
            f
            for f in filings
            if f["form"] == "10-K"
            and timestamp(f["acceptanceDateTime"]).astimezone(NY).date() < start
        ]
        if not annuals:
            raise ValueError(f"No pre-replay annual report found for {ticker}")
        baseline_at = timestamp(annuals[-1]["acceptanceDateTime"])
        selected = [
            f
            for f in filings
            if baseline_at <= timestamp(f["acceptanceDateTime"])
            and timestamp(f["acceptanceDateTime"]).astimezone(NY).date() <= end
        ]
        coverage.append(
            {
                "ticker": ticker,
                "cik": cik,
                "baseline_at": baseline_at.isoformat(),
                "end": end.isoformat(),
                "forms": sorted(FORMS),
                "filings": len(selected),
            }
        )
        for filing in selected:
            accession = filing["accessionNumber"]
            base = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"
            )
            folder = root / "documents" / ticker / accession
            index_url = base + accession + "-index.html"
            index = BeautifulSoup(sec.get(index_url, folder / "filing-index.html"), "html.parser")
            table = index.find("table", class_="tableFile")
            attachments = {filing["primaryDocument"]: ("primary", filing["form"])}
            if table:
                for tr in table.find_all("tr"):
                    cells = tr.find_all("td")
                    if len(cells) < 4 or not cells[2].find("a"):
                        continue
                    kind = cells[3].get_text(strip=True)
                    if not kind.startswith("EX-"):
                        continue
                    href = cells[2].find("a")["href"]
                    name = Path(urlparse(href).path).name
                    attachments[name] = ("exhibit", kind)
            for name, (role, kind) in attachments.items():
                source_url = base + name
                payload = sec.get(source_url, folder / name)
                doc_id = f"{ticker}:{accession}:{name}"
                path = (folder / name).relative_to(root).as_posix()
                sha = hashlib.sha256(payload).hexdigest()
                if Path(name).suffix.lower() not in {".html", ".htm"}:
                    assets.append(
                        {
                            "filing_id": accession,
                            "source_url": source_url,
                            "path": path,
                            "sha256": sha,
                            "type": kind,
                        }
                    )
                    continue
                documents.append(
                    {
                        "id": doc_id,
                        "filing_id": accession,
                        "ticker": ticker,
                        "company": info["name"],
                        "form": filing["form"],
                        "role": role,
                        "available_at": timestamp(filing["acceptanceDateTime"]).isoformat(),
                        "path": path,
                        "source_url": source_url,
                        "sha256": sha,
                    }
                )
                soup = BeautifulSoup(payload, "html.parser")
                for image in soup.find_all("img", src=True):
                    asset_url = urljoin(source_url, image["src"])
                    # Retain externally referenced assets as explicitly unresolved entries.
                    if not asset_url.startswith(base):
                        assets.append(
                            {
                                "document_id": doc_id,
                                "source_url": asset_url,
                                "status": "external_asset_not_downloaded",
                            }
                        )
                        continue
                    asset_name = Path(urlparse(asset_url).path).name
                    try:
                        data = sec.get(asset_url, folder / asset_name)
                        assets.append(
                            {
                                "document_id": doc_id,
                                "source_url": asset_url,
                                "path": (folder / asset_name).relative_to(root).as_posix(),
                                "sha256": hashlib.sha256(data).hexdigest(),
                                "status": "downloaded",
                            }
                        )
                    except httpx.HTTPStatusError as exc:
                        assets.append(
                            {
                                "document_id": doc_id,
                                "source_url": asset_url,
                                "status": f"http_{exc.response.status_code}",
                            }
                        )
            print(f"{ticker} {filing['form']} {filing['filingDate']} {accession}", flush=True)
    manifest = {
        "schema_version": 1,
        "dataset_id": f"sec-pilot-{start}-{end}",
        "title": "SEC historical pilot · " + ", ".join(companies),
        "kind": "historical",
        "description": "SEC source corpus. Price data, real model cache, and reviewed labels pending.",
        "replay_start": str(start),
        "replay_end": str(end),
        "documents": documents,
        "prices": None,
        "default_run": None,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (root / "assets.json").write_text(json.dumps(assets, indent=2))
    (root / "coverage.json").write_text(
        json.dumps(
            {
                "collected_at": datetime.now(UTC).isoformat(),
                "companies": coverage,
                "source": "SEC EDGAR",
                "metadata_snapshots": "metadata/",
                "limitations": "No external news; baseline begins at the selected annual report. "
                "Source timestamps are SEC acceptance times, not issuer press-release times.",
            },
            indent=2,
        )
    )
    print(f"Saved {len(documents)} HTML documents to {root}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/sec-pilot"))
    parser.add_argument("--start", type=date.fromisoformat, default=date(2024, 11, 15))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2024, 12, 31))
    parser.add_argument("--company", action="append", help="TICKER:CIK; repeat for each company")
    args = parser.parse_args()
    agent = os.getenv("SEC_USER_AGENT")
    if not agent:
        parser.error("Set SEC_USER_AGENT to your organization and contact email")
    companies = (
        dict(c.split(":", 1) for c in args.company)
        if args.company
        else {
            "SRFM": "1936224",
            "NCPL": "1414767",
        }
    )
    collect(args.output, companies, args.start, args.end, agent)


if __name__ == "__main__":
    main()
