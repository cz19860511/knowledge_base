from __future__ import annotations

import argparse
from pathlib import Path

from kb_api.replay import write_replay_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-dir", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--knowledge-base-id", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    root_dir = Path(args.root_dir) if args.root_dir else Path("/Users/chenzhuo/hb/knowledge_base")
    output_path = Path(args.output) if args.output else None
    path = write_replay_report(
        root_dir,
        event_date=args.date,
        knowledge_base_id=args.knowledge_base_id,
        output_path=output_path,
    )
    print(path)


if __name__ == "__main__":
    main()
