const state = {
  health: null,
  apiKey: localStorage.getItem("kb_api_key") || "",
  rawFolders: [],
  rawFiles: [],
  rawPipeline: null,
};

const $ = (id) => document.getElementById(id);

function setHealthPill(status) {
  const pill = $("health-pill");
  pill.textContent = status;
  pill.classList.remove("ok", "warn");
  pill.classList.add(status === "ok" ? "ok" : "warn");
}

function renderHealth(data) {
  $("kb-id").textContent = data.knowledge_base_id || "-";
  $("batch-id").textContent = data.batch_id || "-";
  $("retrieval-mode").textContent = data.retrieval_mode || "-";
  $("embed-model").textContent = data.embedding_model || "bge-small-zh-v1.5";
  setHealthPill(data.status || "warn");
}

function formatScore(score) {
  const value = Number(score || 0);
  return value.toFixed(4);
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
  if (!Number.isFinite(value) || value <= 0) {
    return "-";
  }
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

async function fetchJson(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  const text = await res.text();
  let payload;
  try {
    payload = text ? JSON.parse(text) : {};
  } catch (error) {
    throw new Error(`JSON parse failed: ${error.message}`);
  }

  if (!res.ok) {
    const message = payload?.detail || payload?.message || res.statusText;
    throw new Error(message);
  }

  return payload;
}

function renderKnowledgeBases(items) {
  const body = $("kb-table");
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
  $("raw-json").textContent = JSON.stringify(payload, null, 2);

  const list = $("result-list");
  const items = payload.search_result_list || [];
  if (!items.length) {
    list.innerHTML = '<div class="placeholder">没有命中结果。</div>';
    return;
  }

  list.innerHTML = items
    .map((item, index) => {
      const chips = [
        item.retrieval_mode,
        ...(item.matched_rules || []),
        item.doc_type,
        item.folder,
      ]
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
  const select = $("raw-folder");
  const current = select.value || state.rawFolders[0] || "";
  select.innerHTML = folders
    .map((folder) => `<option value="${escapeHtml(folder)}">${escapeHtml(folder)}</option>`)
    .join("");
  if (folders.includes(current)) {
    select.value = current;
  } else if (folders.length) {
    select.value = folders[0];
  }
  state.rawFolders = folders;
  $("raw-folder-count").textContent = select.value || "-";
}

function renderRawPipeline(pipeline) {
  state.rawPipeline = pipeline;
  const pill = $("pipeline-pill");
  const stateText = pipeline?.state || "idle";
  pill.textContent = stateText;
  pill.classList.remove("ok", "warn");
  if (stateText === "success") {
    pill.classList.add("ok");
  } else if (stateText === "failed" || stateText === "running") {
    pill.classList.add("warn");
  }

  $("raw-step").textContent = pipeline?.current_step || "-";
  $("raw-success").textContent = formatTime(pipeline?.last_success_at || pipeline?.finished_at);
}

function renderRawFiles(payload) {
  state.rawFiles = payload.raw_file_list || [];
  renderRawFolderOptions(payload.allowed_folders || []);
  $("raw-total").textContent = payload.total ?? state.rawFiles.length;

  const body = $("raw-table");
  if (!state.rawFiles.length) {
    body.innerHTML = '<tr><td colspan="6" class="placeholder">当前目录还没有原始文件</td></tr>';
    return;
  }

  body.innerHTML = state.rawFiles
    .map((item) => {
      const history = (item.history || [])
        .slice(-2)
        .map((record) => `${record.version || "-"} @ ${formatTime(record.uploaded_at)}`)
        .join(" · ");

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
              <button
                class="ghost-btn danger-btn"
                data-delete-folder="${escapeHtml(item.folder)}"
                data-delete-file="${escapeHtml(item.file_name)}"
              >
                删除
              </button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

function renderRawEmpty(message) {
  $("raw-table").innerHTML = `<tr><td colspan="6" class="placeholder">${escapeHtml(message)}</td></tr>`;
  $("raw-total").textContent = "-";
  $("raw-folder-count").textContent = "-";
  $("raw-step").textContent = "-";
  $("raw-success").textContent = "-";
  const pill = $("pipeline-pill");
  pill.textContent = "未加载";
  pill.classList.remove("ok", "warn");
}

function requireApiKey() {
  if (!state.apiKey) {
    alert("先输入 API Key 再操作原始文件。");
    return false;
  }
  return true;
}

async function loadHealth() {
  try {
    setHealthPill("检查中");
    const data = await fetchJson("/health");
    state.health = data;
    renderHealth(data);
  } catch (error) {
    setHealthPill("warn");
    $("raw-json").textContent = JSON.stringify({ error: error.message }, null, 2);
  }
}

async function loadKnowledgeBases() {
  if (!requireApiKey()) {
    return;
  }

  const data = await fetchJson("/knowledge-bases", {
    headers: { Authorization: `Bearer ${state.apiKey}` },
  });

  renderKnowledgeBases(data.knowledge_base_list || []);
}

async function loadRawFiles(silent = false) {
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

async function runQuery() {
  if (!requireApiKey()) {
    return;
  }

  const payload = {
    knowledge_base_ids: [state.health?.knowledge_base_id || "ai_qna_standard_v1"],
    query: $("query").value.trim(),
    top_k: Number($("topk").value || 3),
    limit: Number($("topk").value || 3),
    search_threshold: Number($("threshold").value || 0),
  };

  if (!payload.query) {
    alert("请输入查询内容。");
    return;
  }

  $("run-query").disabled = true;
  $("run-query").textContent = "检索中...";

  try {
    const data = await fetchJson("/knowledge-bases/retrieve", {
      method: "POST",
      headers: { Authorization: `Bearer ${state.apiKey}` },
      body: JSON.stringify(payload),
    });
    renderResults(data);
  } catch (error) {
    $("result-list").innerHTML = `<div class="placeholder">检索失败：${escapeHtml(error.message)}</div>`;
    $("raw-json").textContent = JSON.stringify({ error: error.message }, null, 2);
  } finally {
    $("run-query").disabled = false;
    $("run-query").textContent = "执行检索";
  }
}

async function uploadRawFiles() {
  if (!requireApiKey()) {
    return;
  }

  const folder = $("raw-folder").value;
  const fileInput = $("raw-files");
  const files = Array.from(fileInput.files || []);
  if (!folder) {
    alert("先选择目标目录。");
    return;
  }
  if (!files.length) {
    alert("先选择要上传的文件。");
    return;
  }

  const form = new FormData();
  form.append("folder", folder);
  form.append("run_pipeline", $("raw-run-pipeline").checked ? "true" : "false");
  files.forEach((file) => form.append("files", file));

  $("upload-raw-files").disabled = true;
  $("upload-raw-files").textContent = "上传中...";

  try {
    const result = await fetchJson("/raw-files/upload", {
      method: "POST",
      headers: { Authorization: `Bearer ${state.apiKey}` },
      body: form,
    });
    fileInput.value = "";
    await loadRawFiles(true);
    await loadRawPipelineStatus(true);
    alert(`上传完成：新增 ${result.created_count || 0} 个，更新 ${result.updated_count || 0} 个。`);
  } catch (error) {
    alert(`上传失败：${error.message}`);
  } finally {
    $("upload-raw-files").disabled = false;
    $("upload-raw-files").textContent = "上传并更新版本";
  }
}

async function deleteRawFile(folder, fileName) {
  if (!requireApiKey()) {
    return;
  }
  const ok = confirm(`确认删除 ${folder}/${fileName} 吗？删除后会触发后续重建。`);
  if (!ok) {
    return;
  }

  try {
    const result = await fetchJson(`/raw-files?folder=${encodeURIComponent(folder)}&file_name=${encodeURIComponent(fileName)}&run_pipeline=true`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    await loadRawFiles(true);
    await loadRawPipelineStatus(true);
    alert(result.deleted ? "删除完成，已触发重建。" : "文件已从台账中移除，已触发重建。");
  } catch (error) {
    alert(`删除失败：${error.message}`);
  }
}

async function triggerRawPipeline(force = false) {
  if (!requireApiKey()) {
    return;
  }

  $("trigger-pipeline").disabled = true;
  $("trigger-pipeline").textContent = force ? "强制重建中..." : "重建中...";

  try {
    await fetchJson(`/raw-files/pipeline?force=${force ? "true" : "false"}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    await loadRawPipelineStatus(true);
  } catch (error) {
    alert(`重建失败：${error.message}`);
  } finally {
    $("trigger-pipeline").disabled = false;
    $("trigger-pipeline").textContent = "手动重建";
  }
}

function bindEvents() {
  $("refresh-health").addEventListener("click", loadHealth);
  $("load-kbs").addEventListener("click", loadKnowledgeBases);
  $("run-query").addEventListener("click", runQuery);
  $("upload-raw-files").addEventListener("click", uploadRawFiles);
  $("refresh-raw-files").addEventListener("click", async () => {
    await loadRawFiles();
    await loadRawPipelineStatus(true);
  });
  $("trigger-pipeline").addEventListener("click", () => triggerRawPipeline(false));
  $("save-key").addEventListener("click", async () => {
    state.apiKey = $("api-key").value.trim();
    localStorage.setItem("kb_api_key", state.apiKey);
    alert("API Key 已保存到本地浏览器。");
    try {
      await loadRawFiles(true);
      await loadRawPipelineStatus(true);
      await loadKnowledgeBases();
    } catch (error) {
      alert(`加载数据失败：${error.message}`);
    }
  });
  $("clear-key").addEventListener("click", () => {
    state.apiKey = "";
    localStorage.removeItem("kb_api_key");
    $("api-key").value = "";
    alert("API Key 已清除。");
    renderRawEmpty("输入 API Key 后即可加载原始文件列表");
  });
  $("raw-table").addEventListener("click", (event) => {
    const button = event.target.closest("[data-delete-folder]");
    if (!button) {
      return;
    }
    const folder = button.getAttribute("data-delete-folder") || "";
    const fileName = button.getAttribute("data-delete-file") || "";
    deleteRawFile(folder, fileName);
  });
}

async function bootstrap() {
  $("api-key").value = state.apiKey;
  bindEvents();
  await loadHealth();
  await loadRawFiles(true);
  await loadRawPipelineStatus(true);
}

bootstrap();
