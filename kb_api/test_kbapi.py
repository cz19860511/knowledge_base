import json
import io
import os
import sys
import urllib.error
import urllib.request


BASE = "http://127.0.0.1:9091"
API_KEY = os.getenv("KB_API_KEY", "change-me")

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def request_json(method, path, payload=None):
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
    global BASE
    if len(sys.argv) > 1:
        BASE = sys.argv[1]

    status, body = request_json("GET", "/health")
    print("__HEALTH__")
    print(status)
    print(body)

    status, body = request_json("GET", "/knowledge-bases")
    print("__KB_LIST__")
    print(status)
    print(body)

    payload = {
        "knowledge_base_ids": ["ai_qna_standard_v1"],
        "query": "安全生产责任制的主要要求是什么",
        "method": "doc",
        "offset": 0,
        "limit": 3,
        "top_k": 3,
        "search_threshold": 0.12,
        "extra_params": [],
    }
    status, body = request_json("POST", "/knowledge-bases/retrieve", payload=payload)
    print("__RETRIEVE__")
    print(status)
    print(body)


if __name__ == "__main__":
    main()
