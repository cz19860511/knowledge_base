from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
import urllib.request


BASE = os.getenv("KB_API_BASE", "http://127.0.0.1:9091")
API_KEY = os.getenv("KB_API_KEY", "change-me")

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def request_json(method: str, path: str, payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {API_KEY}")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def main():
    checks = []

    checks.append(("HEALTH", request_json("GET", "/health")))
    checks.append(("KB_LIST", request_json("GET", "/knowledge-bases")))

    explicit_payload = {
        "knowledge_base_id": "ai_qna_standard_v1",
        "query": "服务区危化品车辆现场处理流程是什么",
        "method": "doc",
        "offset": 0,
        "limit": 3,
        "top_k": 3,
        "search_threshold": 0.0,
        "extra_params": [],
    }
    checks.append(("RETRIEVE_EXPLICIT", request_json("POST", "/knowledge-bases/retrieve", payload=explicit_payload)))

    legacy_payload = {
        "knowledge_base_ids": ["ai_qna_standard_v1"],
        "query": "服务区危化品车辆现场处理流程是什么",
        "method": "doc",
        "offset": 0,
        "limit": 3,
        "top_k": 3,
        "search_threshold": 0.0,
        "extra_params": [],
    }
    checks.append(("RETRIEVE_LEGACY", request_json("POST", "/knowledge-bases/retrieve", payload=legacy_payload)))

    for name, (status, body) in checks:
        print(f"__{name}__")
        print(status)
        print(body)


if __name__ == "__main__":
    main()
