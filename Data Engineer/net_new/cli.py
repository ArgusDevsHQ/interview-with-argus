from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from .dataset import Dataset
from .pipeline import run_replay


def main() -> None:
    parser = argparse.ArgumentParser(description="Run and inspect the supplied disclosure workflow")
    commands = parser.add_subparsers(dest="command", required=True)
    status = commands.add_parser("inference-status", help="Show models, allowance and expiry")
    status.add_argument("--json", action="store_true")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--dataset", type=Path, required=True)
    download = commands.add_parser(
        "download", help="Download filings and daily prices for other companies"
    )
    download.add_argument("--ticker", action="append", required=True)
    download.add_argument("--start", type=date.fromisoformat, required=True)
    download.add_argument("--end", type=date.fromisoformat, required=True)
    download.add_argument("--output", type=Path, required=True)
    download.add_argument("--price-cache", type=Path, default=Path("data/prices-source"))
    download.add_argument("--price-version", type=int, default=1000)
    replay = commands.add_parser("replay")
    replay.add_argument("--dataset", type=Path, required=True)
    replay.add_argument(
        "--provider", choices=["cache", "litellm", "openai", "extractive-preview"], required=True
    )
    replay.add_argument("--cache", type=Path)
    replay.add_argument("--output", type=Path)
    replay.add_argument("--ticker")
    replay.add_argument("--model", help="Model alias; defaults to ARGUS_MODEL")
    replay.add_argument(
        "--activate", action="store_true", help="Use a complete model run in the investor app"
    )
    args = parser.parse_args()
    try:
        if args.command == "inference-status":
            from .inference_status import account_status

            info = account_status()
            if args.json:
                print(json.dumps(info, indent=2))
            else:
                print(
                    f"Allowance: ${info['budget_usd']:.2f}; recorded spend: ${info['spent_usd']:.2f}"
                )
                print(
                    f"Estimated remaining: ${info['available_usd']:.2f}; expires: {info['expires_at']}"
                )
                print("Models: " + ", ".join(info["models"]))
                print(info.get("accounting_note", "Recorded spend may lag in-flight requests."))
            return
        if args.command == "download":
            from .download import download as download_corpus

            print(
                json.dumps(
                    download_corpus(
                        args.ticker,
                        args.start,
                        args.end,
                        args.output,
                        os.getenv("SEC_USER_AGENT", ""),
                        args.price_cache,
                        args.price_version,
                    ),
                    indent=2,
                )
            )
            return
        dataset = Dataset(args.dataset)
        if args.command == "inspect":
            print(
                json.dumps(
                    {
                        "dataset": dataset.manifest.title,
                        "kind": dataset.manifest.kind,
                        "fingerprint": dataset.fingerprint,
                        "documents": len(dataset.documents),
                        "price_sessions": len(dataset.prices),
                        "companies": {
                            ticker: {
                                "documents": sum(d.ticker == ticker for d in dataset.documents),
                                "replay_filings": len(dataset.replay_filings(ticker)),
                            }
                            for ticker in dataset.tickers
                        },
                    },
                    indent=2,
                )
            )
        else:
            output = args.output or (dataset.root / "runs" if args.activate else Path("runs")) / (
                datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
            )
            if args.activate:
                if args.ticker or args.provider == "extractive-preview":
                    raise ValueError(
                        "Activation requires a full model run; omit --ticker and use litellm, openai or their cache"
                    )
                if not output.resolve().is_relative_to(dataset.root.resolve()):
                    raise ValueError("With --activate, output must be inside the dataset directory")
            metadata = run_replay(
                dataset, args.provider, output, args.cache, args.ticker, model=args.model
            )
            if args.activate and not metadata["errors"]:
                from .activation import activate

                activate(dataset, output)
            print(
                json.dumps(
                    {
                        "output": str(output.resolve()),
                        "status": metadata["status"],
                        "errors": metadata["errors"],
                    },
                    indent=2,
                )
            )
            if metadata["errors"]:
                from .pipeline import load_records

                for record in load_records(output):
                    if record.get("error_message"):
                        print(f"{record['filing_id']}: {record['error_message']}")
                raise SystemExit(1)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
