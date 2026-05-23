from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(os.getenv("KB_ROOT_DIR", "/Users/chenzhuo/hb/knowledge_base"))
os.environ.setdefault("KB_ROOT_DIR", str(ROOT))
sys.path.insert(0, str(ROOT))

from kb_api.rag import search  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search the local hybrid retrieval index.")
    parser.add_argument("query")
    parser.add_argument("--topk", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=0.12)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    hits = search(args.query, top_k=args.topk, threshold=args.threshold)
    for rank, hit in enumerate(hits, start=1):
        print(f"#{rank} score={hit['score']:.4f} keyword={hit['keyword_score']:.4f} embedding={hit['embedding_score']:.4f}")
        print(f"chunk_id={hit['chunk_id']}")
        print(f"title={hit['title']}")
        print(hit["content"][:240].replace("\n", " "))
        print()


if __name__ == "__main__":
    main()
