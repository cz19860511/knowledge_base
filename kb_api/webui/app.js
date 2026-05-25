const PAGE = document.body?.dataset?.page || "home";

const state = {
  health: null,
  apiKey: localStorage.getItem("kb_api_key") || "",
  rawFolders: [],
  rawFiles: [],
  rawPipeline: null,
  rawExpandedHistory: new Set(),
  pipelineConfig: null,
  registry: null,
  dailyReportAutomation: null,
  overview: null,
  tasksPage: null,
  selectedTaskId: "",
  taskConfirmations: [],
  taskDetail: null,
  taskLogs: [],
  taskDueReport: null,
  taskWeeklyReport: null,
  taskAutomation: null,
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
  setText("active-kb-id", data.active_knowledge_base_id || data.knowledge_base_id || "-");
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

function todayIsoDate() {
  try {
    return new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Shanghai" });
  } catch {
    return new Date().toISOString().slice(0, 10);
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

function truncateText(value, limit = 420) {
  const text = String(value || "");
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).trim()}…`;
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

function renderKnowledgeBaseRegistry(payload) {
  state.registry = payload;
  const pill = el("registry-pill");
  if (pill) {
    pill.textContent = payload?.active_knowledge_base_id ? `当前：${payload.active_knowledge_base_id}` : "未加载";
    pill.classList.remove("ok", "warn");
    pill.classList.add("ok");
  }
  setText("registry-path", payload?.registry_path || "-");
  setText("registry-save-state", payload?.updated_at ? `已保存 ${formatTime(payload.updated_at)}` : "未保存");

  const body = el("registry-table");
  if (!body) return;

  const items = payload?.items || [];
  if (!items.length) {
    body.innerHTML = '<tr><td colspan="6" class="placeholder">注册表为空</td></tr>';
    return;
  }

  body.innerHTML = items
    .map((item) => {
      const isActive = item.knowledge_base_id === payload?.active_knowledge_base_id;
      const statusPill = isActive ? "当前" : item.status || "-";
      const rootDir = item.root_dir || "-";
      const counts = `${item.doc_count ?? 0} / ${item.chunk_count ?? 0}`;
      return `
        <tr>
          <td>
            <strong>${escapeHtml(item.name || item.knowledge_base_id)}</strong>
            <div class="snippet">${escapeHtml(item.knowledge_base_id)}</div>
          </td>
          <td>${escapeHtml(statusPill)}</td>
          <td>${escapeHtml(rootDir)}</td>
          <td>${escapeHtml(counts)}</td>
          <td>${escapeHtml(formatTime(item.updated_at || item.created_at))}</td>
          <td>
            <div class="file-actions">
              <button class="ghost-btn" data-registry-edit="${escapeHtml(item.knowledge_base_id)}">编辑</button>
              <button class="ghost-btn" data-registry-initialize="${escapeHtml(item.knowledge_base_id)}">初始化目录</button>
              <button class="ghost-btn" data-registry-activate="${escapeHtml(item.knowledge_base_id)}">设为当前</button>
              <button class="ghost-btn danger-btn" data-registry-delete="${escapeHtml(item.knowledge_base_id)}">删除</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

function resetRegistryForm() {
  setInputValue("registry-current-id", "");
  setText("registry-form-mode", "新建");
  setInputValue("registry-kb-id", "");
  setInputValue("registry-name", "");
  setInputValue("registry-owner", "");
  setText("registry-save-state", state.registry?.updated_at ? `已保存 ${formatTime(state.registry.updated_at)}` : "未保存");
  setInputValue("registry-description", "");
  setInputValue("registry-root-dir", "");
  setInputValue("registry-default-batch-id", "");
  setInputValue("registry-doc-count", 0);
  setInputValue("registry-chunk-count", 0);
  setInputValue("registry-status", "active");
}

function fillRegistryForm(item) {
  if (!item) return;
  setInputValue("registry-current-id", item.knowledge_base_id || "");
  setText("registry-form-mode", "编辑");
  setInputValue("registry-kb-id", item.knowledge_base_id || "");
  setInputValue("registry-name", item.name || "");
  setInputValue("registry-owner", item.owner || "");
  setInputValue("registry-description", item.description || "");
  setInputValue("registry-root-dir", item.root_dir || "");
  setInputValue("registry-default-batch-id", item.default_batch_id || "");
  setInputValue("registry-doc-count", item.doc_count ?? 0);
  setInputValue("registry-chunk-count", item.chunk_count ?? 0);
  setInputValue("registry-status", item.status || "active");
}

function buildRegistryPayload() {
  return {
    knowledge_base_id: (el("registry-kb-id")?.value || "").trim(),
    name: (el("registry-name")?.value || "").trim(),
    owner: (el("registry-owner")?.value || "").trim(),
    status: (el("registry-status")?.value || "active").trim(),
    description: (el("registry-description")?.value || "").trim(),
    root_dir: (el("registry-root-dir")?.value || "").trim(),
    default_batch_id: (el("registry-default-batch-id")?.value || "").trim(),
    doc_count: Number(el("registry-doc-count")?.value || 0),
    chunk_count: Number(el("registry-chunk-count")?.value || 0),
  };
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

function renderDailyReportAutomation(payload) {
  state.dailyReportAutomation = payload;
  const pill = el("daily-report-pill");
  if (pill) {
    const isWarn = Boolean(payload?.last_error);
    pill.textContent = payload?.running ? "运行中" : payload?.thread_started ? "已启动" : "未启动";
    pill.classList.remove("ok", "warn");
    pill.classList.add(isWarn ? "warn" : "ok");
  }

  setText("daily-report-scheduled", payload?.scheduled_time || "-");
  setText("daily-report-last-success", payload?.last_success_date || "-");
  setText("daily-report-next", payload?.next_planned_date || (payload?.pending_dates?.[0] || "-"));
  setText("daily-report-error", payload?.last_error || "-");
}

function renderDailyReportAutomationEmpty(message) {
  const pill = el("daily-report-pill");
  if (pill) {
    pill.textContent = "未加载";
    pill.classList.remove("ok", "warn");
  }
  setText("daily-report-scheduled", "-");
  setText("daily-report-last-success", "-");
  setText("daily-report-next", "-");
  setText("daily-report-error", message || "-");
}

function renderOverviewEmpty(message) {
  state.overview = null;
  const pill = el("overview-pill");
  if (pill) {
    pill.textContent = message || "未加载";
    pill.classList.remove("ok", "warn");
  }
  setText("overview-active-kb", "-");
  setText("overview-date", "-");
  setText("overview-kb-count", "-");
  setText("overview-event-total", "-");
  setText("overview-failed-total", "-");
  setText("overview-suggestion-total", "-");
  setText("overview-confirm-total", "-");
  setText("overview-task-total", "-");
  setText("overview-missing-total", "-");
  setText("overview-daily-path", "-");
  setText("overview-daily-summary", "-");
  setText("overview-reconcile-path", "-");
  setText("overview-reconcile-summary", "-");
  setText("overview-replay-path", "-");
  setText("overview-replay-summary", "-");
  setText("overview-automation-path", "-");
  setText("overview-automation-summary", "-");
  setText("overview-task-automation-path", "-");
  setText("overview-task-automation-summary", "-");
  setText("overview-status-pill", message || "未加载");
  setHtml("overview-timeline", '<div class="placeholder">先加载总览，再查看时间线。</div>');
  setHtml("overview-suggestions", '<div class="placeholder">-</div>');
  setHtml("overview-confirmations", '<div class="placeholder">-</div>');
  setHtml("overview-tasks", '<div class="placeholder">-</div>');
}

function renderOverviewSuggestion(item) {
  const chips = [
    item.category || "-",
    item.risk_level ? `风险 ${item.risk_level}` : null,
    item.priority != null ? `优先级 ${item.priority}` : null,
  ]
    .filter(Boolean)
    .map((value) => `<span class="chip">${escapeHtml(String(value))}</span>`)
    .join("");

  return `
    <article class="overview-item">
      <div class="overview-item-head">
        <strong>${escapeHtml(item.title || "-")}</strong>
        <span class="score-badge">${escapeHtml(item.category || "-")}</span>
      </div>
      <div class="chips">${chips}</div>
      <div class="snippet">${escapeHtml(item.summary || item.recommendation || "-")}</div>
    </article>
  `;
}

function renderOverviewConfirmation(item) {
  return `
    <article class="overview-item">
      <div class="overview-item-head">
        <strong>${escapeHtml(item.suggestion?.title || item.decision || "-")}</strong>
        <span class="score-badge">${escapeHtml(item.decision || "-")}</span>
      </div>
      <div class="snippet">${escapeHtml(item.note || item.suggestion?.summary || "-")}</div>
      <div class="mini-note">${escapeHtml(formatTime(item.decided_at || ""))} · ${escapeHtml(item.decided_by || "-")}</div>
      <div class="overview-item-actions">
        <button class="ghost-btn" data-confirmation-task="${escapeHtml(item.confirmation_id || "")}">转任务</button>
      </div>
    </article>
  `;
}

function renderOverviewTask(item) {
  return `
    <article class="overview-item">
      <div class="overview-item-head">
        <strong>${escapeHtml(item.title || "-")}</strong>
        <span class="score-badge">${escapeHtml(item.status || "-")}</span>
      </div>
      <div class="snippet">${escapeHtml(item.summary || "-")}</div>
      <div class="mini-note">${escapeHtml(item.owner || "-")} · ${escapeHtml(item.due_date || "未设截止")}</div>
    </article>
  `;
}

function renderPlatformOverview(payload) {
  state.overview = payload;
  const pill = el("overview-pill");
  if (pill) {
    pill.textContent = payload?.status || "ok";
    pill.classList.remove("ok", "warn");
    pill.classList.add((payload?.status || "ok") === "ok" ? "ok" : "warn");
  }
  setText("overview-active-kb", payload?.active_knowledge_base_id || "-");
  setText("overview-date", `统计日期：${payload?.report_date || todayIsoDate()}`);
  setText("overview-kb-count", String(payload?.knowledge_base_count ?? "-"));
  setText("overview-event-total", String(payload?.event_total ?? "-"));
  setText("overview-failed-total", String(payload?.failed_event_total ?? "-"));
  setText("overview-suggestion-total", String(payload?.suggestion_total ?? "-"));
  setText("overview-confirm-total", String(payload?.confirmation_total ?? "-"));
  setText("overview-task-total", String(payload?.task_total ?? "-"));
  setText("overview-missing-total", String(payload?.missing_ref_total ?? "-"));
  setText("overview-daily-path", payload?.daily_report_path || "-");
  setText("overview-daily-summary", payload?.daily_report_summary || "-");
  setText("overview-reconcile-path", payload?.reconciliation_path || "-");
  setText("overview-reconcile-summary", payload?.reconciliation_summary || "-");
  setText("overview-replay-path", payload?.replay_path || "-");
  setText("overview-replay-summary", payload?.replay_summary || "-");
  setText("overview-automation-path", payload?.daily_automation_path || "-");
  setText("overview-automation-summary", payload?.daily_automation_summary || "-");
  setText("overview-task-automation-path", payload?.task_automation_path || "-");
  setText("overview-task-automation-summary", payload?.task_automation_summary || "-");
  setText("overview-status-pill", payload?.status || "ok");

  const timelineNode = el("overview-timeline");
  const timeline = payload?.timeline || [];
  if (timelineNode) {
    timelineNode.innerHTML = timeline.length
      ? timeline
          .slice(0, 15)
          .map(
            (item) => `
              <article class="result-item">
                <div class="result-top">
                  <strong>${escapeHtml(item.event_type || "-")}</strong>
                  <span class="score-badge">${escapeHtml(item.status || "-")}</span>
                </div>
                <div class="chips">
                  <span class="chip">${escapeHtml(item.started_at || "-")}</span>
                  <span class="chip">${escapeHtml(item.knowledge_base_id || "-")}</span>
                  <span class="chip">${escapeHtml(item.source || "-")}</span>
                </div>
                <div class="snippet">${escapeHtml(item.remark || "-")}</div>
              </article>
            `,
          )
          .join("")
      : '<div class="placeholder">今天还没有事件。</div>';
  }

  const suggestionsNode = el("overview-suggestions");
  if (suggestionsNode) {
    suggestionsNode.innerHTML = (payload?.suggestions || []).length
      ? payload.suggestions.slice(0, 5).map(renderOverviewSuggestion).join("")
      : '<div class="placeholder">今天没有需要特别关注的建议。</div>';
  }

  const confirmationsNode = el("overview-confirmations");
  if (confirmationsNode) {
    confirmationsNode.innerHTML = (payload?.confirmations || []).length
      ? payload.confirmations.slice(0, 5).map(renderOverviewConfirmation).join("")
      : '<div class="placeholder">今天还没有确认记录。</div>';
  }

  const tasksNode = el("overview-tasks");
  if (tasksNode) {
    tasksNode.innerHTML = (payload?.tasks || []).length
      ? payload.tasks.slice(0, 5).map(renderOverviewTask).join("")
      : '<div class="placeholder">今天还没有平台任务。</div>';
  }
}

function renderTaskHistoryEntry(item) {
  const chips = [
    item.event_type || "-",
    item.from_status && item.to_status ? `${item.from_status} → ${item.to_status}` : null,
    item.status ? `状态 ${item.status}` : null,
    item.owner ? `负责人 ${item.owner}` : null,
    item.due_date ? `截止 ${item.due_date}` : null,
  ]
    .filter(Boolean)
    .map((value) => `<span class="chip">${escapeHtml(String(value))}</span>`)
    .join("");

  return `
    <article class="task-history-item">
      <div class="task-history-head">
        <strong>${escapeHtml(formatTime(item.created_at || item.decided_at || ""))}</strong>
        <span class="score-badge">${escapeHtml(item.event_type || "-")}</span>
      </div>
      <div class="chips">${chips}</div>
      <div class="task-history-meta">${escapeHtml(item.note || item.remark || "-")}</div>
    </article>
  `;
}

function renderPlatformTaskDetailEmpty(message) {
  state.taskDetail = null;
  state.taskLogs = [];
  setText("task-detail-title", message || "-");
  setText("task-detail-meta", "-");
  setText("task-detail-summary", "-");
  setText("task-detail-source", "-");
  setText("task-detail-payload", "{}");
  setHtml("task-history", '<div class="placeholder">-</div>');
  setText("task-selection-note", message || "先选择一条任务");
  setDisabled("transition-task", true);
  setText("task-page-pill", message || "未加载");
  setText("task-report-pill", "任务报告未加载");
  setText("task-total", "-");
  setText("task-pending-total", "-");
  setText("task-running-total", "-");
  setText("task-blocked-total", "-");
  setText("task-done-total", "-");
  setText("task-report-path", "-");
  setText("task-log-type", "note");
  setInputValue("task-log-author", "");
  setInputValue("task-log-content", "");
  setText("task-log-note", message || "先选择一条任务");
  setHtml("task-logs", '<div class="placeholder">-</div>');
}

function clearPlatformTaskCreateForm() {
  setInputValue("task-confirmation-id", "");
  setInputValue("task-confirmation-date", "");
  setInputValue("task-create-owner", "");
  setInputValue("task-create-due-date", "");
  setInputValue("task-create-note", "");
}

function renderPlatformTaskDetail(payload) {
  state.taskDetail = payload || null;
  const task = payload?.task || {};
  state.selectedTaskId = task.task_id || "";
  setText("task-detail-title", task.title || "-");
  setText(
    "task-detail-meta",
    [
      task.task_id ? `任务 ID：${task.task_id}` : null,
      task.status ? `状态：${task.status}` : null,
      task.priority != null ? `优先级：${task.priority}` : null,
      task.owner ? `负责人：${task.owner}` : null,
      task.due_date ? `截止：${task.due_date}` : null,
      task.created_at ? `创建：${formatTime(task.created_at)}` : null,
      task.updated_at ? `更新：${formatTime(task.updated_at)}` : null,
    ]
      .filter(Boolean)
      .join(" · "),
  );
  setText("task-detail-summary", task.summary || "-");
  setText(
    "task-detail-source",
    [
      task.source_type ? `来源：${task.source_type}` : null,
      task.source_id ? `来源 ID：${task.source_id}` : null,
      task.source_report_date ? `报告日期：${task.source_report_date}` : null,
      task.source_report_path ? `报告路径：${task.source_report_path}` : null,
    ]
      .filter(Boolean)
      .join(" · "),
  );
  setText("task-detail-payload", JSON.stringify(task.source_payload || {}, null, 2));
  setInputValue("task-target-status", task.status || "ready");
  setInputValue("task-owner", task.owner || "");
  setInputValue("task-due-date", task.due_date || "");
  setInputValue("task-note", task.note || "");
  setText("task-selection-note", `当前任务：${task.title || task.task_id || "-"}`);
  setDisabled("transition-task", false);

  const historyNode = el("task-history");
  const history = payload?.history || [];
  if (historyNode) {
    historyNode.innerHTML = history.length
      ? history.slice().reverse().map(renderTaskHistoryEntry).join("")
      : '<div class="placeholder">暂无历史记录</div>';
  }
}

function renderPlatformTaskList(payload, reportPayload = null) {
  state.tasksPage = {
    list: payload,
    report: reportPayload,
  };
  const pill = el("task-page-pill");
  if (pill) {
    pill.textContent = "已加载";
    pill.classList.remove("ok", "warn");
    pill.classList.add("ok");
  }

  const report = reportPayload || {};
  const items = payload?.items || [];
  const counts = items.reduce(
    (acc, item) => {
      const status = String(item.status || "").trim();
      if (status in acc) {
        acc[status] += 1;
      }
      return acc;
    },
    { pending: 0, running: 0, blocked: 0, done: 0 },
  );
  setText("task-total", String(payload?.total ?? items.length ?? "-"));
  setText("task-pending-total", String(counts.pending ?? 0));
  setText("task-running-total", String(counts.running ?? 0));
  setText("task-blocked-total", String(counts.blocked ?? 0));
  setText("task-done-total", String(counts.done ?? 0));
  setText("task-report-path", report.task_path || payload?.task_path || "-");
  setText("task-report-pill", report.report_date ? `报告 ${report.report_date}` : "任务报告已加载");

  const body = el("task-table");
  if (!body) return;

  if (!items.length) {
    body.innerHTML = '<tr><td colspan="5" class="placeholder">当前筛选条件下没有任务</td></tr>';
    return;
  }

  body.innerHTML = items
    .map((item) => {
      const selected = state.selectedTaskId && state.selectedTaskId === item.task_id;
      return `
        <tr class="${selected ? "task-row-selected" : ""}">
          <td>
            <strong>${escapeHtml(item.title || "-")}</strong>
            <div class="history-text">${escapeHtml(item.summary || "-")}</div>
          </td>
          <td>
            <span class="score-badge">${escapeHtml(item.status || "-")}</span>
            <div class="history-text">${escapeHtml(item.priority != null ? `priority ${item.priority}` : "-")}</div>
          </td>
          <td>
            ${escapeHtml(item.owner || "-")}
            <div class="history-text">${escapeHtml(item.due_date || "未设截止")}</div>
          </td>
          <td>
            ${escapeHtml(item.source_type || "-")}
            <div class="history-text">${escapeHtml(item.source_id || item.source_report_date || "-")}</div>
          </td>
          <td>
            <div class="task-row-actions">
              <button class="ghost-btn" data-task-open="${escapeHtml(item.task_id)}">查看</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

function renderPlatformTaskConfirmations(payload) {
  state.taskConfirmations = payload?.items || [];
  const note = el("task-confirmation-note");
  if (note) {
    note.textContent = payload?.event_date ? `确认日期：${payload.event_date}` : "确认记录已加载";
  }

  const container = el("task-confirmations");
  if (!container) return;

  if (!state.taskConfirmations.length) {
    container.innerHTML = '<div class="placeholder">当前日期没有确认记录</div>';
    return;
  }

  container.innerHTML = state.taskConfirmations
    .map((item) => {
      const suggestion = item.suggestion || {};
      return `
        <article class="overview-item">
          <div class="overview-item-head">
            <strong>${escapeHtml(suggestion.title || item.decision || "-")}</strong>
            <span class="score-badge">${escapeHtml(item.decision || "-")}</span>
          </div>
          <div class="chips">
            <span class="chip">${escapeHtml(item.confirmation_id || "-")}</span>
            <span class="chip">${escapeHtml(item.decided_by || "-")}</span>
            <span class="chip">${escapeHtml(item.decided_at || "-")}</span>
          </div>
          <div class="snippet">${escapeHtml(item.note || suggestion.summary || "-")}</div>
          <div class="mini-note">${escapeHtml(suggestion.recommendation || "-")}</div>
          <div class="task-confirmation-actions">
            <button class="ghost-btn" data-task-confirmation="${escapeHtml(item.confirmation_id || "")}">转任务</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderPlatformTaskLogs(payload) {
  state.taskLogs = payload?.items || [];
  const note = el("task-log-note");
  if (note) {
    note.textContent = payload?.event_date ? `日志日期：${payload.event_date}` : "执行日志已加载";
  }

  const container = el("task-logs");
  if (!container) return;

  if (!state.taskLogs.length) {
    container.innerHTML = '<div class="placeholder">当前没有执行日志</div>';
    return;
  }

  container.innerHTML = state.taskLogs
    .map((item) => {
      return `
        <article class="overview-item">
          <div class="overview-item-head">
            <strong>${escapeHtml(item.log_type || "-")}</strong>
            <span class="score-badge">${escapeHtml(formatTime(item.created_at || ""))}</span>
          </div>
          <div class="chips">
            <span class="chip">${escapeHtml(item.log_id || "-")}</span>
            <span class="chip">${escapeHtml(item.author || "-")}</span>
          </div>
          <div class="snippet">${escapeHtml(item.content || "-")}</div>
        </article>
      `;
    })
    .join("");
}

function renderPlatformTaskLogsEmpty(message) {
  state.taskLogs = [];
  const note = el("task-log-note");
  if (note) {
    note.textContent = message || "执行日志未加载";
  }
  setHtml("task-logs", `<div class="placeholder">${escapeHtml(message || "-")}</div>`);
}

function renderTaskReminderList(selector, items) {
  const container = el(selector);
  if (!container) return;
  if (!items.length) {
    container.innerHTML = '<div class="placeholder">无</div>';
    return;
  }
  container.innerHTML = items
    .slice(0, 8)
    .map((item) => {
      const chips = [
        item.status || "-",
        item.owner || "-",
        item.due_date || "-",
      ]
        .map((value) => `<span class="chip">${escapeHtml(String(value))}</span>`)
        .join("");
      return `
        <article class="overview-item">
          <div class="overview-item-head">
            <strong>${escapeHtml(item.title || "-")}</strong>
            <span class="score-badge">${escapeHtml(item.priority != null ? `P${item.priority}` : "-")}</span>
          </div>
          <div class="chips">${chips}</div>
          <div class="snippet">${escapeHtml(item.summary || item.note || "-")}</div>
        </article>
      `;
    })
    .join("");
}

function renderTaskDueReport(payload) {
  state.taskDueReport = payload || null;
  setText("task-due-pill", payload?.event_date ? `提醒 ${payload.event_date}` : "未加载");
  setText("task-overdue-total", String((payload?.overdue || []).length ?? "-"));
  setText("task-due-soon-total", String((payload?.due_soon || []).length ?? "-"));
  setText("task-no-due-total", String((payload?.no_due || []).length ?? "-"));
  setText("task-due-report-path", payload?.report_path || "-");
  renderTaskReminderList("task-overdue-list", payload?.overdue || []);
  renderTaskReminderList("task-due-soon-list", payload?.due_soon || []);
}

function renderTaskDueReportEmpty(message) {
  state.taskDueReport = null;
  setText("task-due-pill", message || "未加载");
  setText("task-overdue-total", "-");
  setText("task-due-soon-total", "-");
  setText("task-no-due-total", "-");
  setText("task-due-report-path", "-");
  setHtml("task-overdue-list", `<div class="placeholder">${escapeHtml(message || "-")}</div>`);
  setHtml("task-due-soon-list", `<div class="placeholder">${escapeHtml(message || "-")}</div>`);
}

function renderTaskWeeklyReport(payload) {
  state.taskWeeklyReport = payload || null;
  setText("task-weekly-report-status", payload?.event_date ? `周报 ${payload.event_date}` : "未加载");
  setText("task-weekly-report-path", payload?.report_path || "-");
}

function renderTaskWeeklyReportEmpty(message) {
  state.taskWeeklyReport = null;
  setText("task-weekly-report-status", message || "未加载");
  setText("task-weekly-report-path", "-");
}

function renderTaskAutomation(payload) {
  state.taskAutomation = payload || null;
  const pill = el("task-automation-pill");
  if (pill) {
    pill.textContent = payload?.running ? "运行中" : payload?.thread_started ? "已启动" : "未启动";
    pill.classList.remove("ok", "warn");
    pill.classList.add(payload?.last_error ? "warn" : "ok");
  }
  setText("task-automation-run-time", payload?.scheduled_time || "-");
  setText("task-automation-last-success", payload?.last_success_date || "-");
  setText("task-automation-next", payload?.next_planned_date || (payload?.pending_dates?.[0] || "-"));
  setText("task-automation-error", payload?.last_error || "-");
  setText("task-automation-due-path", payload?.last_due_report_path || "-");
  setText("task-automation-weekly-path", payload?.last_weekly_report_path || "-");
}

function renderTaskAutomationEmpty(message) {
  state.taskAutomation = null;
  const pill = el("task-automation-pill");
  if (pill) {
    pill.textContent = message || "未加载";
    pill.classList.remove("ok", "warn");
  }
  setText("task-automation-run-time", "-");
  setText("task-automation-last-success", "-");
  setText("task-automation-next", "-");
  setText("task-automation-error", message || "-");
  setText("task-automation-due-path", "-");
  setText("task-automation-weekly-path", "-");
}

function buildTaskListMarkdown() {
  const filters = getTaskPageFilters();
  const list = state.tasksPage?.list || { total: 0, items: [] };
  const report = state.tasksPage?.report || {};
  const items = list.items || [];
  const lines = [
    `# 平台任务导出 ${filters.date || todayIsoDate()}`,
    "",
    "## 筛选条件",
    "",
    `- 日期：${filters.date || "-"}`,
    `- 状态：${filters.status || "全部"}`,
    `- 来源：${filters.sourceType || "全部"}`,
    "",
    "## 概览",
    "",
    `- 任务总数：${list.total ?? items.length ?? 0}`,
    `- 报告路径：${report.task_path || "-"}`,
    "",
    "## 任务列表",
    "",
  ];

  if (!items.length) {
    lines.push("- 无");
  } else {
    items.forEach((item, index) => {
      lines.push(
        `${index + 1}. [${item.status || "-"}] ${item.title || "-"} ` +
          `priority=${item.priority ?? "-"} owner=${item.owner || "-"} due=${item.due_date || "-"}`,
      );
      lines.push(`   - 任务 ID：${item.task_id || "-"}`);
      lines.push(`   - 来源：${item.source_type || "-"} / ${item.source_id || item.source_report_date || "-"}`);
      if (item.summary) {
        lines.push(`   - 摘要：${item.summary}`);
      }
      if (item.note) {
        lines.push(`   - 备注：${item.note}`);
      }
    });
  }

  if (state.taskConfirmations.length) {
    lines.push("", "## 确认记录", "");
    state.taskConfirmations.forEach((item, index) => {
      const suggestion = item.suggestion || {};
      lines.push(
        `${index + 1}. [${item.decision || "-"}] ${suggestion.title || "-"} ` +
          `confirmation_id=${item.confirmation_id || "-"} decided_by=${item.decided_by || "-"}`,
      );
      if (item.note) {
        lines.push(`   - 备注：${item.note}`);
      }
      if (suggestion.recommendation) {
        lines.push(`   - 建议：${suggestion.recommendation}`);
      }
    });
  }

  return lines.join("\n");
}

function downloadTextFile(filename, content) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportTaskListMarkdown() {
  if (!state.tasksPage?.list) {
    alert("先加载任务列表再导出。");
    return;
  }
  const date = getTaskPageFilters().date || todayIsoDate();
  const filename = `platform_tasks_${date}.md`;
  downloadTextFile(filename, buildTaskListMarkdown());
}

function buildSelectedTaskMarkdown() {
  const payload = state.taskDetail || {};
  const task = payload.task || {};
  const history = payload.history || [];
  const lines = [
    `# 任务详情 ${task.title || task.task_id || "-"}`,
    "",
    "## 基本信息",
    "",
    `- 任务 ID：${task.task_id || "-"}`,
    `- 状态：${task.status || "-"}`,
    `- 优先级：${task.priority ?? "-"}`,
    `- 负责人：${task.owner || "-"}`,
    `- 截止日期：${task.due_date || "-"}`,
    `- 创建时间：${task.created_at || "-"}`,
    `- 更新时间：${task.updated_at || "-"}`,
    `- 来源类型：${task.source_type || "-"}`,
    `- 来源 ID：${task.source_id || "-"}`,
    `- 来源报告日期：${task.source_report_date || "-"}`,
    `- 来源报告路径：${task.source_report_path || "-"}`,
    "",
    "## 任务摘要",
    "",
    task.summary || "-",
    "",
    "## 备注",
    "",
    task.note || "-",
    "",
    "## 原始载荷",
    "",
    "```json",
    JSON.stringify(task.source_payload || {}, null, 2),
    "```",
    "",
    "## 历史轨迹",
    "",
  ];

  if (!history.length) {
    lines.push("- 无");
  } else {
    history.forEach((item, index) => {
      lines.push(
        `${index + 1}. ${item.event_type || "-"} ` +
          `${item.from_status && item.to_status ? `${item.from_status} -> ${item.to_status}` : ""}`.trim(),
      );
      lines.push(`   - 时间：${item.created_at || "-"}`);
      lines.push(`   - 状态：${item.status || "-"}`);
      if (item.owner) {
        lines.push(`   - 负责人：${item.owner}`);
      }
      if (item.due_date) {
        lines.push(`   - 截止日期：${item.due_date}`);
      }
      if (item.note) {
        lines.push(`   - 备注：${item.note}`);
      }
    });
  }

  return lines.join("\n");
}

function exportSelectedTaskMarkdown() {
  if (!state.taskDetail?.task?.task_id) {
    alert("先选择一条任务再导出。");
    return;
  }
  const task = state.taskDetail.task;
  const filename = `platform_task_${task.task_id}.md`;
  downloadTextFile(filename, buildSelectedTaskMarkdown());
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

async function loadDailyAutomation(silent = false) {
  const pill = el("daily-report-pill");
  if (!pill) return;

  if (!state.apiKey) {
    if (!silent) {
      alert("先输入 API Key 再查看日报自动任务。");
    }
    renderDailyReportAutomationEmpty("输入 API Key 后可查看");
    return;
  }

  try {
    const data = await fetchJson("/operations/daily-report/automation", {
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    renderDailyReportAutomation(data);
  } catch (error) {
    if (!silent) {
      alert(`加载日报自动任务失败：${error.message}`);
    }
    renderDailyReportAutomationEmpty("加载失败");
  }
}

async function runDailyAutomationNow() {
  if (!requireApiKey()) return;
  const button = el("run-daily-report-now");
  if (!button) return;

  button.disabled = true;
  button.textContent = "补跑中...";
  try {
    const data = await fetchJson("/operations/daily-report/automation/run", {
      method: "POST",
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    renderDailyReportAutomation({
      ...state.dailyReportAutomation,
      ...data,
    });
    alert(`补跑完成：${data.results?.length || 0} 份日报。`);
  } catch (error) {
    alert(`补跑失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "立即补跑";
  }
}

async function loadPlatformOverview(silent = false) {
  const pill = el("overview-pill");
  if (!pill) return;

  if (!state.apiKey) {
    if (!silent) {
      alert("先输入 API Key 再加载平台总览。");
    }
    renderOverviewEmpty("输入 API Key 后可查看");
    return;
  }

  const today = todayIsoDate();
  const headers = { Authorization: `Bearer ${state.apiKey}` };

  try {
    const [
      registry,
      knowledgeBases,
      automation,
      taskAutomation,
      events,
      dailyReport,
      reconciliation,
      replay,
      suggestions,
      confirmations,
      taskReport,
      tasksList,
      assets,
    ] = await Promise.all([
      fetchJson("/knowledge-base-registry", { headers }),
      fetchJson("/knowledge-bases", { headers }),
      fetchJson("/operations/daily-report/automation", { headers }),
      fetchJson("/operations/platform-task-report/automation", { headers }),
      fetchJson(`/operations/events?date=${encodeURIComponent(today)}&limit=100`, { headers }),
      fetchJson(`/operations/daily-report?date=${encodeURIComponent(today)}&save=false`, { headers }),
      fetchJson(`/operations/version-reconciliation?date=${encodeURIComponent(today)}&save=false`, { headers }),
      fetchJson(`/operations/replay-report?date=${encodeURIComponent(today)}&save=false`, { headers }),
      fetchJson(`/operations/evolution-suggestions?date=${encodeURIComponent(today)}`, { headers }),
      fetchJson(`/operations/evolution-confirmations?date=${encodeURIComponent(today)}`, { headers }),
      fetchJson(`/operations/platform-task-report?date=${encodeURIComponent(today)}&save=false`, { headers }),
      fetchJson(`/operations/platform-tasks?date=${encodeURIComponent(today)}&limit=50`, { headers }),
      fetchJson(`/operations/assets?limit=500`, { headers }),
    ]);

    const failedEventTotal = (events.items || []).filter((item) => String(item.status || "").trim() === "failed").length;
    const summary = {
      status: reconciliation.missing_ref_total || failedEventTotal ? "warn" : "ok",
      report_date: today,
      active_knowledge_base_id: registry.active_knowledge_base_id || state.health?.active_knowledge_base_id || state.health?.knowledge_base_id || "-",
      knowledge_base_count: knowledgeBases.total ?? (knowledgeBases.knowledge_base_list || []).length,
      event_total: events.total ?? (events.items || []).length,
      failed_event_total: failedEventTotal,
      suggestion_total: suggestions.total_suggestions ?? (suggestions.suggestions || []).length,
      confirmation_total: confirmations.total ?? (confirmations.items || []).length,
      task_total: taskReport.total ?? (tasksList.items || []).length,
      missing_ref_total: reconciliation.missing_ref_total ?? 0,
      daily_report_path: dailyReport.report_path || "-",
      daily_report_summary: truncateText(dailyReport.content || "今日日报未生成。", 500),
      reconciliation_path: reconciliation.report_path || "-",
      reconciliation_summary: truncateText(reconciliation.content || "对账结果为空。", 360),
      replay_path: replay.report_path || "-",
      replay_summary: truncateText(replay.content || "回放结果为空。", 360),
      daily_automation_path: automation.running ? "运行中" : automation.thread_started ? "已启动" : "未启动",
      daily_automation_summary: automation.last_error ? `自动调度异常：${automation.last_error}` : `计划时间 ${automation.scheduled_time || "-"}`,
      task_automation_path: taskAutomation.running ? "运行中" : taskAutomation.thread_started ? "已启动" : "未启动",
      task_automation_summary: taskAutomation.last_error ? `自动汇总异常：${taskAutomation.last_error}` : `计划时间 ${taskAutomation.scheduled_time || "-"}`,
      timeline: (events.items || []).slice().sort((a, b) => String(a.started_at || "").localeCompare(String(b.started_at || ""))),
      suggestions: (suggestions.suggestions || []).slice(0, 5),
      confirmations: (confirmations.items || []).slice(0, 5),
      tasks: (tasksList.items || []).slice(0, 5),
      asset_total: assets.total ?? (assets.items || []).length,
      recent_assets: (assets.items || []).slice(-5),
    };
    renderPlatformOverview(summary);
  } catch (error) {
    if (!silent) {
      alert(`加载平台总览失败：${error.message}`);
    }
    renderOverviewEmpty("加载失败");
  }
}

function getTaskPageFilters() {
  return {
    date: (el("task-date")?.value || "").trim() || todayIsoDate(),
    status: (el("task-status-filter")?.value || "").trim(),
    sourceType: (el("task-source-filter")?.value || "").trim(),
  };
}

async function loadPlatformTaskDetail(taskId, silent = false) {
  if (!requireApiKey()) return;
  if (!taskId) {
    renderPlatformTaskDetailEmpty("先选择一条任务");
    return;
  }

  try {
    const filters = getTaskPageFilters();
    const payload = await fetchJson(`/operations/platform-tasks/${encodeURIComponent(taskId)}?date=${encodeURIComponent(filters.date)}`, {
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    renderPlatformTaskDetail(payload);
    renderPlatformTaskList(state.tasksPage?.list || { items: [], total: 0 }, state.tasksPage?.report || null);
    await loadPlatformTaskLogs(taskId, true);
  } catch (error) {
    if (!silent) {
      alert(`加载任务详情失败：${error.message}`);
    }
    renderPlatformTaskDetailEmpty("加载失败");
  }
}

async function loadPlatformTasks(silent = false) {
  const pill = el("task-page-pill");
  if (!pill) return;

  if (!state.apiKey) {
    if (!silent) {
      alert("先输入 API Key 再加载平台任务。");
    }
    pill.textContent = "未加载";
    pill.classList.remove("ok", "warn");
    renderPlatformTaskDetailEmpty("输入 API Key 后可查看");
    setHtml("task-table", '<tr><td colspan="5" class="placeholder">输入 API Key 后可加载任务</td></tr>');
    renderTaskDueReportEmpty("输入 API Key 后可查看");
    renderTaskWeeklyReportEmpty("输入 API Key 后可查看");
    renderTaskAutomationEmpty("输入 API Key 后可查看");
    return;
  }

  const filters = getTaskPageFilters();
  const headers = { Authorization: `Bearer ${state.apiKey}` };

  try {
    const [report, list] = await Promise.all([
      fetchJson(`/operations/platform-task-report?date=${encodeURIComponent(filters.date)}&save=false`, { headers }),
      fetchJson(
        `/operations/platform-tasks?date=${encodeURIComponent(filters.date)}&status=${encodeURIComponent(filters.status)}&source_type=${encodeURIComponent(filters.sourceType)}&limit=200`,
        { headers },
      ),
    ]);
    const confirmations = await fetchJson(`/operations/evolution-confirmations?date=${encodeURIComponent(filters.date)}&limit=200`, { headers });
    const dueReport = await fetchJson(`/operations/platform-task-due-report?date=${encodeURIComponent(filters.date)}&horizon_days=7&save=false`, { headers });
    const weeklyReport = await fetchJson(`/operations/platform-task-weekly-report?date=${encodeURIComponent(filters.date)}&days=7&save=false`, { headers });
    const automation = await fetchJson("/operations/platform-task-report/automation", { headers });

    state.tasksPage = { list, report };
    renderPlatformTaskConfirmations(confirmations);
    renderTaskDueReport(dueReport);
    renderTaskWeeklyReport(weeklyReport);
    renderTaskAutomation(automation);
    const nextTaskId =
      state.selectedTaskId && (list.items || []).some((item) => item.task_id === state.selectedTaskId)
        ? state.selectedTaskId
        : (list.items || [])[0]?.task_id || "";
    renderPlatformTaskList(list, report);
    if (nextTaskId) {
      await loadPlatformTaskDetail(nextTaskId, true);
      await loadPlatformTaskLogs(nextTaskId, true);
    } else {
      renderPlatformTaskDetailEmpty("当前筛选条件下没有任务");
      renderPlatformTaskLogsEmpty("当前筛选条件下没有执行日志");
    }
  } catch (error) {
    if (!silent) {
      alert(`加载平台任务失败：${error.message}`);
    }
    pill.textContent = "加载失败";
    pill.classList.remove("ok", "warn");
    pill.classList.add("warn");
    renderPlatformTaskDetailEmpty("加载失败");
    renderTaskDueReportEmpty("加载失败");
    renderTaskWeeklyReportEmpty("加载失败");
    renderTaskAutomationEmpty("加载失败");
  }
}

async function loadPlatformTaskLogs(taskId = "", silent = false) {
  if (!requireApiKey()) return;

  const filters = getTaskPageFilters();
  const resolvedTaskId = taskId || state.selectedTaskId || "";
  const url = new URL("/operations/platform-task-logs", window.location.origin);
  url.searchParams.set("date", filters.date);
  if (resolvedTaskId) {
    url.searchParams.set("task_id", resolvedTaskId);
  }
  url.searchParams.set("limit", "200");

  try {
    const payload = await fetchJson(url.pathname + url.search, {
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    renderPlatformTaskLogs(payload);
  } catch (error) {
    if (!silent) {
      alert(`加载执行日志失败：${error.message}`);
    }
    renderPlatformTaskLogsEmpty("加载失败");
  }
}

async function addCurrentTaskLog() {
  if (!requireApiKey()) return;
  if (!state.selectedTaskId) {
    alert("先选择一条任务。");
    return;
  }

  const payload = {
    log_type: (el("task-log-type")?.value || "note").trim(),
    author: (el("task-log-author")?.value || "").trim() || "system",
    content: (el("task-log-content")?.value || "").trim(),
  };
  if (!payload.content) {
    alert("请填写日志内容。");
    return;
  }

  const button = el("add-task-log");
  if (!button) return;
  button.disabled = true;
  button.textContent = "记录中...";
  try {
    await fetchJson(`/operations/platform-tasks/${encodeURIComponent(state.selectedTaskId)}/logs?date=${encodeURIComponent(getTaskPageFilters().date)}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${state.apiKey}` },
      body: JSON.stringify(payload),
    });
    setInputValue("task-log-content", "");
    await loadPlatformTaskDetail(state.selectedTaskId, true);
    await loadPlatformTaskLogs(state.selectedTaskId, true);
    alert("日志已记录。");
  } catch (error) {
    alert(`新增日志失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "新增日志";
  }
}

async function savePlatformTaskLogReport() {
  if (!requireApiKey()) return;
  const filters = getTaskPageFilters();
  const taskId = state.selectedTaskId || "";
  const button = el("save-task-log-report");
  if (!button) return;

  button.disabled = true;
  button.textContent = "保存中...";
  try {
    const url = new URL("/operations/platform-task-log-report", window.location.origin);
    url.searchParams.set("date", filters.date);
    if (taskId) {
      url.searchParams.set("task_id", taskId);
    }
    url.searchParams.set("save", "true");
    const report = await fetchJson(url.pathname + url.search, {
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    alert(`任务日志报告已保存：${report.report_path || "-"}`);
  } catch (error) {
    alert(`保存任务日志报告失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "保存日志报告";
  }
}

async function savePlatformTaskDueReport() {
  if (!requireApiKey()) return;
  const filters = getTaskPageFilters();
  const button = el("save-task-due-report");
  if (!button) return;

  button.disabled = true;
  button.textContent = "保存中...";
  try {
    const report = await fetchJson(`/operations/platform-task-due-report?date=${encodeURIComponent(filters.date)}&horizon_days=7&save=true`, {
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    renderTaskDueReport({
      ...state.taskDueReport,
      report_path: report.report_path,
      event_date: report.event_date,
    });
    alert(`到期提醒已保存：${report.report_path || "-"}`);
  } catch (error) {
    alert(`保存到期提醒失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "保存提醒报告";
  }
}

async function savePlatformTaskWeeklyReport() {
  if (!requireApiKey()) return;
  const filters = getTaskPageFilters();
  const button = el("save-task-weekly-report");
  if (!button) return;

  button.disabled = true;
  button.textContent = "保存中...";
  try {
    const report = await fetchJson(`/operations/platform-task-weekly-report?date=${encodeURIComponent(filters.date)}&days=7&save=true`, {
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    renderTaskWeeklyReport({
      ...state.taskWeeklyReport,
      report_path: report.report_path,
      event_date: report.event_date,
    });
    alert(`平台任务周报已保存：${report.report_path || "-"}`);
  } catch (error) {
    alert(`保存周报失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "保存周报";
  }
}

async function runPlatformTaskAutomationNow() {
  if (!requireApiKey()) return;
  const filters = getTaskPageFilters();
  const button = el("run-task-automation-now");
  if (!button) return;

  button.disabled = true;
  button.textContent = "补跑中...";
  try {
    const url = new URL("/operations/platform-task-report/automation/run", window.location.origin);
    url.searchParams.set("date", filters.date);
    const data = await fetchJson(url.pathname + url.search, {
      method: "POST",
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    renderTaskAutomation({
      ...state.taskAutomation,
      ...data,
    });
    alert(`任务自动汇总补跑完成：${data.results?.length || 0} 份。`);
  } catch (error) {
    alert(`任务自动汇总补跑失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "立即补跑";
  }
}

async function savePlatformTaskReport() {
  if (!requireApiKey()) return;
  const filters = getTaskPageFilters();
  const button = el("save-task-report");
  if (!button) return;

  button.disabled = true;
  button.textContent = "保存中...";
  try {
    const report = await fetchJson(`/operations/platform-task-report?date=${encodeURIComponent(filters.date)}&save=true`, {
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    if (state.tasksPage) {
      state.tasksPage.report = report;
    }
    renderPlatformTaskList(state.tasksPage?.list || { total: 0, items: [] }, report);
    alert(`任务报告已保存：${report.report_path || "-"}`);
  } catch (error) {
    alert(`保存任务报告失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "保存任务报告";
  }
}

async function savePlatformTaskHistoryReport() {
  if (!requireApiKey()) return;
  const filters = getTaskPageFilters();
  const button = el("save-task-history-report");
  if (!button) return;

  button.disabled = true;
  button.textContent = "保存中...";
  try {
    const report = await fetchJson(`/operations/platform-task-history-report?date=${encodeURIComponent(filters.date)}&save=true`, {
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    alert(`任务历史报告已保存：${report.report_path || "-"}`);
  } catch (error) {
    alert(`保存任务历史报告失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "保存历史报告";
  }
}

async function transitionCurrentTask() {
  if (!requireApiKey()) return;
  if (!state.selectedTaskId) {
    alert("先选择一条任务。");
    return;
  }

  const payload = {
    target_status: (el("task-target-status")?.value || "ready").trim(),
    owner: (el("task-owner")?.value || "").trim(),
    due_date: (el("task-due-date")?.value || "").trim(),
    note: (el("task-note")?.value || "").trim(),
  };

  const button = el("transition-task");
  if (!button) return;

  button.disabled = true;
  button.textContent = "流转中...";
  try {
    await fetchJson(`/operations/platform-tasks/${encodeURIComponent(state.selectedTaskId)}/transition`, {
      method: "POST",
      headers: { Authorization: `Bearer ${state.apiKey}` },
      body: JSON.stringify(payload),
    });
    await loadPlatformTasks(true);
    alert("任务流转已更新。");
  } catch (error) {
    alert(`流转失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "应用流转";
  }
}

async function createTaskFromConfirmation() {
  if (!requireApiKey()) return;
  const confirmationId = (el("task-confirmation-id")?.value || "").trim();
  if (!confirmationId) {
    alert("先填写确认 ID。");
    return;
  }

  const params = new URLSearchParams();
  params.set("confirmation_id", confirmationId);
  const date = (el("task-confirmation-date")?.value || "").trim();
  if (date) {
    params.set("date", date);
  }
  const owner = (el("task-create-owner")?.value || "").trim();
  if (owner) {
    params.set("owner", owner);
  }
  const dueDate = (el("task-create-due-date")?.value || "").trim();
  if (dueDate) {
    params.set("due_date", dueDate);
  }
  const note = (el("task-create-note")?.value || "").trim();
  if (note) {
    params.set("note", note);
  }

  const button = el("create-task-from-confirmation");
  if (!button) return;

  button.disabled = true;
  button.textContent = "生成中...";
  try {
    const created = await fetchJson(`/operations/platform-tasks/from-confirmation?${params.toString()}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    await loadPlatformTasks(true);
    state.selectedTaskId = created.task_id || "";
    if (state.selectedTaskId) {
      await loadPlatformTaskDetail(state.selectedTaskId, true);
    }
    alert(`任务已生成：${created.title || created.task_id || "-"}`);
  } catch (error) {
    alert(`生成任务失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "从确认生成任务";
  }
}

async function createTaskFromConfirmationRecord(confirmationId, confirmationDate, suggestionTitle) {
  if (!requireApiKey()) return;
  if (!confirmationId) {
    alert("缺少确认 ID。");
    return;
  }

  const params = new URLSearchParams();
  params.set("confirmation_id", confirmationId);
  params.set("date", confirmationDate || todayIsoDate());
  const selectedConfirmation =
    (state.overview?.confirmations || []).find((item) => item.confirmation_id === confirmationId) ||
    (state.taskConfirmations || []).find((item) => item.confirmation_id === confirmationId);
  if (selectedConfirmation?.decided_by) {
    params.set("owner", selectedConfirmation.decided_by);
  }
  if (selectedConfirmation?.note) {
    params.set("note", selectedConfirmation.note);
  }

  try {
    const created = await fetchJson(`/operations/platform-tasks/from-confirmation?${params.toString()}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    alert(`已从确认生成任务：${created.title || suggestionTitle || created.task_id || "-"}`);
    if (PAGE === "overview") {
      await loadPlatformOverview(true);
    } else if (PAGE === "tasks") {
      await loadPlatformTasks(true);
      state.selectedTaskId = created.task_id || "";
      if (state.selectedTaskId) {
        await loadPlatformTaskDetail(state.selectedTaskId, true);
      }
    }
  } catch (error) {
    alert(`从确认生成任务失败：${error.message}`);
  }
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

async function loadKnowledgeBaseRegistry(silent = false) {
  const pill = el("registry-pill");
  if (!pill) return;

  if (!state.apiKey) {
    if (!silent) {
      alert("先输入 API Key 再加载注册表。");
    }
    pill.textContent = "未加载";
    setText("registry-save-state", "未加载");
    return;
  }

  const data = await fetchJson("/knowledge-base-registry", {
    headers: { Authorization: `Bearer ${state.apiKey}` },
  });
  data.registry_path = "/data/kb/operations/knowledge_bases.json";
  renderKnowledgeBaseRegistry(data);
}

async function saveKnowledgeBaseRegistryItem() {
  if (!requireApiKey()) return;
  const payload = buildRegistryPayload();
  if (!payload.knowledge_base_id || !payload.name) {
    alert("知识库 ID 和名称不能为空。");
    return;
  }

  const currentId = (el("registry-current-id")?.value || "").trim();
  const method = currentId ? "PUT" : "POST";
  const url = currentId ? `/knowledge-base-registry/${encodeURIComponent(currentId)}` : "/knowledge-base-registry";
  const button = el("save-registry-item");
  if (!button) return;

  button.disabled = true;
  button.textContent = "保存中...";

  try {
    const data = await fetchJson(url, {
      method,
      headers: { Authorization: `Bearer ${state.apiKey}` },
      body: JSON.stringify(payload),
    });
    data.registry_path = "/data/kb/operations/knowledge_bases.json";
    renderKnowledgeBaseRegistry(data);
    fillRegistryForm((data.items || []).find((item) => item.knowledge_base_id === payload.knowledge_base_id) || payload);
    alert("知识库已保存。");
  } catch (error) {
    alert(`保存失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "保存知识库";
  }
}

async function deleteKnowledgeBaseRegistryItem(kbId) {
  if (!requireApiKey()) return;
  const ok = confirm(`确认删除知识库 ${kbId} 吗？`);
  if (!ok) return;
  try {
    const data = await fetchJson(`/knowledge-base-registry/${encodeURIComponent(kbId)}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    data.registry_path = "/data/kb/operations/knowledge_bases.json";
    renderKnowledgeBaseRegistry(data);
    resetRegistryForm();
    await loadKnowledgeBases();
  } catch (error) {
    alert(`删除失败：${error.message}`);
  }
}

async function activateKnowledgeBaseRegistryItem(kbId) {
  if (!requireApiKey()) return;
  const item = (state.registry?.items || []).find((row) => row.knowledge_base_id === kbId);
  const ok = confirm(`切换到 ${kbId} 后，原始文件、流程配置和检索都会跟着当前知识库走。${item?.doc_count || item?.chunk_count ? " 当前库已有数据，继续切换？" : " 该库还没有数据，是否继续？"}`);
  if (!ok) return;
  try {
    const data = await fetchJson(`/knowledge-base-registry/${encodeURIComponent(kbId)}/activate`, {
      method: "POST",
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    data.registry_path = "/data/kb/operations/knowledge_bases.json";
    renderKnowledgeBaseRegistry(data);
    await loadKnowledgeBases();
  } catch (error) {
    alert(`设为当前失败：${error.message}`);
  }
}

async function initializeKnowledgeBaseRegistryItem(kbId) {
  if (!requireApiKey()) return;
  const item = (state.registry?.items || []).find((row) => row.knowledge_base_id === kbId);
  const ok = confirm(`初始化 ${kbId} 的目录和默认配置吗？这会创建原始文件、chunk、向量和运行目录，便于后续上传和预处理。`);
  if (!ok) return;
  try {
    const data = await fetchJson(`/knowledge-base-registry/${encodeURIComponent(kbId)}/initialize`, {
      method: "POST",
      headers: { Authorization: `Bearer ${state.apiKey}` },
    });
    data.registry_path = "/data/kb/operations/knowledge_bases.json";
    renderKnowledgeBaseRegistry(data);
    await loadKnowledgeBases();
    alert(`初始化完成：${item?.name || kbId}`);
  } catch (error) {
    alert(`初始化失败：${error.message}`);
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
  el("refresh-daily-report")?.addEventListener("click", () => loadDailyAutomation(true));
  el("run-daily-report-now")?.addEventListener("click", runDailyAutomationNow);
  el("load-kbs")?.addEventListener("click", loadKnowledgeBases);
  el("run-query")?.addEventListener("click", runQuery);
  el("save-key")?.addEventListener("click", async () => {
    state.apiKey = (el("api-key")?.value || "").trim();
    localStorage.setItem("kb_api_key", state.apiKey);
    alert("API Key 已保存到本地浏览器。");
    try {
      await loadKnowledgeBases();
      await loadDailyAutomation(true);
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
    renderDailyReportAutomationEmpty("输入 API Key 后可查看");
  });
}

function bindOverviewEvents() {
  el("refresh-overview")?.addEventListener("click", () => loadPlatformOverview(true));
  el("refresh-overview-quick")?.addEventListener("click", () => loadPlatformOverview(true));
  el("load-overview")?.addEventListener("click", () => loadPlatformOverview());
  el("save-key")?.addEventListener("click", async () => {
    state.apiKey = (el("api-key")?.value || "").trim();
    localStorage.setItem("kb_api_key", state.apiKey);
    alert("API Key 已保存到本地浏览器。");
    try {
      await loadPlatformOverview(true);
    } catch (error) {
      alert(`加载总览失败：${error.message}`);
    }
  });
  el("overview-confirmations")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-confirmation-task]");
    if (!button) return;
    const confirmationId = button.getAttribute("data-confirmation-task") || "";
    const item = (state.overview?.confirmations || []).find((row) => row.confirmation_id === confirmationId);
    if (!item) {
      alert("没有找到对应的确认记录。");
      return;
    }
    createTaskFromConfirmationRecord(confirmationId, todayIsoDate(), item.suggestion?.title || "");
  });
}

function bindTaskEvents() {
  el("save-key")?.addEventListener("click", async () => {
    state.apiKey = (el("api-key")?.value || "").trim();
    localStorage.setItem("kb_api_key", state.apiKey);
    alert("API Key 已保存到本地浏览器。");
    try {
      await loadPlatformTasks(true);
    } catch (error) {
      alert(`加载任务失败：${error.message}`);
    }
  });
  el("load-tasks")?.addEventListener("click", async () => {
    await loadPlatformTasks();
  });
  el("refresh-tasks")?.addEventListener("click", async () => {
    await loadPlatformTasks(true);
  });
  el("export-task-markdown")?.addEventListener("click", exportTaskListMarkdown);
  el("save-task-report")?.addEventListener("click", savePlatformTaskReport);
  el("save-task-history-report")?.addEventListener("click", savePlatformTaskHistoryReport);
  el("save-task-log-report")?.addEventListener("click", savePlatformTaskLogReport);
  el("save-task-due-report")?.addEventListener("click", savePlatformTaskDueReport);
  el("save-task-weekly-report")?.addEventListener("click", savePlatformTaskWeeklyReport);
  el("run-task-automation-now")?.addEventListener("click", runPlatformTaskAutomationNow);
  el("refresh-task-detail")?.addEventListener("click", async () => {
    if (state.selectedTaskId) {
      await loadPlatformTaskDetail(state.selectedTaskId);
    }
  });
  el("refresh-task-logs")?.addEventListener("click", async () => {
    await loadPlatformTaskLogs(state.selectedTaskId, true);
  });
  el("add-task-log")?.addEventListener("click", addCurrentTaskLog);
  el("export-task-detail-markdown")?.addEventListener("click", exportSelectedTaskMarkdown);
  el("transition-task")?.addEventListener("click", transitionCurrentTask);
  el("create-task-from-confirmation")?.addEventListener("click", createTaskFromConfirmation);
  el("fill-confirmation-example")?.addEventListener("click", () => {
    setInputValue("task-confirmation-id", "ecf_example");
    setInputValue("task-confirmation-date", todayIsoDate());
    setInputValue("task-create-owner", "项目负责人");
    setInputValue("task-create-due-date", todayIsoDate());
    setInputValue("task-create-note", "由确认记录直接转入任务台账，便于后续跟进。");
  });
  el("clear-confirmation-form")?.addEventListener("click", clearPlatformTaskCreateForm);
  el("task-table")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-task-open]");
    if (!button) return;
    const taskId = button.getAttribute("data-task-open") || "";
    if (taskId) {
      state.selectedTaskId = taskId;
      loadPlatformTaskDetail(taskId);
    }
  });
  el("task-confirmations")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-task-confirmation]");
    if (!button) return;
    const confirmationId = button.getAttribute("data-task-confirmation") || "";
    const item = state.taskConfirmations.find((row) => row.confirmation_id === confirmationId);
    if (!item) {
      alert("没有找到对应的确认记录。");
      return;
    }
    createTaskFromConfirmationRecord(confirmationId, (el("task-date")?.value || "").trim() || todayIsoDate(), item.suggestion?.title || "");
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

function bindRegistryEvents() {
  el("save-registry-key")?.addEventListener("click", async () => {
    state.apiKey = (el("api-key")?.value || "").trim();
    localStorage.setItem("kb_api_key", state.apiKey);
    alert("API Key 已保存到本地浏览器。");
    try {
      await loadKnowledgeBaseRegistry(true);
    } catch (error) {
      alert(`加载注册表失败：${error.message}`);
    }
  });
  el("load-registry")?.addEventListener("click", async () => {
    await loadKnowledgeBaseRegistry();
  });
  el("refresh-registry")?.addEventListener("click", async () => {
    await loadKnowledgeBaseRegistry(true);
  });
  el("save-registry-item")?.addEventListener("click", saveKnowledgeBaseRegistryItem);
  el("new-registry-item")?.addEventListener("click", resetRegistryForm);
  el("reset-registry-form")?.addEventListener("click", resetRegistryForm);
  el("registry-table")?.addEventListener("click", (event) => {
    const edit = event.target.closest("[data-registry-edit]");
    if (edit) {
      const kbId = edit.getAttribute("data-registry-edit") || "";
      const item = (state.registry?.items || []).find((row) => row.knowledge_base_id === kbId);
      if (item) fillRegistryForm(item);
      return;
    }
    const activate = event.target.closest("[data-registry-activate]");
    if (activate) {
      const kbId = activate.getAttribute("data-registry-activate") || "";
      activateKnowledgeBaseRegistryItem(kbId);
      return;
    }
    const initialize = event.target.closest("[data-registry-initialize]");
    if (initialize) {
      const kbId = initialize.getAttribute("data-registry-initialize") || "";
      initializeKnowledgeBaseRegistryItem(kbId);
      return;
    }
    const remove = event.target.closest("[data-registry-delete]");
    if (remove) {
      const kbId = remove.getAttribute("data-registry-delete") || "";
      deleteKnowledgeBaseRegistryItem(kbId);
    }
  });
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

  if (PAGE === "registry") {
    bindRegistryEvents();
    if (state.apiKey) {
      try {
        await loadKnowledgeBaseRegistry(true);
      } catch {
        setText("registry-save-state", "加载失败");
      }
    } else {
      setText("registry-save-state", "输入 API Key 后可加载");
    }
    return;
  }

  if (PAGE === "overview") {
    bindOverviewEvents();
    if (state.apiKey) {
      await loadPlatformOverview(true);
    } else {
      renderOverviewEmpty("输入 API Key 后可查看");
    }
    return;
  }

  if (PAGE === "tasks") {
    bindTaskEvents();
    const taskDate = el("task-date");
    if (taskDate && !taskDate.value) {
      taskDate.value = todayIsoDate();
    }
    if (state.apiKey) {
      await loadPlatformTasks(true);
    } else {
      renderPlatformTaskDetailEmpty("输入 API Key 后可查看");
      setHtml("task-table", '<tr><td colspan="5" class="placeholder">输入 API Key 后可加载任务</td></tr>');
    }
    return;
  }

  bindHomeEvents();
  await loadHealth();
  if (state.apiKey) {
    await loadDailyAutomation(true);
  } else {
    renderDailyReportAutomationEmpty("输入 API Key 后可查看");
  }
}

bootstrap();
