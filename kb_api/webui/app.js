const PAGE = document.body?.dataset?.page || "home";

const state = {
  health: null,
  apiKey: localStorage.getItem("kb_api_key") || "",
  rawFolders: [],
  rawFiles: [],
  rawPipeline: null,
  rawExpandedHistory: new Set(),
  pipelineConfig: null,
};

const $ = (id) => document.getElementById(id);

function el(id) {
  return $(id);
}

function setText(id, value) {
  const node = el(id);
  if (node) {
    node.textContent = value;
  }
}

function setHtml(id, value) {
  const node = el(id);
  if (node) {
    node.innerHTML = value;
  }
}

function setDisabled(id, value) {
  const node = el(id);
  if (node) {
    node.disabled = value;
  }
}

function setHealthPill(status) {
  const pill = el("health-pill");
  if (!pill) {
    return;
  }
  pill.textContent = status;
  pill.classList.remove("ok", "warn");
  pill.classList.add(status === "ok" ? "ok" : "warn");
}

function renderHealth(data) {
  setText("kb-id", data.knowledge_base_id || "-");
  setText("batch-id", data.batch_id || "-");
  setText("retrieval-mode", data.retrieval_mode || "-");
  setText("embed-model", data.embedding_model || "bge-small-zh-v1.5");
  setHealthPill(data.status || "warn");
}

function formatScore(score) {
  return Number(score || 0).toFixed(4);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(size >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function formatTime(value) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return value;
  }
}

function splitList(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  if (typeof value === "string") {
    return value
      .split(/[,\n]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}

function joinList(value) {
  return splitList(value).join(", ");
}

function setInputValue(id, value) {
  const node = el(id);
  if (node) {
    node.value = value ?? "";
  }
}

function setCheckboxValue(id, value) {
  const node = el(id);
  if (node) {
    node.checked = Boolean(value);
  }
}

function getCheckboxValue(id) {
  const node = el(id);
  return Boolean(node?.checked);
}

async function fetchJson(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(url, { ...options, headers });
  const text = await res.text();

  let payload;
  try {
    payload = text ? JSON.parse(text) : {};
  } catch (error) {
    throw new Error(`JSON parse failed: ${error.message}`);
  }

  if (!res.ok) {
    throw new Error(payload?.detail || payload?.message || res.statusText);
  }
  return payload;
}

function requireApiKey() {
  if (!state.apiKey) {
    alert("先输入 API Key 再操作。");
    return false;
  }
  return true;
}

function renderKnowledgeBases(items) {
  const body = el("kb-table");
  if (!body) return;
  if (!items.length) {
    body.innerHTML = '<tr><td colspan="4" class="placeholder">没有加载到知识库数据</td></tr>';
    return;
  }

  body.innerHTML = items
    .map(
      (item) => `
        <tr>
          <td>
            <strong>${escapeHtml(item.name)}</strong>
            <div class="snippet">${escapeHtml(item.knowledge_base_id)}</div>
          </td>
          <td>${item.doc_count}</td>
          <td>${item.chunk_count}</td>
          <td>${escapeHtml(item.description || "-")}</td>
        </tr>
      `,
    )
    .join("");
}

function renderResults(payload) {
  const rawJson = el("raw-json");
  if (rawJson) {
    rawJson.textContent = JSON.stringify(payload, null, 2);
  }

  const list = el("result-list");
  if (!list) return;

  const items = payload.search_result_list || [];
  if (!items.length) {
    list.innerHTML = '<div class="placeholder">没有命中结果。</div>';
    return;
  }

  list.innerHTML = items
    .map((item, index) => {
      const chips = [item.retrieval_mode, ...(item.matched_rules || []), item.doc_type, item.folder]
        .filter(Boolean)
        .map((value) => `<span class="chip">${escapeHtml(String(value))}</span>`)
        .join("");

      return `
        <article class="result-item">
          <div class="result-top">
            <strong>${index + 1}. ${escapeHtml(item.title || "未命名结果")}</strong>
            <span class="score-badge">${formatScore(item.score)}</span>
          </div>
          <div class="chips">${chips}</div>
          <div class="snippet">${escapeHtml((item.content || "").slice(0, 380))}</div>
        </article>
      `;
    })
    .join("");
}

function renderRawFolderOptions(folders) {
  const select = el("raw-folder");
  if (!select) return;

  const current = select.value || state.rawFolders[0] || "";
  select.innerHTML = folders.map((folder) => `<option value="${escapeHtml(folder)}">${escapeHtml(folder)}</option>`).join("");
  if (folders.includes(current)) {
    select.value = current;
  } else if (folders.length) {
    select.value = folders[0];
  }

  state.rawFolders = folders;
  const selected = select.value || "-";
  setText("raw-folder-count", selected);
  setText("current-folder", selected);
}

function renderRawPipeline(pipeline) {
  state.rawPipeline = pipeline;
  const pill = el("pipeline-pill");
  if (!pill) return;

  const stateText = pipeline?.state || "idle";
  pill.textContent = stateText;
  pill.classList.remove("ok", "warn");
  if (stateText === "success") {
    pill.classList.add("ok");
  } else if (stateText === "failed" || stateText === "running") {
    pill.classList.add("warn");
  }

  const stage = pipeline?.current_stage || pipeline?.current_step || "-";
  const folder = pipeline?.current_folder || "-";
  setText("raw-step", folder && folder !== "-" ? `${stage} / ${folder}` : stage);
  setText("raw-success", formatTime(pipeline?.last_success_at || pipeline?.finished_at));
}

function renderRawFiles(payload) {
  state.rawFiles = payload.raw_file_list || [];
  renderRawFolderOptions(payload.allowed_folders || []);
  setText("raw-total", payload.total ?? state.rawFiles.length);

  const body = el("raw-table");
  if (!body) return;
  if (!state.rawFiles.length) {
    body.innerHTML = '<tr><td colspan="6" class="placeholder">当前目录还没有原始文件</td></tr>';
    return;
  }

  body.innerHTML = state.rawFiles
    .map((item) => {
      const rawKey = item.raw_key || `${item.folder}/${item.file_name}`;
      const isExpanded = state.rawExpandedHistory.has(rawKey);
      const history = (item.history || [])
        .slice(-2)
        .map((record) => `${record.version || "-"} @ ${formatTime(record.uploaded_at)}`)
        .join(" · ");
      const historyRows = (item.history || [])
        .slice()
        .reverse()
        .map((record, index) => {
          const versionLabel = record.version || `v${index + 1}`;
          const meta = [
            record.uploaded_at ? `上传 ${formatTime(record.uploaded_at)}` : null,
            record.size_bytes != null ? `大小 ${formatBytes(record.size_bytes)}` : null,
            record.source_version ? `来自 ${record.source_version}` : null,
            record.restored_from ? `回滚自 ${record.restored_from}` : null,
            record.action ? `动作 ${record.action}` : null,
          ]
            .filter(Boolean)
            .join(" · ");

          return `
            <li class="history-item">
              <div class="history-item-top">
                <strong>${escapeHtml(versionLabel)}</strong>
                <span class="history-chip">${escapeHtml(meta || "-")}</span>
              </div>
              <div class="history-item-sub">
                ${escapeHtml(record.checksum ? `checksum ${record.checksum}` : "checksum -")}
                ${record.stored_path ? ` · ${escapeHtml(record.stored_path)}` : ""}
              </div>
            </li>
          `;
        })
        .join("");

      return `
        <tr>
          <td>
            <strong>${escapeHtml(item.file_name)}</strong>
            <div class="history-text">${escapeHtml(item.folder)}</div>
          </td>
          <td>
            <strong>${escapeHtml(item.version || "v1")}</strong>
            <div class="history-text">共 ${item.version_count || 1} 个版本</div>
          </td>
          <td>
            ${escapeHtml(formatTime(item.upload_time))}
            <div class="history-text">${escapeHtml(history || "-")}</div>
          </td>
          <td>${escapeHtml(formatBytes(item.size_bytes))}</td>
          <td>${item.deleted ? "已删除" : "正常"}</td>
          <td>
            <div class="file-actions">
              <button class="ghost-btn" data-toggle-history="${escapeHtml(rawKey)}">${isExpanded ? "收起历史" : "展开历史"}</button>
              <button class="ghost-btn danger-btn" data-delete-folder="${escapeHtml(item.folder)}" data-delete-file="${escapeHtml(item.file_name)}">删除</button>
              ${Number(item.version_count || 0) > 1 ? `<button class="ghost-btn" data-rollback-folder="${escapeHtml(item.folder)}" data-rollback-file="${escapeHtml(item.file_name)}">回滚上一版</button>` : ""}
            </div>
          </td>
        </tr>
        ${isExpanded ? `
        <tr class="history-row">
          <td colspan="6">
            <div class="history-panel">
              <div class="history-panel-head">版本历史</div>
              <ul class="history-list">
                ${historyRows || '<li class="history-item"><div class="history-item-sub">暂无历史记录</div></li>'}
              </ul>
            </div>
          </td>
        </tr>` : ""}
      `;
    })
    .join("");
}

function renderRawEmpty(message) {
  setHtml("raw-table", `<tr><td colspan="6" class="placeholder">${escapeHtml(message)}</td></tr>`);
  setText("raw-total", "-");
  setText("raw-folder-count", "-");
  setText("current-folder", "-");
  setText("raw-step", "-");
  setText("raw-success", "-");
  const pill = el("pipeline-pill");
  if (pill) {
    pill.textContent = "未加载";
    pill.classList.remove("ok", "warn");
  }
}

function renderPipelineConfig(config) {
  state.pipelineConfig = config;
  const pill = el("config-pill");
  if (pill) {
    pill.textContent = config?.updated_at ? "已加载" : "默认配置";
    pill.classList.remove("ok", "warn");
    pill.classList.add("ok");
  }
  const meta = config?.updated_at ? `已保存 ${formatTime(config.updated_at)}` : "未保存";
  setText("config-save-state", meta);
  setText("config-path", config?.config_path || "-");

  const payload = config?.config || {};
  const preprocess = payload.preprocess || {};
  const chunk = payload.chunk || {};
  const embedding = payload.embedding || {};

  renderFolderCheckboxes("preprocess-folders", preprocess.folders || []);
  renderFolderCheckboxes("chunk-folders", chunk.folders || []);
  setInputValue("preprocess-primary-exts", joinList(preprocess.primary_exts || []));
  setInputValue("preprocess-supplement-exts", joinList(preprocess.supplement_exts || []));
  setCheckboxValue("preprocess-markitdown-docx-enabled", preprocess.markitdown_docx_enabled);
  setInputValue("preprocess-mineru-command", preprocess.mineru_command || "");
  setInputValue("preprocess-mineru-pipeline", preprocess.mineru_pipeline || "");

  setInputValue("chunk-max-chars", chunk.max_chunk_chars ?? "");
  setInputValue("chunk-min-chars", chunk.min_chunk_chars ?? "");
  setInputValue("chunk-mineru-bonus", chunk.mineru_parser_bonus ?? "");

  setInputValue("embedding-provider", embedding.provider || "");
  setInputValue("embedding-model-path", embedding.model_path || "");
  setInputValue("embedding-model-name", embedding.model_name || "");
  setInputValue("embedding-device", embedding.device || "");
  setInputValue("embedding-batch-size", embedding.batch_size ?? "");
  setInputValue("embedding-pooling", embedding.pooling || "");
  setInputValue("embedding-query-instruction", embedding.query_instruction || "");
  setInputValue("embedding-max-length", embedding.max_length ?? "");
  setCheckboxValue("embedding-normalize", embedding.normalize);
}

function renderFolderCheckboxes(containerId, folders) {
  const container = el(containerId);
  if (!container) return;
  const selected = new Set((folders || []).map((item) => String(item)));
  const options = state.rawFolders.length ? state.rawFolders : [
    "02规章制度与标准规范",
    "03SOP流程化资料_疑似",
    "04表单台账与字段说明_疑似",
    "05岗位职责与角色资料",
    "06安全与应急资料",
    "07信息系统与APP操作",
  ];
  container.innerHTML = options
    .map((folder) => {
      const checked = selected.has(folder) ? "checked" : "";
      return `
        <label class="check-pill">
          <input type="checkbox" data-folder-choice="${escapeHtml(containerId)}" value="${escapeHtml(folder)}" ${checked} />
          <span>${escapeHtml(folder)}</span>
        </label>
      `;
    })
    .join("");
}

function collectFolderCheckboxes(containerId) {
  const container = el(containerId);
  if (!container) return [];
  return Array.from(container.querySelectorAll('input[type="checkbox"]:checked')).map((input) => input.value);
}

function buildPipelineConfigPayload() {
  return {
    version: 1,
    preprocess: {
      folders: collectFolderCheckboxes("preprocess-folders"),
      primary_exts: splitList(el("preprocess-primary-exts")?.value || ""),
      supplement_exts: splitList(el("preprocess-supplement-exts")?.value || ""),
      markitdown_docx_enabled: getCheckboxValue("preprocess-markitdown-docx-enabled"),
      mineru_command: (el("preprocess-mineru-command")?.value || "").trim(),
      mineru_pipeline: (el("preprocess-mineru-pipeline")?.value || "").trim(),
    },
    chunk: {
      folders: collectFolderCheckboxes("chunk-folders"),
      max_chunk_chars: Number(el("chunk-max-chars")?.value || 1800),
      min_chunk_chars: Number(el("chunk-min-chars")?.value || 300),
      mineru_parser_bonus: Number(el("chunk-mineru-bonus")?.value || 50),
    },
    embedding: {
      provider: (el("embedding-provider")?.value || "").trim(),
      model_path: (el("embedding-model-path")?.value || "").trim(),
      model_name: (el("embedding-model-name")?.value || "").trim(),
      device: (el("embedding-device")?.value || "").trim(),
      batch_size: Number(el("embedding-batch-size")?.value || 16),
      pooling: (el("embedding-pooling")?.value || "").trim(),
      query_instruction: (el("embedding-query-instruction")?.value || "").trim(),
      max_length: Number(el("embedding-max-length")?.value || 512),
      normalize: getCheckboxValue("embedding-normalize"),
    },
  };
}

async function loadHealth() {
  const pill = el("health-pill");
  if (!pill) return;
  try {
    setHealthPill("检查中");
    const data = await fetchJson("/health");
    state.health = data;
    renderHealth(data);
  } catch (error) {
    setHealthPill("warn");
    const rawJson = el("raw-json");
    if (rawJson) {
      rawJson.textContent = JSON.stringify({ error: error.message }, null, 2);
    }
  }
}

async function loadKnowledgeBases() {
  if (!requireApiKey()) return;
  const body = el("kb-table");
  if (!body) return;

  const data = await fetchJson("/knowledge-bases", {
    headers: { Authorization: `Bearer ${state.apiKey}` },
  });
  renderKnowledgeBases(data.knowledge_base_list || []);
}

async function loadRawFiles(silent = false) {
  const body = el("raw-table");
  if (!body) return;

  if (!state.apiKey) {
    if (!silent) {
      alert("先输入 API Key 再加载原始文件。");
    }
    renderRawEmpty("输入 API Key 后即可加载原始文件列表");
    return;
  }

  const data = await fetchJson("/raw-files", {
    headers: { Authorization: `Bearer ${state.apiKey}` },
  });
  renderRawFiles(data);
}

async function loadRawPipelineStatus(silent = false) {
  const pill = el("pipeline-pill");
  if (!pill) return;

  if (!state.apiKey) {
    if (!silent) {
      alert("先输入 API Key 再查看流水线状态。");
    }
    renderRawPipeline(null);
    return;
  }

  const data = await fetchJson("/raw-files/pipeline", {
    headers: { Authorization: `Bearer ${state.apiKey}` },
  });
  renderRawPipeline(data);
}

async function loadPipelineConfig(silent = false) {
  const pill = el("config-pill");
  if (!pill) return;

  if (!state.apiKey) {
    if (!silent) {
      alert("先输入 API Key 再加载配置。");
    }
    pill.textContent = "未加载";
    pill.classList.remove("ok", "warn");
    setText("config-save-state", "未加载");
    return;
  }

  const data = await fetchJson("/pipeline-config", {
    headers: { Authorization: `Bearer ${state.apiKey}` },
  });
  renderPipelineConfig(data);
}

async function savePipelineConfig() {
  if (!requireApiKey()) return;
  const button = el("save-config");
  if (!button) return;

  const payload = buildPipelineConfigPayload();
  button.disabled = true;
  button.textContent = "保存中...";

  try {
    const data = await fetchJson("/pipeline-config", {
      method: "PUT",
      headers: { Authorization: `Bearer ${state.apiKey}` },
      body: JSON.stringify({ config: payload }),
    });
    renderPipelineConfig(data);
    alert("配置已保存。");
  } catch (error) {
    alert(`保存失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "保存配置";
  }
}

async function runQuery() {
  if (!requireApiKey()) return;
  const runQueryBtn = el("run-query");
  if (!runQueryBtn) return;

  const payload = {
    knowledge_base_ids: [state.health?.knowledge_base_id || "ai_qna_standard_v1"],
    query: (el("query")?.value || "").trim(),
    top_k: Number(el("topk")?.value || 3),
    limit: Number(el("topk")?.value || 3),
    search_threshold: Number(el("threshold")?.value || 0),
  };

  if (!payload.query) {
    alert("请输入查询内容。");
    return;
  }

  runQueryBtn.disabled = true;
  runQueryBtn.textContent = "检索中...";

  try {
    const data = await fetchJson("/knowledge-bases/retrieve", {
      method: "POST",
      headers: { Authorization: `Bearer ${state.apiKey}` },
      body: JSON.stringify(payload),
    });
    renderResults(data);
  } catch (error) {
    const list = el("result-list");
    if (list) {
      list.innerHTML = `<div class="placeholder">检索失败：${escapeHtml(error.message)}</div>`;
    }
    const rawJson = el("raw-json");
    if (rawJson) {
      rawJson.textContent = JSON.stringify({ error: error.message }, null, 2);
    }
  } finally {
    runQueryBtn.disabled = false;
    runQueryBtn.textContent = "执行检索";
  }
}

async function uploadRawFiles() {
  if (!requireApiKey()) return;

  const folder = el("raw-folder")?.value;
  const fileInput = el("raw-files");
  const uploadBtn = el("upload-raw-files");
  if (!folder || !fileInput || !uploadBtn) {
    return;
  }

  const files = Array.from(fileInput.files || []);
  if (!files.length) {
    alert("先选择要上传的文件。");
    return;
  }

  const form = new FormData();
  form.append("folder", folder);
  files.forEach((file) => form.append("files", file));

  uploadBtn.disabled = true;
  uploadBtn.textContent = "上传中...";

  try {
    const result = await fetchJson("/raw-files/upload", {
      method: "POST",
      headers: { Authorization: `Bearer ${state.apiKey}` },
      body: form,
    });
    fileInput.value = "";
    await loadRawFiles(true);
    alert(`上传完成：新增 ${result.created_count || 0} 个，更新 ${result.updated_count || 0} 个。`);
  } catch (error) {
    alert(`上传失败：${error.message}`);
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.textContent = "上传并更新版本";
  }
}

async function deleteRawFile(folder, fileName) {
  if (!requireApiKey()) return;
  const ok = confirm(`确认删除 ${folder}/${fileName} 吗？`);
  if (!ok) return;

  try {
    const result = await fetchJson(`/raw-files?folder=${encodeURIComponent(folder)}&file_name=${encodeURIComponent(fileName)}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    await loadRawFiles(true);
    alert(result.deleted ? "删除完成。" : "文件已从台账中移除。");
  } catch (error) {
    alert(`删除失败：${error.message}`);
  }
}

async function rollbackRawFile(folder, fileName) {
  if (!requireApiKey()) return;
  const ok = confirm(`确认把 ${folder}/${fileName} 回滚到上一版吗？`);
  if (!ok) return;

  try {
    const result = await fetchJson(`/raw-files/rollback?folder=${encodeURIComponent(folder)}&file_name=${encodeURIComponent(fileName)}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    await loadRawFiles(true);
    await loadRawPipelineStatus(true);
    alert(`回滚完成，已恢复 ${result.restored_from_version || "上一版"}。`);
  } catch (error) {
    alert(`回滚失败：${error.message}`);
  }
}

async function runRawStage(stage, buttonId, runningText) {
  if (!requireApiKey()) return;
  const folder = el("raw-folder")?.value;
  if (!folder) {
    alert("先选择一个原始目录。");
    return;
  }

  const button = el(buttonId);
  if (!button) return;

  button.disabled = true;
  button.textContent = runningText;

  try {
    await fetchJson(`/raw-files/pipeline?stage=${encodeURIComponent(stage)}&folder=${encodeURIComponent(folder)}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    await loadRawPipelineStatus(true);
  } catch (error) {
    alert(`${runningText}失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = buttonId === "run-preprocess" ? "预处理" : buttonId === "run-chunk" ? "生成 Chunk" : "生成 Embedding";
  }
}

function bindHomeEvents() {
  el("refresh-health")?.addEventListener("click", loadHealth);
  el("load-kbs")?.addEventListener("click", loadKnowledgeBases);
  el("run-query")?.addEventListener("click", runQuery);
  el("save-key")?.addEventListener("click", async () => {
    state.apiKey = (el("api-key")?.value || "").trim();
    localStorage.setItem("kb_api_key", state.apiKey);
    alert("API Key 已保存到本地浏览器。");
    try {
      await loadKnowledgeBases();
    } catch (error) {
      alert(`加载数据失败：${error.message}`);
    }
  });
  el("clear-key")?.addEventListener("click", () => {
    state.apiKey = "";
    localStorage.removeItem("kb_api_key");
    const apiKeyInput = el("api-key");
    if (apiKeyInput) {
      apiKeyInput.value = "";
    }
    alert("API Key 已清除。");
    const list = el("result-list");
    if (list) {
      list.innerHTML = '<div class="placeholder">执行一次检索后，结果会显示在这里。</div>';
    }
  });
}

function bindRawEvents() {
  el("save-key")?.addEventListener("click", async () => {
    state.apiKey = (el("api-key")?.value || "").trim();
    localStorage.setItem("kb_api_key", state.apiKey);
    alert("API Key 已保存到本地浏览器。");
    try {
      await loadRawFiles(true);
      await loadRawPipelineStatus(true);
    } catch (error) {
      alert(`加载数据失败：${error.message}`);
    }
  });
  el("load-raw-files")?.addEventListener("click", async () => {
    await loadRawFiles();
  });
  el("refresh-raw-files")?.addEventListener("click", async () => {
    await loadRawFiles(true);
    await loadRawPipelineStatus(true);
  });
  el("upload-raw-files")?.addEventListener("click", uploadRawFiles);
  el("run-preprocess")?.addEventListener("click", () => runRawStage("preprocess", "run-preprocess", "预处理"));
  el("run-chunk")?.addEventListener("click", () => runRawStage("chunk", "run-chunk", "生成 Chunk"));
  el("run-embedding")?.addEventListener("click", () => runRawStage("embedding", "run-embedding", "生成 Embedding"));
  el("raw-table")?.addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-toggle-history]");
    if (toggle) {
      const key = toggle.getAttribute("data-toggle-history") || "";
      if (state.rawExpandedHistory.has(key)) {
        state.rawExpandedHistory.delete(key);
      } else {
        state.rawExpandedHistory.add(key);
      }
      renderRawFiles({ total: state.rawFiles.length, allowed_folders: state.rawFolders, raw_file_list: state.rawFiles });
      return;
    }
    const button = event.target.closest("[data-delete-folder]");
    if (!button) return;
    const folder = button.getAttribute("data-delete-folder") || "";
    const fileName = button.getAttribute("data-delete-file") || "";
    deleteRawFile(folder, fileName);
  });
  el("raw-table")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-rollback-folder]");
    if (!button) return;
    const folder = button.getAttribute("data-rollback-folder") || "";
    const fileName = button.getAttribute("data-rollback-file") || "";
    rollbackRawFile(folder, fileName);
  });
}

function bindConfigEvents() {
  el("save-key")?.addEventListener("click", async () => {
    state.apiKey = (el("api-key")?.value || "").trim();
    localStorage.setItem("kb_api_key", state.apiKey);
    alert("API Key 已保存到本地浏览器。");
    try {
      await loadPipelineConfig(true);
    } catch (error) {
      alert(`加载配置失败：${error.message}`);
    }
  });
  el("load-config")?.addEventListener("click", async () => {
    await loadPipelineConfig();
  });
  el("refresh-config")?.addEventListener("click", async () => {
    await loadPipelineConfig(true);
  });
  el("save-config")?.addEventListener("click", savePipelineConfig);
}

async function bootstrap() {
  const apiKeyInput = el("api-key");
  if (apiKeyInput) {
    apiKeyInput.value = state.apiKey;
  }

  if (PAGE === "raw") {
    bindRawEvents();
    await loadRawFiles(true);
    await loadRawPipelineStatus(true);
    return;
  }

  if (PAGE === "config") {
    bindConfigEvents();
    if (state.apiKey) {
      try {
        await loadPipelineConfig(true);
      } catch {
        setText("config-save-state", "加载失败");
      }
    } else {
      setText("config-save-state", "输入 API Key 后可加载");
    }
    return;
  }

  bindHomeEvents();
  await loadHealth();
}

bootstrap();
