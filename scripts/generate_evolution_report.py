from __future__ import annotations

import argparse
from pathlib import Path

from kb_api.config import settings
from kb_api.evolution import write_evolution_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate platform self-evolution suggestion report.")
    parser.add_argument("--date", default=None, help="Target date in YYYY-MM-DD format.")
    parser.add_argument("--knowledge-base-id", default=None, help="Optional knowledge base filter.")
    parser.add_argument("--output", default=None, help="Optional output path.")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else None
    result = write_evolution_report(
        settings.root_dir,
        event_date=args.date,
        knowledge_base_id=args.knowledge_base_id,
        output_path=output_path,
    )
    print(result)


if __name__ == "__main__":
    main()
