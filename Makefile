PYTHON ?= python3
KB_ROOT_DIR ?= $(CURDIR)
KB_API_KEY ?= change-me
QUERY ?= 安全生产责任制的主要要求是什么

.PHONY: check build-hybrid search test-api

check:
	$(PYTHON) -m py_compile \
		embedding_service/config.py \
		embedding_service/main.py \
		embedding_service/model.py \
		embedding_service/schemas.py \
		kb_api/config.py \
		kb_api/main.py \
		kb_api/rag.py \
		kb_api/raw_store.py \
		kb_api/schemas.py \
		scripts/build_hybrid_vectors.py \
		scripts/build_selected_and_chunks.py \
		scripts/build_vectors.py \
		scripts/preprocess_raw_02_07.py \
		scripts/rag_answer.py \
		scripts/search_hybrid_vectors.py \
		scripts/search_vectors.py

build-hybrid:
	$(PYTHON) scripts/build_hybrid_vectors.py

search:
	KB_ROOT_DIR=$(KB_ROOT_DIR) $(PYTHON) scripts/search_hybrid_vectors.py "$(QUERY)" --topk 3

test-api:
	KB_ROOT_DIR=$(KB_ROOT_DIR) KB_API_KEY=$(KB_API_KEY) $(PYTHON) -c "from fastapi.testclient import TestClient; from kb_api.main import app; c=TestClient(app); h={'Authorization':'Bearer $(KB_API_KEY)'}; print(c.get('/health', headers=h).json())"
