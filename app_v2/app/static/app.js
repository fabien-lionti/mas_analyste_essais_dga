const state = {
  analyses: [],
  analysis: null,
  files: [],
  events: [],
  channelStatus: null,
  recurrent: [],
  anomalyFiles: [],
  anomalies: [],
  selectedChannels: new Set(),
  validatedStructure: null,
  recurrentFilter: "",
  presets: {},
  channelAnalysisRunning: false,
  channelAnalysisTaskId: null,
  channelAnalysisPollId: 0,
  resamplingRunning: false,
  resamplingTaskId: null,
  resamplingPollId: 0,
  workflowStep: "sources",
  explorationFiles: [],
  explorationChannels: [],
  explorationFileId: "",
};

const $ = id => document.getElementById(id);

function setStatus(message, kind = "") {
  const status = $("statusBar");
  status.textContent = message;
  status.className = `status-bar ${kind}`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = await response.text();
    try {
      detail = JSON.parse(detail).detail || detail;
    } catch (_) {
      // keep raw detail
    }
    throw new Error(detail);
  }
  return response.json();
}

function currentAnalysisId() {
  return state.analysis?.analysis_id || "";
}

function renderTable(containerId, columns, rows, emptyText = "Aucune donnée") {
  const container = $(containerId);
  if (!rows || !rows.length) {
    container.innerHTML = `<div class="empty">${escapeHtml(emptyText)}</div>`;
    return;
  }
  container.innerHTML = `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>${columns.map(col => `<th>${escapeHtml(col.label)}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${rows.map(row => `
            <tr>
              ${columns.map(col => `<td>${col.render ? col.render(row) : escapeHtml(row[col.key])}</td>`).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderKpis() {
  const summary = state.channelStatus?.summary || {};
  const kpis = [
    ["Analyse", state.analysis?.name || "-"],
    ["Fichiers DXD", state.files.length],
    ["Canaux récurrents", state.recurrent.length || summary.recurrent_channel_count || 0],
    ["Fichiers anomalies", state.anomalyFiles.length],
    ["Statut canaux", state.channelStatus?.status || "not_started"],
  ];
  $("kpiGrid").innerHTML = kpis.map(([label, value]) => `
    <div class="kpi">
      <div class="label">${escapeHtml(label)}</div>
      <div class="value">${escapeHtml(value)}</div>
    </div>
  `).join("");
}

function canUseChannelWorkflow() {
  return Boolean(currentAnalysisId() && state.files.length);
}

function canUseSamplingWorkflow() {
  return Boolean(canUseChannelWorkflow() && state.selectedChannels.size);
}

function showWorkflowStep(step) {
  let target = step;
  if (target === "channels" && !canUseChannelWorkflow()) target = "sources";
  if (target === "sampling" && !canUseSamplingWorkflow()) target = canUseChannelWorkflow() ? "channels" : "sources";
  state.workflowStep = target;
  document.querySelectorAll("[data-workflow-step]").forEach(button => {
    button.classList.toggle("active", button.dataset.workflowStep === target);
  });
  document.querySelectorAll(".workflow-step").forEach(item => item.classList.remove("active"));
  $(`workflow-${target}`)?.classList.add("active");
}

function renderWorkflowState() {
  const stateNode = $("workflowSourceState");
  if (stateNode) {
    const files = state.files.length;
    const name = state.analysis?.name || "Aucune analyse";
    stateNode.textContent = files
      ? `${files} fichier(s) DXD identifié(s) pour ${name}`
      : "Aucun périmètre DXD initialisé";
  }
  const channelsTab = $("workflowChannelsTab");
  if (channelsTab) {
    channelsTab.disabled = !canUseChannelWorkflow();
  }
  const samplingTab = $("workflowSamplingTab");
  if (samplingTab) {
    samplingTab.disabled = !canUseSamplingWorkflow();
  }
  const finalizeButton = $("finalizeAnalysisBtn");
  if (finalizeButton) {
    finalizeButton.disabled = state.resamplingRunning || !canUseSamplingWorkflow();
  }
  showWorkflowStep(state.workflowStep);
}

function renderAnalyses() {
  renderAnalysisChoice();
}

function analysisSummaryRows() {
  const sampling = state.analysis?.config?.sampling || {};
  const exportedCount = state.files.filter(file => file.resampled_json_path).length;
  return [
    ["Analyse", state.analysis?.name || "-"],
    ["Type", state.analysis?.kind || "-"],
    ["Fichiers DXD", state.files.length],
    ["JSON exportés", exportedCount],
    ["Canaux sélectionnés", state.validatedStructure?.selected_channels?.length || state.selectedChannels.size || 0],
    ["Canaux récurrents", state.recurrent.length || state.channelStatus?.summary?.recurrent_channel_count || 0],
    ["Fréquence sampling", sampling.target_frequency_hz ? `${sampling.target_frequency_hz} Hz` : "-"],
    ["Méthode interpolation", sampling.method || "-"],
    ["Dossier JSON", sampling.resampled_json_dir || "-"],
  ];
}

function renderAnalysisChoice() {
  const list = $("analysisChoiceList");
  const summary = $("analysisChoiceSummary");
  if (!list || !summary) return;
  if (!state.analyses.length) {
    list.innerHTML = '<div class="empty">Aucune analyse disponible</div>';
  } else {
    list.innerHTML = `
      <div class="choice-list">
        ${state.analyses.map(item => `
          <div class="choice-row ${item.analysis_id === currentAnalysisId() ? "active" : ""}">
            <button type="button" class="choice-item" data-analysis-id="${escapeHtml(item.analysis_id)}">
              <span>${escapeHtml(item.name)}</span>
              <span class="muted">${escapeHtml(item.kind)}</span>
            </button>
            <button type="button" class="danger choice-delete" data-delete-analysis-id="${escapeHtml(item.analysis_id)}">Supprimer</button>
          </div>
        `).join("")}
      </div>
    `;
  }
  summary.innerHTML = `
    <div class="summary-grid">
      ${analysisSummaryRows().map(([label, value]) => `
        <div>
          <div class="label">${escapeHtml(label)}</div>
          <div class="value">${escapeHtml(value)}</div>
        </div>
      `).join("")}
    </div>
  `;
}

function setExplorationStatus(message) {
  const node = $("explorationStatus");
  if (node) node.textContent = message;
}

function plotlyLayout(title, ytitle = "") {
  return {
    title: { text: title, font: { color: "#17202c", size: 13 } },
    paper_bgcolor: "#ffffff",
    plot_bgcolor: "#fbfcfe",
    font: { color: "#17202c" },
    margin: { l: 58, r: 24, t: 42, b: 52 },
    xaxis: { gridcolor: "#e5eaf1", zerolinecolor: "#d7dee8" },
    yaxis: { title: ytitle, gridcolor: "#e5eaf1", zerolinecolor: "#d7dee8" },
    legend: { orientation: "h", y: -0.2 },
  };
}

function renderExplorationFileOptions() {
  const select = $("explorationFileSelect");
  if (!select) return;
  select.innerHTML = state.explorationFiles.length
    ? state.explorationFiles.map(file => `
      <option value="${escapeHtml(file.file_id)}">${escapeHtml(file.resampled_json_name || file.source_dxd_name)}</option>
    `).join("")
    : '<option value="">Aucun JSON exporté</option>';
  if (state.explorationFileId && state.explorationFiles.some(file => file.file_id === state.explorationFileId)) {
    select.value = state.explorationFileId;
  } else if (state.explorationFiles.length) {
    state.explorationFileId = state.explorationFiles[0].file_id;
    select.value = state.explorationFileId;
  } else {
    state.explorationFileId = "";
  }
}

function renderExplorationChannelOptions(previous = []) {
  const select = $("explorationChannelSelect");
  if (!select) return;
  select.innerHTML = state.explorationChannels.map(channel => `
    <option value="${escapeHtml(channel.value)}">${escapeHtml(channel.label || channel.value)}</option>
  `).join("");
  const selected = previous.length ? previous : state.explorationChannels.slice(0, 2).map(channel => channel.value);
  Array.from(select.options).forEach(option => {
    option.selected = selected.includes(option.value);
  });
}

function selectedExplorationChannels() {
  return Array.from($("explorationChannelSelect")?.selectedOptions || [])
    .map(option => option.value)
    .slice(0, 2);
}

function clampExplorationChannelSelection() {
  const select = $("explorationChannelSelect");
  if (!select) return;
  const selected = Array.from(select.options)
    .filter(option => option.selected)
    .map(option => option.value);
  if (selected.length <= 2) return;
  const keep = new Set(selected.slice(-2));
  Array.from(select.options).forEach(option => {
    option.selected = keep.has(option.value);
  });
  setExplorationStatus("Maximum 2 canaux affichables en même temps.");
}

function renderExplorationLabels() {
  const select = $("explorationLabelSelect");
  if (!select) return;
  select.innerHTML = '<option value="">Tous les labels</option>';
}

function drawEmptyPlot(plotId, message) {
  const node = $(plotId);
  if (!node || !window.Plotly) return;
  Plotly.react(plotId, [], {
    ...plotlyLayout(message),
    annotations: [{
      text: message,
      x: 0.5,
      y: 0.5,
      xref: "paper",
      yref: "paper",
      showarrow: false,
      font: { color: "#657386", size: 13 },
    }],
  }, { responsive: true, displaylogo: false });
}

function drawSignalPlot(payload) {
  if (!window.Plotly) return;
  const traces = (payload.channels || []).map((channel, index) => {
    const axisName = index === 0 || !$("explorationMultiAxisInput").checked ? "y" : `y${index + 1}`;
    return {
      type: "scattergl",
      mode: "lines",
      name: channel.name,
      x: payload.time || [],
      y: channel.values || [],
      yaxis: axisName,
      line: { color: index === 0 ? "#1368ce" : "#15803d", width: 1.5 },
      hovertemplate: "t=%{x:.2f}s<br>val=%{y:.4g}<extra></extra>",
    };
  });
  const layout = plotlyLayout("Signaux rééchantillonnés");
  layout.xaxis.title = "temps (s)";
  if (traces.length > 1 && $("explorationMultiAxisInput").checked) {
    layout.yaxis2 = {
      title: traces[1].name,
      overlaying: "y",
      side: "right",
      gridcolor: "#e5eaf1",
      zerolinecolor: "#d7dee8",
    };
  }
  Plotly.react("explorationSignalPlot", traces, layout, { responsive: true, displaylogo: false });
}

function drawTrajectoryPlot(payload) {
  if (!window.Plotly) return;
  const items = payload.items || [];
  if (!items.length) {
    drawEmptyPlot("explorationTrajectoryPlot", "Trajectoire GPS indisponible");
    return;
  }
  const trace = {
    type: "scattergl",
    mode: "lines",
    name: "trajectoire",
    x: items.map(item => item.lon),
    y: items.map(item => item.lat),
    text: items.map(item => `t=${Number(item.time || 0).toFixed(1)}s`),
    line: { color: "#1368ce", width: 2 },
    hovertemplate: "lon=%{x:.6f}<br>lat=%{y:.6f}<br>%{text}<extra></extra>",
  };
  const layout = plotlyLayout("Trajectoire GPS", "latitude");
  layout.xaxis.title = "longitude";
  layout.yaxis.scaleanchor = "x";
  layout.yaxis.scaleratio = 1;
  Plotly.react("explorationTrajectoryPlot", [trace], layout, { responsive: true, displaylogo: false });
}

async function loadExplorationFiles() {
  const analysisId = currentAnalysisId();
  if (!analysisId) return;
  try {
    const payload = await api(`/api/analyses/${encodeURIComponent(analysisId)}/exploration/files`);
    state.explorationFiles = payload.items || [];
    renderExplorationFileOptions();
    renderExplorationLabels();
    if (state.explorationFileId) {
      await loadExplorationChannels();
      await refreshExploration();
    } else {
      setExplorationStatus("Aucun JSON exporté pour cette analyse.");
      drawEmptyPlot("explorationSignalPlot", "Aucun signal");
      drawEmptyPlot("explorationTrajectoryPlot", "Aucune trajectoire");
    }
  } catch (error) {
    state.explorationFiles = [];
    renderExplorationFileOptions();
    setExplorationStatus(error.message || String(error));
  }
}

async function loadExplorationChannels() {
  const analysisId = currentAnalysisId();
  const fileId = state.explorationFileId || $("explorationFileSelect")?.value;
  if (!analysisId || !fileId) return;
  const previous = selectedExplorationChannels();
  const payload = await api(`/api/analyses/${encodeURIComponent(analysisId)}/exploration/files/${encodeURIComponent(fileId)}/signals/options`);
  state.explorationChannels = (payload.items || []).filter(item => item.available);
  renderExplorationChannelOptions(previous);
}

async function refreshExploration() {
  const analysisId = currentAnalysisId();
  const fileId = state.explorationFileId || $("explorationFileSelect")?.value;
  if (!analysisId || !fileId) {
    setExplorationStatus("Sélectionne une analyse avec des JSON exportés.");
    return;
  }
  if (!state.explorationChannels.length) {
    await loadExplorationChannels();
  }
  const channels = selectedExplorationChannels();
  const maxPoints = $("explorationMaxPointsInput").value || "8000";
  const params = new URLSearchParams({ max_points: maxPoints });
  if (channels.length) {
    params.set("channels", channels.join(","));
  }
  setExplorationStatus("Chargement des graphes...");
  const [series, trajectory] = await Promise.all([
    api(`/api/analyses/${encodeURIComponent(analysisId)}/exploration/files/${encodeURIComponent(fileId)}/series?${params.toString()}`),
    api(`/api/analyses/${encodeURIComponent(analysisId)}/exploration/files/${encodeURIComponent(fileId)}/trajectory?max_points=${encodeURIComponent(maxPoints)}`),
  ]);
  drawSignalPlot(series);
  drawTrajectoryPlot(trajectory);
  const currentFile = state.explorationFiles.find(file => file.file_id === fileId);
  setExplorationStatus([
    `Fichier: ${currentFile?.resampled_json_name || currentFile?.source_dxd_name || "-"}`,
    `Canaux: ${channels.length ? channels.join(", ") : "-"}`,
    `Filtre segments: ${$("explorationSegmentSourceSelect").value}`,
    `Label: ${$("explorationLabelSelect").value || "Tous"}`,
  ].join("\n"));
}

async function refreshExplorationFromChannelSelection() {
  try {
    clampExplorationChannelSelection();
    await refreshExploration();
  } catch (error) {
    setExplorationStatus(`Erreur canaux:\n${error.message || String(error)}`);
    setStatus(error.message || String(error), "error");
  }
}

async function goToRelativeExplorationFile(delta) {
  if (!state.explorationFiles.length) return;
  const current = state.explorationFileId || $("explorationFileSelect").value;
  const index = Math.max(0, state.explorationFiles.findIndex(file => file.file_id === current));
  const nextIndex = Math.max(0, Math.min(state.explorationFiles.length - 1, index + delta));
  const next = state.explorationFiles[nextIndex];
  if (!next || next.file_id === current) return;
  state.explorationFileId = next.file_id;
  $("explorationFileSelect").value = next.file_id;
  await loadExplorationChannels();
  await refreshExploration();
}

function renderFiles() {
  renderTable(
    "filesTable",
    [
      { key: "source_dxd_name", label: "DXD" },
      { key: "status", label: "Statut", render: row => `<span class="pill ok">${escapeHtml(row.status)}</span>` },
      { key: "file_id", label: "file_id", render: row => `<span class="code">${escapeHtml(row.file_id)}</span>` },
      { key: "source_dxd_path", label: "Chemin", render: row => `<span class="code">${escapeHtml(row.source_dxd_path)}</span>` },
      { key: "size", label: "Taille", render: row => escapeHtml(row.metadata?.size_bytes || "") },
    ],
    state.files,
    "Aucun fichier rattaché à l'analyse"
  );
}

function renderEvents() {
  renderTable(
    "eventsTable",
    [
      { key: "created_at", label: "Date" },
      { key: "level", label: "Niveau", render: row => `<span class="pill">${escapeHtml(row.level)}</span>` },
      { key: "event_type", label: "Type" },
      { key: "message", label: "Message" },
    ],
    state.events,
    "Aucun événement"
  );
}

function renderPresets() {
  const select = $("presetSelect");
  if (!select) return;
  const entries = Object.entries(state.presets || {});
  const previous = select.value;
  select.innerHTML = entries.map(([key, item]) => `
    <option value="${escapeHtml(key)}">${escapeHtml(item.label || key)}</option>
  `).join("");
  if (previous && entries.some(([key]) => key === previous)) {
    select.value = previous;
  } else if (entries.some(([key]) => key === "minimum")) {
    select.value = "minimum";
  }
  updatePresetOptions(false);
}

function renderChannelStatus() {
  const savedChannels = state.validatedStructure?.selected_channels || [];
  const activeChannels = state.selectedChannels.size
    ? Array.from(state.selectedChannels)
    : savedChannels;
  const activeChannelsHtml = activeChannels.length
    ? `
      <div class="channel-structure-list">
        ${activeChannels.map(channel => `<span class="channel-chip">${escapeHtml(channel)}</span>`).join("")}
      </div>
    `
    : '<div class="empty compact-empty">Aucun canal actif</div>';
  if (!state.validatedStructure) {
    $("channelStatus").innerHTML = `
      <div class="stack">
        <div class="empty compact-empty">Aucune structure sauvegardée</div>
        <div>
          <h3>Structure active</h3>
          <div class="muted">Sélection en cours: <strong>${escapeHtml(activeChannels.length)}</strong> canal(aux)</div>
          ${activeChannelsHtml}
        </div>
      </div>
    `;
    return;
  }
  $("channelStatus").innerHTML = `
    <div class="stack">
      <div><span class="pill ok">${escapeHtml(state.validatedStructure.status)}</span></div>
      <div>Canaux sélectionnés: <strong>${escapeHtml(state.validatedStructure.selected_channels?.length || 0)}</strong></div>
      <div>Normalisation: <strong>${state.validatedStructure.normalize_names ? "oui" : "non"}</strong></div>
      <div>Mise à jour: <strong>${escapeHtml(state.validatedStructure.updated_at || "-")}</strong></div>
      <div>
        <h3>Structure active</h3>
        <div class="muted">Canaux actifs: <strong>${escapeHtml(activeChannels.length)}</strong></div>
        ${activeChannelsHtml}
      </div>
    </div>
  `;
}

function renderChannels() {
  const filter = state.recurrentFilter.trim().toLowerCase();
  const filteredRecurrent = state.recurrent.filter(row => {
    if (!filter) return true;
    return [row.channel, row.source_name]
      .some(value => String(value || "").toLowerCase().includes(filter));
  });
  const countNode = $("recurrentCount");
  if (countNode) {
    countNode.textContent = `${filteredRecurrent.length} canal(aux) filtré(s), ${state.recurrent.length} total`;
  }
  renderTable(
    "recurrentTable",
    [
      {
        key: "selected",
        label: "",
        render: row => `<input type="checkbox" class="channel-select" data-channel="${escapeHtml(row.channel)}" ${state.selectedChannels.has(row.channel) ? "checked" : ""}>`,
      },
      { key: "channel", label: "Canal normalisé" },
      { key: "source_name", label: "Nom DXD" },
      { key: "file_count", label: "Fichiers avec canal" },
      { key: "total_files", label: "Fichiers analysés" },
    ],
    filteredRecurrent,
    "Aucun canal récurrent calculé. Lance un scan de structure DXD."
  );
  document.querySelectorAll(".channel-select").forEach(input => {
    input.addEventListener("change", () => {
      if (input.checked) {
        state.selectedChannels.add(input.dataset.channel);
      } else {
        state.selectedChannels.delete(input.dataset.channel);
      }
      renderChannelStatus();
    });
  });
  renderTable(
    "anomalyFilesTable",
    [
      {
        key: "source_dxd_name",
        label: "Fichier",
        render: row => `<button type="button" class="link-button anomaly-file" data-file-id="${escapeHtml(row.file_id)}">${escapeHtml(row.source_dxd_name)}</button>`,
      },
      { key: "anomaly_count", label: "Anomalies" },
      { key: "status", label: "Statut", render: row => `<span class="pill error">${escapeHtml(row.status)}</span>` },
    ],
    state.anomalyFiles,
    "Aucun fichier anomalie"
  );
  document.querySelectorAll(".anomaly-file").forEach(button => {
    button.addEventListener("click", () => wrapAction(() => loadAnomalyDetails(button.dataset.fileId), "Détail anomalies chargé")());
  });
  renderTable(
    "anomalyDetailTable",
    [
      { key: "source_dxd_name", label: "Fichier" },
      { key: "channel", label: "Canal" },
      { key: "details", label: "Détails" },
    ],
    state.anomalies,
    "Sélectionne un fichier anomalie"
  );
  renderChannelStatus();
}

function updatePresetOptions(force = true) {
  const selected = $("presetSelect")?.value || "minimum";
  const preset = state.presets?.[selected];
  const description = $("presetDescription");
  const textarea = $("targetChannelsInput");
  if (description) {
    const count = preset?.channels?.length || 0;
    description.textContent = preset
      ? `${preset.description || ""} ${count} canal(aux).`.trim()
      : "";
  }
  if (textarea && preset?.channels && (force || !textarea.value.trim())) {
    textarea.value = preset.channels.join("\n");
  }
}

function targetChannelsFromOptions() {
  if (!$("targetChannelsInput")) return [];
  return $("targetChannelsInput").value
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean);
}

function setChannelAnalysisRunning(isRunning, task = null) {
  state.channelAnalysisRunning = isRunning;
  if (task?.task_id) {
    state.channelAnalysisTaskId = task.task_id;
  }
  const progress = $("channelAnalysisProgress");
  const analyzeButton = $("analyzeChannelsBtn");
  const cancelButton = $("cancelChannelAnalysisBtn");
  const labelNode = $("channelAnalysisProgressLabel");
  const fillNode = progress?.querySelector(".progress-fill");
  if (!progress || !analyzeButton || !cancelButton || !labelNode || !fillNode) return;
  progress.classList.toggle("hidden", !isRunning);
  analyzeButton.disabled = isRunning;
  cancelButton.disabled = !isRunning || !state.channelAnalysisTaskId;
  const percent = Math.max(0, Math.min(Number(task?.percent ?? 0), 100));
  fillNode.style.width = `${percent}%`;
  labelNode.textContent = isRunning
    ? `${percent.toFixed(0)} % · ${task?.message || "Analyse"}`
    : "Préparation";
  if (!isRunning) {
    state.channelAnalysisTaskId = null;
  }
}

function setResamplingRunning(isRunning, task = null) {
  state.resamplingRunning = isRunning;
  if (task?.task_id) {
    state.resamplingTaskId = task.task_id;
  }
  const progress = $("resamplingProgress");
  const finalizeButton = $("finalizeAnalysisBtn");
  const cancelButton = $("cancelResamplingBtn");
  const labelNode = $("resamplingProgressLabel");
  const fillNode = progress?.querySelector(".progress-fill");
  if (!progress || !finalizeButton || !cancelButton || !labelNode || !fillNode) return;
  progress.classList.toggle("hidden", !isRunning);
  finalizeButton.disabled = isRunning || !canUseSamplingWorkflow();
  cancelButton.disabled = !isRunning || !state.resamplingTaskId;
  const percent = Math.max(0, Math.min(Number(task?.percent ?? 0), 100));
  fillNode.style.width = `${percent}%`;
  labelNode.textContent = isRunning
    ? `${percent.toFixed(0)} % · ${task?.message || "Export"}`
    : "Préparation";
  if (!isRunning) {
    state.resamplingTaskId = null;
  }
}

function renderAll() {
  renderAnalyses();
  renderKpis();
  renderFiles();
  renderEvents();
  renderPresets();
  renderChannels();
  renderWorkflowState();
  renderAnalysisChoice();
}

async function loadAnalyses() {
  const payload = await api("/api/analyses");
  state.analyses = payload.items || [];
  if (!state.analysis && state.analyses.length) {
    state.analysis = state.analyses[0];
  }
  renderAll();
}

async function loadAnalysis(analysisId = currentAnalysisId()) {
  if (!analysisId) {
    state.analysis = null;
    state.files = [];
    state.events = [];
    state.channelStatus = null;
    state.recurrent = [];
    state.anomalyFiles = [];
    state.anomalies = [];
    state.validatedStructure = null;
    renderAll();
    return;
  }
  state.analysis = await api(`/api/analyses/${encodeURIComponent(analysisId)}`);
  state.selectedChannels = new Set();
  state.anomalies = [];
  await Promise.all([loadFiles(), loadEvents(), loadChannels()]);
  renderAll();
  await loadExplorationFiles();
  resumeCurrentChannelAnalysis(analysisId);
  resumeCurrentResampling(analysisId);
}

async function loadFiles() {
  const analysisId = currentAnalysisId();
  if (!analysisId) return;
  const payload = await api(`/api/analyses/${encodeURIComponent(analysisId)}/files`);
  state.files = payload.items || [];
}

async function loadEvents() {
  const analysisId = currentAnalysisId();
  if (!analysisId) return;
  const payload = await api(`/api/analyses/${encodeURIComponent(analysisId)}/events`);
  state.events = payload.items || [];
}

async function loadPresets() {
  const analysisId = currentAnalysisId();
  if (!analysisId) {
    state.presets = {};
    return;
  }
  const payload = await api(`/api/analyses/${encodeURIComponent(analysisId)}/channels/presets`);
  state.presets = payload.items || {};
}

async function loadChannels() {
  const analysisId = currentAnalysisId();
  if (!analysisId) return;
  await loadPresets();
  const [status, recurrent, anomalyFiles, validated] = await Promise.all([
    api(`/api/analyses/${encodeURIComponent(analysisId)}/channels/status`),
    api(`/api/analyses/${encodeURIComponent(analysisId)}/channels/recurrent`),
    api(`/api/analyses/${encodeURIComponent(analysisId)}/channels/anomalies/files`),
    api(`/api/analyses/${encodeURIComponent(analysisId)}/channels/validated-structure`),
  ]);
  state.channelStatus = status;
  state.recurrent = recurrent.items || [];
  state.anomalyFiles = anomalyFiles.items || [];
  state.validatedStructure = validated.structure || null;
  if (!state.selectedChannels.size) {
    const initial = state.validatedStructure?.selected_channels || state.recurrent.map(row => row.channel);
    state.selectedChannels = new Set(initial);
  }
}

async function createAnalysis() {
  const name = $("analysisNameInput").value.trim();
  if (!name) throw new Error("Nom d'analyse requis");
  const sourceDxdDir = $("sourceDxdDirInput").value.trim();
  const payload = await api("/api/analyses", {
    method: "POST",
    body: JSON.stringify({
      name,
      kind: $("analysisKindInput").value,
      source_dxd_dir: sourceDxdDir || null,
      config: { source: "ui" },
    }),
  });
  state.analysis = payload;
  if (sourceDxdDir && $("discoverOnCreateInput").checked) {
    await api(`/api/analyses/${encodeURIComponent(payload.analysis_id)}/files/discover-dxd`, {
      method: "POST",
      body: JSON.stringify({
        dxd_dir: sourceDxdDir,
        recursive: $("recursiveInput").checked,
      }),
    });
  }
  await loadAnalyses();
  await loadAnalysis(payload.analysis_id);
  if (state.files.length) {
    showWorkflowStep("channels");
  }
}

async function deleteAnalysisById(analysisId) {
  if (!analysisId) throw new Error("Aucune analyse sélectionnée");
  const analysis = state.analyses.find(item => item.analysis_id === analysisId);
  const name = analysis?.name || state.analysis?.name || analysisId;
  if (!window.confirm(`Supprimer l'analyse "${name}" et toutes ses données rattachées ?`)) {
    setStatus("Suppression annulée");
    return;
  }
  await api(`/api/analyses/${encodeURIComponent(analysisId)}`, { method: "DELETE" });
  state.analysis = null;
  state.files = [];
  state.events = [];
  state.channelStatus = null;
  state.recurrent = [];
  state.anomalyFiles = [];
  state.anomalies = [];
  state.selectedChannels = new Set();
  state.validatedStructure = null;
  await loadAnalyses();
  if (state.analyses.length) {
    await loadAnalysis(state.analyses[0].analysis_id);
  } else {
    renderAll();
  }
}

async function analyzeChannels() {
  const analysisId = currentAnalysisId();
  if (!analysisId) throw new Error("Aucune analyse active");
  const pollId = ++state.channelAnalysisPollId;
  setChannelAnalysisRunning(true, { percent: 0, message: "Démarrage" });
  try {
    const maxFiles = $("maxFilesInput").value ? Number($("maxFilesInput").value) : null;
    const task = await api(`/api/analyses/${encodeURIComponent(analysisId)}/channels/analyze`, {
      method: "POST",
      body: JSON.stringify({
        preset_name: "inventory",
        normalize_names: $("normalizeNamesInput").checked,
        min_frequency: 1,
        target_channels: [],
        max_files: maxFiles,
      }),
    });
    setChannelAnalysisRunning(true, task);
    await pollChannelAnalysis(analysisId, task.task_id, pollId);
    setChannelAnalysisRunning(true, { percent: 100, message: "Rafraîchissement des résultats" });
    await loadAnalysis(analysisId);
  } finally {
    if (pollId === state.channelAnalysisPollId) {
      setChannelAnalysisRunning(false);
    }
  }
}

async function saveChannelStructure() {
  const analysisId = currentAnalysisId();
  if (!analysisId) throw new Error("Aucune analyse active");
  const selectedChannels = Array.from(state.selectedChannels);
  if (!selectedChannels.length) throw new Error("Aucun canal sélectionné");
  await api(`/api/analyses/${encodeURIComponent(analysisId)}/channels/validated-structure`, {
    method: "POST",
    body: JSON.stringify({
      selected_channels: selectedChannels,
      normalize_names: $("normalizeNamesInput").checked,
    }),
  });
  await loadChannels();
  if (state.selectedChannels.size) {
    showWorkflowStep("sampling");
  }
}

async function finalizeAnalysis() {
  const analysisId = currentAnalysisId();
  if (!analysisId) throw new Error("Aucune analyse active");
  if (!state.files.length) throw new Error("Aucun fichier DXD identifié");
  if (!state.selectedChannels.size) throw new Error("Aucun canal sélectionné");
  const samplingRate = Number($("samplingRateInput").value);
  if (!Number.isFinite(samplingRate) || samplingRate <= 0) {
    throw new Error("Fréquence de sampling invalide");
  }
  await api(`/api/analyses/${encodeURIComponent(analysisId)}/config`, {
    method: "PATCH",
    body: JSON.stringify({
      config: {
        workflow: "dxd_channels_resampling",
        sampling: {
          target_frequency_hz: samplingRate,
          method: $("samplingMethodInput").value,
          resampled_json_dir: $("resampledJsonDirInput").value.trim() || null,
        },
      },
    }),
  });
  await saveChannelStructure();
  const pollId = ++state.resamplingPollId;
  setResamplingRunning(true, { percent: 0, message: "Démarrage" });
  try {
    const task = await api(`/api/analyses/${encodeURIComponent(analysisId)}/resampling/export-json`, {
      method: "POST",
      body: JSON.stringify({
        target_frequency_hz: samplingRate,
        interpolation_method: $("samplingMethodInput").value,
        output_dir: $("resampledJsonDirInput").value.trim() || null,
      }),
    });
    setResamplingRunning(true, task);
    await pollResampling(analysisId, task.task_id, pollId);
    await loadAnalysis(analysisId);
  } finally {
    if (pollId === state.resamplingPollId) {
      setResamplingRunning(false);
    }
  }
}

async function loadAnomalyDetails(fileId) {
  const analysisId = currentAnalysisId();
  if (!analysisId || !fileId) return;
  const payload = await api(`/api/analyses/${encodeURIComponent(analysisId)}/channels/anomalies?file_id=${encodeURIComponent(fileId)}`);
  state.anomalies = payload.items || [];
}

function selectAllRecurrent() {
  state.selectedChannels = new Set(state.recurrent.map(row => row.channel));
  renderChannels();
}

function clearRecurrent() {
  state.selectedChannels = new Set();
  renderChannels();
}

async function pollChannelAnalysis(analysisId, taskId, pollId = state.channelAnalysisPollId) {
  const terminal = new Set(["finished", "cancelled", "failed"]);
  while (true) {
    await new Promise(resolve => setTimeout(resolve, 450));
    if (pollId !== state.channelAnalysisPollId) return null;
    const task = await api(`/api/analyses/${encodeURIComponent(analysisId)}/channels/tasks/${encodeURIComponent(taskId)}`);
    setChannelAnalysisRunning(!terminal.has(task.status), task);
    if (terminal.has(task.status)) {
      if (task.status === "failed") {
        throw new Error(task.error || "Analyse canaux échouée");
      }
      return task;
    }
  }
}

async function pollResampling(analysisId, taskId, pollId = state.resamplingPollId) {
  const terminal = new Set(["finished", "finished_with_errors", "cancelled", "failed"]);
  while (true) {
    await new Promise(resolve => setTimeout(resolve, 450));
    if (pollId !== state.resamplingPollId) return null;
    const task = await api(`/api/analyses/${encodeURIComponent(analysisId)}/resampling/tasks/${encodeURIComponent(taskId)}`);
    setResamplingRunning(!terminal.has(task.status), task);
    if (terminal.has(task.status)) {
      if (task.status === "failed") {
        throw new Error(task.error || "Export JSON échoué");
      }
      return task;
    }
  }
}

async function resumeCurrentChannelAnalysis(analysisId = currentAnalysisId()) {
  if (!analysisId || state.channelAnalysisRunning) return;
  try {
    const payload = await api(`/api/analyses/${encodeURIComponent(analysisId)}/channels/tasks/current`);
    const task = payload.task;
    if (!task || !["queued", "running", "cancelling"].includes(task.status)) return;
    const pollId = ++state.channelAnalysisPollId;
    setChannelAnalysisRunning(true, task);
    setStatus("Analyse canaux reprise", "ok");
    pollChannelAnalysis(analysisId, task.task_id, pollId)
      .then(async finishedTask => {
        if (pollId !== state.channelAnalysisPollId || !finishedTask) return;
        await loadAnalysis(analysisId);
        setStatus(
          finishedTask.status === "cancelled" ? "Analyse canaux interrompue" : "Analyse canaux terminée",
          finishedTask.status === "cancelled" ? "" : "ok"
        );
      })
      .catch(error => setStatus(error.message || String(error), "error"))
      .finally(() => {
        if (pollId === state.channelAnalysisPollId) {
          setChannelAnalysisRunning(false);
        }
      });
  } catch (_) {
    // A restarted server has no in-memory task to resume.
  }
}

async function resumeCurrentResampling(analysisId = currentAnalysisId()) {
  if (!analysisId || state.resamplingRunning) return;
  try {
    const payload = await api(`/api/analyses/${encodeURIComponent(analysisId)}/resampling/tasks/current`);
    const task = payload.task;
    if (!task || !["queued", "running", "cancelling"].includes(task.status)) return;
    const pollId = ++state.resamplingPollId;
    setResamplingRunning(true, task);
    setStatus("Export JSON repris", "ok");
    pollResampling(analysisId, task.task_id, pollId)
      .then(async finishedTask => {
        if (pollId !== state.resamplingPollId || !finishedTask) return;
        await loadAnalysis(analysisId);
        setStatus(
          finishedTask.status === "cancelled" ? "Export JSON interrompu" : "Export JSON terminé",
          finishedTask.status === "cancelled" ? "" : "ok"
        );
      })
      .catch(error => setStatus(error.message || String(error), "error"))
      .finally(() => {
        if (pollId === state.resamplingPollId) {
          setResamplingRunning(false);
        }
      });
  } catch (_) {
    // A restarted server has no in-memory task to resume.
  }
}

async function cancelChannelAnalysis() {
  const analysisId = currentAnalysisId();
  const taskId = state.channelAnalysisTaskId;
  if (!analysisId || !taskId) return;
  const task = await api(
    `/api/analyses/${encodeURIComponent(analysisId)}/channels/tasks/${encodeURIComponent(taskId)}/cancel`,
    { method: "POST" }
  );
  setChannelAnalysisRunning(true, task);
}

async function cancelResampling() {
  const analysisId = currentAnalysisId();
  const taskId = state.resamplingTaskId;
  if (!analysisId || !taskId) return;
  const task = await api(
    `/api/analyses/${encodeURIComponent(analysisId)}/resampling/tasks/${encodeURIComponent(taskId)}/cancel`,
    { method: "POST" }
  );
  setResamplingRunning(true, task);
}

function bindActions() {
  $("mainNav").addEventListener("click", event => {
    const button = event.target.closest("button[data-view]");
    if (!button) return;
    document.querySelectorAll("#mainNav button").forEach(item => item.classList.remove("active"));
    button.classList.add("active");
    document.querySelectorAll(".view").forEach(item => item.classList.remove("active"));
    $(`view-${button.dataset.view}`).classList.add("active");
  });

  $("analysisWorkflowTabs")?.addEventListener("click", event => {
    const button = event.target.closest("button[data-workflow-step]");
    if (!button || button.disabled) return;
    showWorkflowStep(button.dataset.workflowStep);
  });
  $("analysisChoiceList")?.addEventListener("click", event => {
    const deleteButton = event.target.closest("button[data-delete-analysis-id]");
    if (deleteButton) {
      wrapAction(() => deleteAnalysisById(deleteButton.dataset.deleteAnalysisId), "Analyse supprimée")();
      return;
    }
    const button = event.target.closest("button[data-analysis-id]");
    if (!button) return;
    wrapAction(() => loadAnalysis(button.dataset.analysisId), "Analyse chargée")();
  });
  $("explorationFileSelect")?.addEventListener("change", wrapAction(async () => {
    state.explorationFileId = $("explorationFileSelect").value;
    await loadExplorationChannels();
    await refreshExploration();
  }, "Exploration chargée"));
  $("explorationPrevBtn")?.addEventListener("click", wrapAction(() => goToRelativeExplorationFile(-1), "Fichier précédent"));
  $("explorationNextBtn")?.addEventListener("click", wrapAction(() => goToRelativeExplorationFile(1), "Fichier suivant"));
  const explorationChannelSelect = $("explorationChannelSelect");
  ["input", "change", "click", "mouseup", "keyup"].forEach(eventName => {
    explorationChannelSelect?.addEventListener(eventName, () => {
      setTimeout(refreshExplorationFromChannelSelection, 0);
    });
  });
  ["explorationMaxPointsInput", "explorationMultiAxisInput", "explorationSegmentSourceSelect", "explorationLabelSelect"].forEach(id => {
    $(id)?.addEventListener("change", wrapAction(refreshExploration, "Exploration chargée"));
  });
  document.addEventListener("keydown", event => {
    const activeView = document.querySelector(".view.active");
    if (!activeView || activeView.id !== "view-exploration") return;
    if (event.target && ["INPUT", "SELECT", "TEXTAREA"].includes(event.target.tagName)) return;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      wrapAction(() => goToRelativeExplorationFile(-1), "Fichier précédent")();
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      wrapAction(() => goToRelativeExplorationFile(1), "Fichier suivant")();
    }
  });
  window.addEventListener("resize", () => {
    ["explorationSignalPlot", "explorationTrajectoryPlot"].forEach(id => {
      const el = $(id);
      if (el && window.Plotly) Plotly.Plots.resize(el);
    });
  });
  $("createAnalysisBtn").addEventListener("click", wrapAction(createAnalysis, "Analyse créée"));
  $("analyzeChannelsBtn").addEventListener("click", wrapAction(analyzeChannels, "Analyse canaux terminée"));
  $("cancelChannelAnalysisBtn").addEventListener("click", wrapAction(cancelChannelAnalysis, "Arrêt demandé"));
  $("selectAllRecurrentBtn").addEventListener("click", selectAllRecurrent);
  $("clearRecurrentBtn").addEventListener("click", clearRecurrent);
  $("saveChannelStructureBtn").addEventListener("click", wrapAction(saveChannelStructure, "Structure sauvegardée"));
  $("finalizeAnalysisBtn").addEventListener("click", wrapAction(finalizeAnalysis, "Analyse créée et export JSON terminé"));
  $("cancelResamplingBtn").addEventListener("click", wrapAction(cancelResampling, "Arrêt demandé"));
  $("channelSearchInput").addEventListener("input", event => {
    state.recurrentFilter = event.target.value;
    renderChannels();
  });
  $("presetSelect")?.addEventListener("change", () => updatePresetOptions(true));
}

function wrapAction(fn, successMessage) {
  return async () => {
    try {
      setStatus("Traitement en cours...");
      await fn();
      renderAll();
      setStatus(successMessage, "ok");
    } catch (error) {
      setStatus(error.message || String(error), "error");
    }
  };
}

async function init() {
  bindActions();
  try {
    await loadAnalyses();
    if (state.analysis) {
      await loadAnalysis(state.analysis.analysis_id);
    }
    setStatus("Prêt");
  } catch (error) {
    setStatus(error.message || String(error), "error");
  }
}

init();
