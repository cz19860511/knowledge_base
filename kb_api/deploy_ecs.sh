#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 4 ]]; then
  echo "Usage: $0 <user> <host> <remote_dir> <ecs_data_dir> [ssh_port]"
  echo "Example: $0 root 1.2.3.4 /opt/kb-app /data/kb"
  exit 1
fi

USER_NAME="$1"
HOST="$2"
REMOTE_DIR="$3"
DATA_DIR="$4"
SSH_PORT="${5:-22}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "[1/4] Sync code..."
rsync -avz -e "ssh -p ${SSH_PORT}" \
  --exclude '__pycache__' \
  --exclude '.DS_Store' \
  --exclude 'raw' \
  --exclude 'working' \
  --exclude 'tmp' \
  --exclude 'outputs' \
  --exclude '.venv_kb' \
  "${PROJECT_ROOT}/kb_api" \
  "${PROJECT_ROOT}/requirements-kb-api.txt" \
  "${PROJECT_ROOT}/kb_api/nginx.conf" \
  "${USER_NAME}@${HOST}:${REMOTE_DIR}/"

echo "[2/4] Sync runtime data..."
rsync -avz -e "ssh -p ${SSH_PORT}" \
  --exclude '.DS_Store' \
  "${PROJECT_ROOT}/chunks/" \
  "${PROJECT_ROOT}/vectors/" \
  "${PROJECT_ROOT}/rag/" \
  "${PROJECT_ROOT}/selected/" \
  "${USER_NAME}@${HOST}:${DATA_DIR}/"

echo "[3/4] Sync deployment docs..."
rsync -avz -e "ssh -p ${SSH_PORT}" \
  "${PROJECT_ROOT}/docs/目录说明.md" \
  "${PROJECT_ROOT}/docs/阿里云ECS部署迁移清单.md" \
  "${USER_NAME}@${HOST}:${REMOTE_DIR}/docs/"

echo "[4/4] Done."
echo "Remote code: ${REMOTE_DIR}"
echo "Remote data: ${DATA_DIR}"
