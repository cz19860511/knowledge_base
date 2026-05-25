from __future__ import annotations

import argparse

from kb_api.config import settings
from kb_api.daily_memory import ingest_daily_report_to_memory


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest daily report into platform memory knowledge base.")
    parser.add_argument("--date", default=None, help="Report date in YYYY-MM-DD format.")
    args = parser.parse_args()

    payload = ingest_daily_report_to_memory(settings.root_dir, event_date=args.date, save_report=True)
    print(payload["report_path"])
    print(payload["chunks_path"])
    print(payload["vectors_root"])


if __name__ == "__main__":
    main()
