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
  parametricFiles: [],
  parametricChannels: [],
  parametricFileId: "",
  annotationFiles: [],
  annotationChannels: [],
  annotationFileId: "",
  annotations: [],
  annotationLabels: [],
  annotationManagedLabels: [],
  annotationEditingId: "",
  annotationSeries: null,
  annotationClickTarget: "end",
  annotationCatalog: [],
  annotationLabelSummary: [],
  annotationStep: "annotate",
  dynamicPrompts: [],
  dynamicRuns: [],
  dynamicAnalyses: [],
  dynamicPredictions: [],
  dynamicContext: null,
  dynamicSelectedRunId: "",
  dynamicSelectedAnalysisId: "",
  dynamicSelectedPredictionId: "",
};

let explorationDateFilterTimer = null;
let annotationDateFilterTimer = null;

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

function showExplorationStep(step) {
  document.querySelectorAll("[data-exploration-step]").forEach(button => {
    button.classList.toggle("active", button.dataset.explorationStep === step);
  });
  document.querySelectorAll(".exploration-step").forEach(item => item.classList.remove("active"));
  $(`exploration-${step}`)?.classList.add("active");
}

function showAnnotationStep(step) {
  const target = step === "catalog" ? "catalog" : "annotate";
  state.annotationStep = target;
  document.querySelectorAll("[data-annotation-step]").forEach(button => {
    button.classList.toggle("active", button.dataset.annotationStep === target);
  });
  document.querySelectorAll(".annotation-step").forEach(item => item.classList.remove("active"));
  $(`annotation-${target}`)?.classList.add("active");
  if (target === "annotate") {
    resizeAnnotationPlotsSoon();
  }
}

function showDynamicAnalysisStep(step) {
  const target = ["analysis", "prepare", "results"].includes(step) ? step : "analysis";
  document.querySelectorAll("[data-dynamic-step]").forEach(button => {
    button.classList.toggle("active", button.dataset.dynamicStep === target);
  });
  document.querySelectorAll(".dynamic-analysis-step").forEach(item => item.classList.remove("active"));
  $(`dynamic-analysis-${target}`)?.classList.add("active");
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

function setParametricStatus(message) {
  const node = $("parametricStatus");
  if (node) node.textContent = message;
}

function setAnnotationStatus(message) {
  const node = $("annotationStatus");
  if (node) node.textContent = message;
}

function setDynamicAnalysisStatus(message) {
  const node = $("dynamicAnalysisStatus");
  if (node) node.textContent = message;
}

function renderMarkdownLite(text) {
  const lines = String(text || "").split(/\r?\n/);
  return lines.map(line => {
    if (line.startsWith("### ")) return `<h3>${escapeHtml(line.slice(4))}</h3>`;
    if (line.startsWith("## ")) return `<h2>${escapeHtml(line.slice(3))}</h2>`;
    if (line.startsWith("- ")) return `<div>• ${escapeHtml(line.slice(2))}</div>`;
    if (!line.trim()) return "<br>";
    return `<p>${escapeHtml(line)}</p>`;
  }).join("");
}

function resizePlots(ids) {
  if (!window.Plotly) return;
  ids.forEach(id => {
    const el = $(id);
    if (el) Plotly.Plots.resize(el);
  });
}

function resizeAnnotationPlotsSoon() {
  requestAnimationFrame(() => {
    resizePlots(["annotationSignalPlot", "annotationTrajectoryPlot"]);
    setTimeout(() => resizePlots(["annotationSignalPlot", "annotationTrajectoryPlot"]), 80);
  });
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
  renderParametricChannelOptions();
}

function renderParametricChannelOptions() {
  const select = $("parametricChannelSelect");
  if (!select) return;
  const previous = selectedParametricChannels();
  const channels = state.parametricChannels.length ? state.parametricChannels : state.explorationChannels;
  select.innerHTML = channels.map(channel => `
    <option value="${escapeHtml(channel.value)}">${escapeHtml(channel.label || channel.value)}</option>
  `).join("");
  const values = channels.map(channel => channel.value);
  const selected = previous.length
    ? previous.filter(channel => values.includes(channel)).slice(0, 2)
    : values.slice(0, 2);
  Array.from(select.options).forEach(option => {
    option.selected = selected.includes(option.value);
  });
}

function renderParametricFileOptions() {
  const select = $("parametricFileSelect");
  if (!select) return;
  select.innerHTML = state.parametricFiles.length
    ? state.parametricFiles.map(file => `
      <option value="${escapeHtml(file.file_id)}">${escapeHtml(file.resampled_json_name || file.source_dxd_name)}</option>
    `).join("")
    : '<option value="">Aucun JSON exporté</option>';
  if (state.parametricFileId && state.parametricFiles.some(file => file.file_id === state.parametricFileId)) {
    select.value = state.parametricFileId;
  } else if (state.parametricFiles.length) {
    state.parametricFileId = state.parametricFiles[0].file_id;
    select.value = state.parametricFileId;
  } else {
    state.parametricFileId = "";
  }
}

function renderAnnotationFileOptions() {
  const select = $("annotationFileSelect");
  if (!select) return;
  select.innerHTML = state.annotationFiles.length
    ? state.annotationFiles.map(file => `
      <option value="${escapeHtml(file.file_id)}">${escapeHtml(file.resampled_json_name || file.source_dxd_name)}</option>
    `).join("")
    : '<option value="">Aucun JSON exporté</option>';
  if (state.annotationFileId && state.annotationFiles.some(file => file.file_id === state.annotationFileId)) {
    select.value = state.annotationFileId;
  } else if (state.annotationFiles.length) {
    state.annotationFileId = state.annotationFiles[0].file_id;
    select.value = state.annotationFileId;
  } else {
    state.annotationFileId = "";
  }
}

function renderAnnotationChannelOptions(previous = "") {
  const select = $("annotationChannelSelect");
  if (!select) return;
  select.innerHTML = state.annotationChannels.length
    ? state.annotationChannels.map(channel => `
      <option value="${escapeHtml(channel.value)}">${escapeHtml(channel.label || channel.value)}</option>
    `).join("")
    : '<option value="">Aucun canal disponible</option>';
  const values = state.annotationChannels.map(channel => channel.value);
  const previousValues = Array.isArray(previous) ? previous : [previous].filter(Boolean);
  const selected = previousValues.length
    ? previousValues.filter(channel => values.includes(channel)).slice(0, 2)
    : values.slice(0, 2);
  Array.from(select.options).forEach(option => {
    option.selected = selected.includes(option.value);
  });
}

function renderAnnotationLabels() {
  const annotateSelect = $("annotationLabelSelect");
  if (annotateSelect) {
    const previous = annotateSelect.value;
    annotateSelect.innerHTML = state.annotationLabels.length
      ? [
        '<option value="">Choisir un label</option>',
        ...state.annotationLabels.map(label => `<option value="${escapeHtml(label)}">${escapeHtml(label)}</option>`),
      ].join("")
      : '<option value="">Aucun label disponible</option>';
    annotateSelect.value = state.annotationLabels.includes(previous) ? previous : "";
  }
  const catalogSelect = $("annotationCatalogLabelSelect");
  if (catalogSelect) {
    const previous = catalogSelect.value;
    catalogSelect.innerHTML = [
      '<option value="">Tous les labels</option>',
      ...state.annotationLabels.map(label => `<option value="${escapeHtml(label)}">${escapeHtml(label)}</option>`),
    ].join("");
    catalogSelect.value = state.annotationLabels.includes(previous) ? previous : "";
  }
  const renameSelect = $("annotationRenameOldLabelSelect");
  if (renameSelect) {
    const previous = renameSelect.value;
    renameSelect.innerHTML = state.annotationManagedLabels.length
      ? state.annotationManagedLabels.map(label => `<option value="${escapeHtml(label.label_id)}">${escapeHtml(label.name)}</option>`).join("")
      : '<option value="">Aucun label</option>';
    renameSelect.value = state.annotationManagedLabels.some(label => label.label_id === previous)
      ? previous
      : (state.annotationManagedLabels[0]?.label_id || "");
  }
}

function selectedExplorationChannels() {
  return Array.from($("explorationChannelSelect")?.selectedOptions || [])
    .map(option => option.value)
    .slice(0, 2);
}

function selectedParametricChannels() {
  return Array.from($("parametricChannelSelect")?.selectedOptions || [])
    .map(option => option.value)
    .slice(0, 2);
}

function selectedAnnotationChannels() {
  return Array.from($("annotationChannelSelect")?.selectedOptions || [])
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

function clampParametricChannelSelection() {
  const select = $("parametricChannelSelect");
  if (!select) return;
  const selected = Array.from(select.options)
    .filter(option => option.selected)
    .map(option => option.value);
  if (selected.length <= 2) return;
  const keep = new Set(selected.slice(-2));
  Array.from(select.options).forEach(option => {
    option.selected = keep.has(option.value);
  });
  setParametricStatus("Maximum 2 canaux affichables en même temps.");
}

function clampAnnotationChannelSelection() {
  const select = $("annotationChannelSelect");
  if (!select) return;
  const selected = Array.from(select.options)
    .filter(option => option.selected)
    .map(option => option.value);
  if (selected.length <= 2) return;
  const keep = new Set(selected.slice(-2));
  Array.from(select.options).forEach(option => {
    option.selected = keep.has(option.value);
  });
  setAnnotationStatus("Maximum 2 canaux affichables en même temps.");
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

function drawAnnotationSignalPlot(payload) {
  if (!window.Plotly) return;
  state.annotationSeries = payload;
  const channels = payload.channels || [];
  if (!channels.length) {
    drawEmptyPlot("annotationSignalPlot", "Aucun signal");
    return;
  }
  const traces = channels.map((channel, index) => ({
    type: "scattergl",
    mode: "lines",
    name: channel.name,
    x: payload.time || [],
    y: channel.values || [],
    yaxis: index === 0 ? "y" : `y${index + 1}`,
    line: { color: index === 0 ? "#1368ce" : "#15803d", width: 1.5 },
    hovertemplate: "t=%{x:.2f}s<br>val=%{y:.4g}<extra></extra>",
  }));
  const guideChannel = channels[0];
  const guideStep = Math.max(1, Math.floor((payload.time || []).length / 1200));
  const guideTrace = {
    type: "scatter",
    mode: "markers",
    name: "Guide clic",
    x: (payload.time || []).filter((_, index) => index % guideStep === 0),
    y: (guideChannel.values || []).filter((_, index) => index % guideStep === 0),
    marker: { size: 7, color: "#1368ce", opacity: 0.08 },
    hovertemplate: "t=%{x:.2f}s<extra></extra>",
    showlegend: false,
  };
  const currentStart = Number($("annotationStartInput")?.value);
  const currentEnd = Number($("annotationEndInput")?.value);
  const currentShapes = Number.isFinite(currentStart) && Number.isFinite(currentEnd) && currentEnd > currentStart
    ? [
      {
        type: "rect",
        xref: "x",
        yref: "paper",
        x0: currentStart,
        x1: currentEnd,
        y0: 0,
        y1: 1,
        fillcolor: "rgba(180, 35, 24, 0.08)",
        line: { width: 0 },
        layer: "below",
      },
      {
        type: "line",
        xref: "x",
        yref: "paper",
        x0: currentStart,
        x1: currentStart,
        y0: 0,
        y1: 1,
        line: { color: "#15803d", width: 2, dash: "dash" },
      },
      {
        type: "line",
        xref: "x",
        yref: "paper",
        x0: currentEnd,
        x1: currentEnd,
        y0: 0,
        y1: 1,
        line: { color: "#b42318", width: 2, dash: "dash" },
      },
    ]
    : [];
  const savedShapes = state.annotations.map((annotation, index) => ({
    type: "rect",
    xref: "x",
    yref: "paper",
    x0: annotation.start_time_sec,
    x1: annotation.end_time_sec,
    y0: 0,
    y1: 1,
    fillcolor: index % 2 === 0 ? "rgba(19, 104, 206, 0.14)" : "rgba(21, 128, 61, 0.14)",
    line: { width: 1, color: index % 2 === 0 ? "#1368ce" : "#15803d" },
  }));
  const labels = state.annotations.map(annotation => ({
    text: annotation.label,
    x: (Number(annotation.start_time_sec) + Number(annotation.end_time_sec)) / 2,
    y: 1,
    xref: "x",
    yref: "paper",
    yanchor: "bottom",
    showarrow: false,
    font: { color: "#17202c", size: 11 },
    bgcolor: "rgba(255, 255, 255, 0.82)",
    bordercolor: "#d7dee8",
    borderpad: 3,
  }));
  const layout = plotlyLayout("Signal annotable", channels[0].unit || "");
  layout.xaxis.title = "temps (s)";
  layout.dragmode = "closest";
  layout.shapes = [...savedShapes, ...currentShapes];
  layout.annotations = labels;
  if (traces.length > 1) {
    layout.yaxis2 = {
      title: traces[1].name,
      overlaying: "y",
      side: "right",
      gridcolor: "#e5eaf1",
      zerolinecolor: "#d7dee8",
    };
  }
  Promise.resolve(Plotly.react("annotationSignalPlot", [...traces, guideTrace], layout, {
    responsive: true,
    displaylogo: false,
  })).then(bindAnnotationPlotSelection);
}

function drawAnnotationTrajectoryPlot(payload) {
  if (!window.Plotly) return;
  const items = payload.items || [];
  if (!items.length) {
    drawEmptyPlot("annotationTrajectoryPlot", "Trajectoire GPS indisponible");
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
  Plotly.react("annotationTrajectoryPlot", [trace], layout, { responsive: true, displaylogo: false });
}

function drawParametricPlot(payload) {
  if (!window.Plotly) return;
  const items = payload.items || [];
  if (!items.length) {
    drawEmptyPlot("parametricPlot", "Aucun point disponible");
    return;
  }
  const scatterMode = $("parametricScatterInput")?.checked !== false;
  const trace = {
    type: "scattergl",
    mode: scatterMode ? "markers" : "lines",
    name: `${payload.y_channel} / ${payload.x_channel}`,
    x: items.map(item => item.x),
    y: items.map(item => item.y),
    text: items.map(item => item.file_name),
    marker: { color: "#1368ce", size: 4, opacity: 0.55 },
    line: { color: "#1368ce", width: 1.3 },
    hovertemplate: "x=%{x:.4g}<br>y=%{y:.4g}<br>%{text}<extra></extra>",
  };
  const layout = plotlyLayout("Vision paramétrique", payload.y_channel);
  layout.xaxis.title = payload.x_channel;
  Plotly.react("parametricPlot", [trace], layout, { responsive: true, displaylogo: false });
}

async function loadExplorationFiles() {
  const analysisId = currentAnalysisId();
  if (!analysisId) return;
  try {
    const params = new URLSearchParams();
    const dateFrom = $("explorationDateFromInput")?.value;
    const dateTo = $("explorationDateToInput")?.value;
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    const query = params.toString();
    const payload = await api(
      `/api/analyses/${encodeURIComponent(analysisId)}/exploration/files${query ? `?${query}` : ""}`
    );
    state.explorationFiles = payload.items || [];
    renderExplorationFileOptions();
    renderExplorationLabels();
    const dateStatus = $("explorationDateRangeStatus");
    if (dateStatus && (dateFrom || dateTo)) {
      dateStatus.textContent = `${state.explorationFiles.length} fichier(s) dans la plage sélectionnée.`;
    }
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

async function loadExplorationDateRange() {
  const analysisId = currentAnalysisId();
  const fromInput = $("explorationDateFromInput");
  const toInput = $("explorationDateToInput");
  const status = $("explorationDateRangeStatus");
  if (!analysisId || !fromInput || !toInput) return;
  const payload = await api(`/api/analyses/${encodeURIComponent(analysisId)}/exploration/date-range`);
  renderDateRangeControls(payload, fromInput, toInput, status);
}

async function loadParametricDateRange() {
  const analysisId = currentAnalysisId();
  const fromInput = $("parametricDateFromInput");
  const toInput = $("parametricDateToInput");
  const status = $("parametricDateRangeStatus");
  if (!analysisId || !fromInput || !toInput) return;
  const payload = await api(`/api/analyses/${encodeURIComponent(analysisId)}/exploration/date-range`);
  renderDateRangeControls(payload, fromInput, toInput, status);
}

async function loadAnnotationDateRange() {
  const analysisId = currentAnalysisId();
  const fromInput = $("annotationDateFromInput");
  const toInput = $("annotationDateToInput");
  const status = $("annotationDateRangeStatus");
  if (!analysisId || !fromInput || !toInput) return;
  const payload = await api(`/api/analyses/${encodeURIComponent(analysisId)}/exploration/date-range`);
  renderDateRangeControls(payload, fromInput, toInput, status);
  const catalogFrom = $("annotationCatalogDateFromInput");
  const catalogTo = $("annotationCatalogDateToInput");
  if (catalogFrom && catalogTo) {
    renderDateRangeControls(payload, catalogFrom, catalogTo, null);
  }
}

function renderDateRangeControls(payload, fromInput, toInput, status) {
  const dates = payload.dates || [];
  renderExplorationDateOptions(fromInput, dates, "Toutes les dates");
  renderExplorationDateOptions(toInput, dates, "Toutes les dates");
  if (status) {
    status.textContent = payload.date_min && payload.date_max
      ? `Dates disponibles: ${payload.date_min} à ${payload.date_max}`
      : "Aucune plage de dates disponible dans les métadonnées.";
  }
}

function renderExplorationDateOptions(select, dates, emptyLabel) {
  const previous = select.value;
  select.innerHTML = [
    `<option value="">${escapeHtml(emptyLabel)}</option>`,
    ...dates.map(date => `<option value="${escapeHtml(date)}">${escapeHtml(date)}</option>`),
  ].join("");
  select.value = dates.includes(previous) ? previous : "";
}

function scheduleExplorationDateFilter() {
  if (explorationDateFilterTimer) {
    clearTimeout(explorationDateFilterTimer);
  }
  explorationDateFilterTimer = setTimeout(async () => {
    explorationDateFilterTimer = null;
    try {
      await loadExplorationFiles();
      if ($("parametricScopeSelect")?.value === "filtered") {
        await refreshParametric();
      }
    } catch (error) {
      setExplorationStatus(`Erreur filtre date:\n${error.message || String(error)}`);
      setStatus(error.message || String(error), "error");
    }
  }, 80);
}

function scheduleAnnotationDateFilter() {
  if (annotationDateFilterTimer) {
    clearTimeout(annotationDateFilterTimer);
  }
  annotationDateFilterTimer = setTimeout(async () => {
    annotationDateFilterTimer = null;
    try {
      await loadAnnotationFiles();
    } catch (error) {
      setAnnotationStatus(`Erreur filtre date:\n${error.message || String(error)}`);
      setStatus(error.message || String(error), "error");
    }
  }, 80);
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

async function loadAnnotationFiles() {
  const analysisId = currentAnalysisId();
  if (!analysisId) return;
  const params = new URLSearchParams();
  const dateFrom = $("annotationDateFromInput")?.value;
  const dateTo = $("annotationDateToInput")?.value;
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const query = params.toString();
  const payload = await api(
    `/api/analyses/${encodeURIComponent(analysisId)}/exploration/files${query ? `?${query}` : ""}`
  );
  state.annotationFiles = payload.items || [];
  renderAnnotationFileOptions();
  const dateStatus = $("annotationDateRangeStatus");
  if (dateStatus && (dateFrom || dateTo)) {
    dateStatus.textContent = `${state.annotationFiles.length} fichier(s) dans la plage sélectionnée.`;
  }
  if (state.annotationFileId) {
    await loadAnnotationChannels();
    await loadAnnotations();
    await refreshAnnotationPlots();
  } else {
    state.annotationChannels = [];
    state.annotations = [];
    renderAnnotationChannelOptions();
    renderAnnotationsTable();
    setAnnotationStatus("Aucun JSON exporté pour cette analyse.");
    drawEmptyPlot("annotationSignalPlot", "Aucun signal");
    drawEmptyPlot("annotationTrajectoryPlot", "Aucune trajectoire");
  }
}

async function loadAnnotationChannels() {
  const analysisId = currentAnalysisId();
  const fileId = state.annotationFileId || $("annotationFileSelect")?.value;
  if (!analysisId || !fileId) return;
  const previous = selectedAnnotationChannels();
  const payload = await api(`/api/analyses/${encodeURIComponent(analysisId)}/exploration/files/${encodeURIComponent(fileId)}/signals/options`);
  state.annotationChannels = (payload.items || []).filter(item => item.available);
  renderAnnotationChannelOptions(previous);
}

async function loadAnnotationLabels() {
  const analysisId = currentAnalysisId();
  if (!analysisId) return;
  const payload = await api(`/api/analyses/${encodeURIComponent(analysisId)}/annotation-labels`);
  state.annotationManagedLabels = payload.items || [];
  state.annotationLabels = state.annotationManagedLabels.map(label => label.name);
  renderAnnotationLabels();
}

async function loadAnnotations() {
  const analysisId = currentAnalysisId();
  const fileId = state.annotationFileId || $("annotationFileSelect")?.value;
  if (!analysisId || !fileId) return;
  const payload = await api(
    `/api/analyses/${encodeURIComponent(analysisId)}/annotations?file_id=${encodeURIComponent(fileId)}`
  );
  state.annotations = payload.items || [];
  renderAnnotationsTable();
  await loadAnnotationLabels();
}

async function loadAnnotationCatalog() {
  const analysisId = currentAnalysisId();
  if (!analysisId) return;
  const [annotationsPayload, summaryPayload] = await Promise.all([
    api(`/api/analyses/${encodeURIComponent(analysisId)}/annotations`),
    api(`/api/analyses/${encodeURIComponent(analysisId)}/annotations/summary`),
  ]);
  state.annotationCatalog = annotationsPayload.items || [];
  state.annotationLabelSummary = summaryPayload.items || [];
  await loadAnnotationLabels();
  renderAnnotationLabelSummary();
  renderAnnotationCatalog();
}

async function loadDynamicAnalysis() {
  const analysisId = currentAnalysisId();
  if (!analysisId) return;
  if (!state.explorationChannels.length && state.explorationFileId) {
    await loadExplorationChannels();
  }
  await loadAnnotationLabels();
  const analyses = await api(`/api/analyses/${encodeURIComponent(analysisId)}/dynamic-analysis`);
  state.dynamicAnalyses = analyses.items || [];
  state.dynamicPrompts = state.dynamicAnalyses;
  const selected = state.dynamicSelectedAnalysisId || state.dynamicAnalyses[0]?.dynamic_analysis_id || "";
  state.dynamicSelectedAnalysisId = selected;
  if (selected) {
    const predictions = await api(`/api/analyses/${encodeURIComponent(analysisId)}/dynamic-analysis/${encodeURIComponent(selected)}/predictions`);
    state.dynamicPredictions = predictions.items || [];
  } else {
    state.dynamicPredictions = [];
  }
  state.dynamicRuns = state.dynamicPredictions;
  renderDynamicPromptOptions();
  renderDynamicChannelOptions();
  renderDynamicLabelOptions();
  renderDynamicRuns();
}

async function saveDynamicPrompt() {
  const analysisId = currentAnalysisId();
  if (!analysisId) throw new Error("Aucune analyse active");
  const labelCategory = $("dynamicAnalysisLabelCategorySelect")?.value || selectedDynamicLabels().filter(Boolean)[0] || "";
  if (!labelCategory) throw new Error("Choisis une catégorie de label");
  const payload = {
    name: $("dynamicAnalysisPromptNameInput")?.value.trim() || "Analyse de segments annotés",
    system_prompt: $("dynamicAnalysisSystemPromptInput")?.value || "",
    selected_channels: selectedDynamicChannels(),
    indicators: [],
    label_category: labelCategory,
    output_schema: dynamicOutputSchema(),
  };
  const dynamicAnalysis = await api(`/api/analyses/${encodeURIComponent(analysisId)}/dynamic-analysis`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.dynamicSelectedAnalysisId = dynamicAnalysis.dynamic_analysis_id;
  await loadDynamicAnalysis();
  $("dynamicAnalysisPromptSelect").value = dynamicAnalysis.dynamic_analysis_id;
  showDynamicAnalysisStep("prepare");
}

async function buildDynamicContext() {
  const analysisId = currentAnalysisId();
  if (!analysisId) throw new Error("Aucune analyse active");
  const context = await api(`/api/analyses/${encodeURIComponent(analysisId)}/dynamic-analysis/context`, {
    method: "POST",
    body: JSON.stringify(dynamicAnalysisPayload()),
  });
  renderDynamicContext(context);
  setDynamicAnalysisStatus(`${context.summary.segment_count} segment(s) dans le contexte.`);
}

async function runDynamicAnalysis() {
  const analysisId = currentAnalysisId();
  if (!analysisId) throw new Error("Aucune analyse active");
  const dynamicAnalysisId = state.dynamicSelectedAnalysisId || $("dynamicAnalysisPromptSelect")?.value;
  if (!dynamicAnalysisId) {
    await saveDynamicPrompt();
  }
  const resolvedDynamicAnalysisId = state.dynamicSelectedAnalysisId || $("dynamicAnalysisPromptSelect")?.value;
  if (!resolvedDynamicAnalysisId) throw new Error("Aucune analyse dynamique configurée");
  const result = await api(`/api/analyses/${encodeURIComponent(analysisId)}/dynamic-analysis/${encodeURIComponent(resolvedDynamicAnalysisId)}/predictions`, {
    method: "POST",
    body: JSON.stringify({
      user_prompt: $("dynamicAnalysisUserPromptInput")?.value || "",
      context_before_sec: Number($("dynamicContextBeforeInput")?.value || 0),
      context_after_sec: Number($("dynamicContextAfterInput")?.value || 0),
      max_annotations: Number($("dynamicMaxSegmentsInput")?.value || 25),
      max_points_per_segment: Number($("dynamicMaxPointsInput")?.value || 250),
      provider: "dry_run",
      model: null,
    }),
  });
  await loadDynamicAnalysis();
  if (result.items?.[0]) selectDynamicRun(result.items[0].prediction_id);
  setDynamicAnalysisStatus(`${result.items?.length || 0} prédiction(s) sauvegardée(s).`);
  showDynamicAnalysisStep("results");
}

async function deleteDynamicRun(runId) {
  if (!runId) return;
  const analysisId = currentAnalysisId();
  if (!analysisId) throw new Error("Aucune analyse active");
  if (!window.confirm("Supprimer cette analyse dynamique ?")) {
    setStatus("Suppression annulée");
    return;
  }
  await api(`/api/analyses/${encodeURIComponent(analysisId)}/dynamic-analysis/runs/${encodeURIComponent(runId)}`, {
    method: "DELETE",
  });
  if (state.dynamicSelectedRunId === runId) {
    state.dynamicSelectedRunId = "";
    $("dynamicAnalysisResult").innerHTML = "";
    $("dynamicAnalysisCorrectionInput").value = "";
    $("saveDynamicAnalysisVersionBtn").disabled = true;
  }
  await loadDynamicAnalysis();
}

async function saveDynamicAnalysisVersion() {
  const analysisId = currentAnalysisId();
  const predictionId = state.dynamicSelectedPredictionId || state.dynamicSelectedRunId;
  if (!analysisId || !predictionId) throw new Error("Aucune prédiction sélectionnée");
  const version = await api(`/api/analyses/${encodeURIComponent(analysisId)}/dynamic-analysis/predictions/${encodeURIComponent(predictionId)}/corrections`, {
    method: "POST",
    body: JSON.stringify({
      corrected_response_markdown: $("dynamicAnalysisCorrectionInput")?.value || "",
      corrected_response_json: {},
      corrected_confidence: $("dynamicAnalysisConfidenceSelect")?.value || null,
      note: $("dynamicAnalysisCorrectionNoteInput")?.value || null,
      validated_for_dataset: $("dynamicAnalysisValidatedInput")?.checked || false,
    }),
  });
  await loadDynamicAnalysis();
  const prediction = state.dynamicPredictions.find(item => item.prediction_id === predictionId);
  if (prediction) selectDynamicRun(predictionId);
  setDynamicAnalysisStatus(`Correction ${version.correction_id} sauvegardée.`);
}

async function loadParametricFiles() {
  const analysisId = currentAnalysisId();
  if (!analysisId) return;
  const params = new URLSearchParams();
  const dateFrom = $("parametricDateFromInput")?.value;
  const dateTo = $("parametricDateToInput")?.value;
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const query = params.toString();
  const payload = await api(
    `/api/analyses/${encodeURIComponent(analysisId)}/exploration/files${query ? `?${query}` : ""}`
  );
  state.parametricFiles = payload.items || [];
  renderParametricFileOptions();
  const dateStatus = $("parametricDateRangeStatus");
  if (dateStatus && (dateFrom || dateTo)) {
    dateStatus.textContent = `${state.parametricFiles.length} fichier(s) dans la plage sélectionnée.`;
  }
  if (state.parametricFileId) {
    await loadParametricChannels();
  } else {
    state.parametricChannels = [];
    renderParametricChannelOptions();
    drawEmptyPlot("parametricPlot", "Aucune donnée");
  }
}

async function loadParametricChannels() {
  const analysisId = currentAnalysisId();
  const fileId = state.parametricFileId || $("parametricFileSelect")?.value || state.explorationFileId;
  if (!analysisId || !fileId) return;
  const payload = await api(`/api/analyses/${encodeURIComponent(analysisId)}/exploration/files/${encodeURIComponent(fileId)}/signals/options`);
  state.parametricChannels = (payload.items || []).filter(item => item.available);
  renderParametricChannelOptions();
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

async function refreshParametric() {
  const analysisId = currentAnalysisId();
  const scope = $("parametricScopeSelect")?.value || "current";
  const fileId = state.parametricFileId || $("parametricFileSelect")?.value || state.explorationFileId;
  updateParametricScopeUi();
  if (!analysisId || !fileId) {
    setParametricStatus("Sélectionne une analyse avec des JSON exportés.");
    drawEmptyPlot("parametricPlot", "Aucune donnée");
    return;
  }
  if (!state.parametricChannels.length) {
    await loadParametricChannels();
  }
  const [xChannel, yChannel] = selectedParametricChannels();
  if (!xChannel || !yChannel) {
    setParametricStatus("Choisis deux canaux pour tracer la vision paramétrique.");
    drawEmptyPlot("parametricPlot", "Canaux manquants");
    return;
  }
  const params = new URLSearchParams({
    scope,
    x_channel: xChannel,
    y_channel: yChannel,
    max_points: $("parametricMaxPointsInput")?.value || "8000",
  });
  if (scope === "current") {
    params.set("file_id", fileId);
  } else {
    const dateFrom = $("parametricDateFromInput")?.value;
    const dateTo = $("parametricDateToInput")?.value;
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
  }
  setParametricStatus("Chargement de la distribution paramétrique...");
  const payload = await api(`/api/analyses/${encodeURIComponent(analysisId)}/exploration/parametric?${params.toString()}`);
  drawParametricPlot(payload);
  setParametricStatus([
    `Portée: ${scope === "current" ? "fichier courant" : "fichiers filtrés"}`,
    `Fichiers: ${payload.file_count}`,
    `Points: ${payload.returned_point_count} / ${payload.point_count}`,
    `Canaux: ${payload.x_channel} -> ${payload.y_channel}`,
  ].join("\n"));
}

async function refreshAnnotationPlots() {
  const analysisId = currentAnalysisId();
  const fileId = state.annotationFileId || $("annotationFileSelect")?.value;
  const channels = selectedAnnotationChannels();
  if (!analysisId || !fileId) {
    setAnnotationStatus("Sélectionne une analyse avec des JSON exportés.");
    return;
  }
  if (!state.annotationChannels.length) {
    await loadAnnotationChannels();
  }
  const selectedChannels = channels.length ? channels : selectedAnnotationChannels();
  if (!selectedChannels.length) {
    setAnnotationStatus("Aucun canal disponible pour ce fichier.");
    drawEmptyPlot("annotationSignalPlot", "Aucun signal");
    drawEmptyPlot("annotationTrajectoryPlot", "Aucune trajectoire");
    return;
  }
  const maxPoints = $("annotationMaxPointsInput")?.value || "8000";
  const params = new URLSearchParams({ max_points: maxPoints, channels: selectedChannels.join(",") });
  setAnnotationStatus("Chargement du fichier annotable...");
  const [series, trajectory] = await Promise.all([
    api(`/api/analyses/${encodeURIComponent(analysisId)}/exploration/files/${encodeURIComponent(fileId)}/series?${params.toString()}`),
    api(`/api/analyses/${encodeURIComponent(analysisId)}/exploration/files/${encodeURIComponent(fileId)}/trajectory?max_points=${encodeURIComponent(maxPoints)}`),
  ]);
  drawAnnotationSignalPlot(series);
  drawAnnotationTrajectoryPlot(trajectory);
  updateAnnotationRangeSlider();
  resizeAnnotationPlotsSoon();
  const currentFile = state.annotationFiles.find(file => file.file_id === fileId);
  setAnnotationStatus([
    `Fichier: ${currentFile?.resampled_json_name || currentFile?.source_dxd_name || "-"}`,
    `Canaux: ${selectedChannels.join(", ")}`,
    `Segments sauvegardés: ${state.annotations.length}`,
  ].join("\n"));
}

function updateParametricScopeUi() {
  const controls = $("parametricFileControls");
  if (!controls) return;
  const isFiltered = $("parametricScopeSelect")?.value === "filtered";
  controls.classList.toggle("hidden", isFiltered);
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

async function refreshParametricFromChannelSelection() {
  try {
    clampParametricChannelSelection();
    await refreshParametric();
  } catch (error) {
    setParametricStatus(`Erreur canaux:\n${error.message || String(error)}`);
    setStatus(error.message || String(error), "error");
  }
}

async function refreshAnnotationFromChannelSelection() {
  try {
    clampAnnotationChannelSelection();
    await refreshAnnotationPlots();
  } catch (error) {
    setAnnotationStatus(`Erreur canaux:\n${error.message || String(error)}`);
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

async function goToRelativeParametricFile(delta) {
  if (!state.parametricFiles.length) return;
  const current = state.parametricFileId || $("parametricFileSelect").value;
  const index = Math.max(0, state.parametricFiles.findIndex(file => file.file_id === current));
  const nextIndex = Math.max(0, Math.min(state.parametricFiles.length - 1, index + delta));
  const next = state.parametricFiles[nextIndex];
  if (!next || next.file_id === current) return;
  state.parametricFileId = next.file_id;
  $("parametricFileSelect").value = next.file_id;
  await loadParametricChannels();
  await refreshParametric();
}

async function goToRelativeAnnotationFile(delta) {
  if (!state.annotationFiles.length) return;
  const current = state.annotationFileId || $("annotationFileSelect").value;
  const index = Math.max(0, state.annotationFiles.findIndex(file => file.file_id === current));
  const nextIndex = Math.max(0, Math.min(state.annotationFiles.length - 1, index + delta));
  const next = state.annotationFiles[nextIndex];
  if (!next || next.file_id === current) return;
  state.annotationFileId = next.file_id;
  $("annotationFileSelect").value = next.file_id;
  resetAnnotationForm();
  await loadAnnotationChannels();
  await loadAnnotations();
  await refreshAnnotationPlots();
}

function resetAnnotationForm() {
  state.annotationEditingId = "";
  const start = $("annotationStartInput");
  const end = $("annotationEndInput");
  const label = $("annotationLabelSelect");
  const confidence = $("annotationConfidenceInput");
  const comment = $("annotationCommentInput");
  if (start) start.value = "0";
  if (end) end.value = "1";
  updateAnnotationRangeSlider();
  if (label) label.value = "";
  if (confidence) confidence.value = "1";
  if (comment) comment.value = "";
  const button = $("saveAnnotationBtn");
  if (button) button.textContent = "Sauvegarder segment";
}

function annotationTimes() {
  return (state.annotationSeries?.time || [])
    .map(value => Number(value))
    .filter(value => Number.isFinite(value));
}

function annotationMinTime() {
  const times = annotationTimes();
  return times.length ? Math.min(...times) : 0;
}

function annotationMaxTime() {
  const times = annotationTimes();
  return times.length ? Math.max(...times) : 1;
}

function annotationMinSegmentLen() {
  const times = annotationTimes();
  if (times.length >= 2) {
    const step = Math.abs(times[1] - times[0]);
    if (Number.isFinite(step) && step > 0) return Math.max(0.01, step);
  }
  return 0.01;
}

function updateAnnotationRangeSlider() {
  const slider = $("annotationEndRangeInput");
  if (!slider) return;
  const start = Number($("annotationStartInput")?.value);
  const minEnd = Number.isFinite(start)
    ? Math.min(annotationMaxTime(), start + annotationMinSegmentLen())
    : annotationMinTime();
  slider.min = minEnd.toFixed(2);
  slider.max = annotationMaxTime().toFixed(2);
  slider.value = $("annotationEndInput")?.value || slider.min;
}

function redrawAnnotationCurrentSegment() {
  if (state.annotationSeries) {
    drawAnnotationSignalPlot(state.annotationSeries);
  }
}

function setAnnotationStart(value) {
  const startInput = $("annotationStartInput");
  const endInput = $("annotationEndInput");
  const tMin = annotationMinTime();
  const tMax = annotationMaxTime();
  const minLen = annotationMinSegmentLen();
  const nextStart = Math.max(tMin, Math.min(Number(value), Math.max(tMin, tMax - minLen)));
  let nextEnd = Number(endInput?.value);
  if (!Number.isFinite(nextEnd) || nextEnd <= nextStart) {
    nextEnd = Math.min(tMax, nextStart + 1);
  }
  if (startInput) startInput.value = nextStart.toFixed(2);
  if (endInput) endInput.value = Math.max(nextStart + minLen, Math.min(nextEnd, tMax)).toFixed(2);
  updateAnnotationRangeSlider();
  redrawAnnotationCurrentSegment();
}

function setAnnotationEnd(value) {
  const startInput = $("annotationStartInput");
  const endInput = $("annotationEndInput");
  const tMax = annotationMaxTime();
  const minLen = annotationMinSegmentLen();
  const start = Number(startInput?.value);
  const safeStart = Number.isFinite(start) ? start : annotationMinTime();
  const nextEnd = Math.max(safeStart + minLen, Math.min(Number(value), tMax));
  if (startInput && !Number.isFinite(start)) startInput.value = safeStart.toFixed(2);
  if (endInput) endInput.value = nextEnd.toFixed(2);
  updateAnnotationRangeSlider();
  redrawAnnotationCurrentSegment();
}

function setAnnotationClickTarget(target) {
  state.annotationClickTarget = target === "start" ? "start" : "end";
  $("annotationClickStartBtn")?.classList.toggle("active", state.annotationClickTarget === "start");
  $("annotationClickEndBtn")?.classList.toggle("active", state.annotationClickTarget === "end");
}

function editAnnotation(annotationId) {
  const annotation = state.annotations.find(item => item.annotation_id === annotationId);
  if (!annotation) return;
  state.annotationEditingId = annotationId;
  $("annotationStartInput").value = annotation.start_time_sec;
  $("annotationEndInput").value = annotation.end_time_sec;
  $("annotationLabelSelect").value = annotation.label || "";
  $("annotationConfidenceInput").value = annotation.confidence ?? "";
  $("annotationCommentInput").value = annotation.comment || "";
  $("saveAnnotationBtn").textContent = "Modifier segment";
  updateAnnotationRangeSlider();
  redrawAnnotationCurrentSegment();
  setAnnotationStatus(`Modification du segment ${annotation.label || annotationId}`);
}

function setAnnotationRangeFromPlotPoints(points) {
  const times = (points || [])
    .map(point => Number(point.x))
    .filter(value => Number.isFinite(value));
  if (times.length < 2) return;
  const start = Math.min(...times);
  const end = Math.max(...times);
  if (end <= start) return;
  $("annotationStartInput").value = start.toFixed(2);
  $("annotationEndInput").value = end.toFixed(2);
  setAnnotationStatus(`Segment sélectionné: ${start.toFixed(2)} s -> ${end.toFixed(2)} s`);
}

function annotationTimeFromClientX(plot, clientX) {
  const layout = plot?._fullLayout;
  const axis = layout?.xaxis;
  if (!layout || !axis) return null;
  const rect = plot.getBoundingClientRect();
  const plotLeft = rect.left + Number(axis._offset ?? layout.margin?.l ?? 0);
  const plotWidth = Number(axis._length ?? (layout.width - layout.margin.l - layout.margin.r));
  const pixel = clientX - plotLeft;
  if (!Number.isFinite(pixel) || !Number.isFinite(plotWidth) || pixel < 0 || pixel > plotWidth) return null;
  const [start, end] = axis.range || [];
  const numericStart = Number(start);
  const numericEnd = Number(end);
  if (!Number.isFinite(numericStart) || !Number.isFinite(numericEnd) || !plotWidth) return null;
  return numericStart + (pixel / plotWidth) * (numericEnd - numericStart);
}

function setAnnotationRange(start, end) {
  const numericStart = Number(start);
  const numericEnd = Number(end);
  if (!Number.isFinite(numericStart) || !Number.isFinite(numericEnd)) return;
  const left = Math.min(numericStart, numericEnd);
  const right = Math.max(numericStart, numericEnd);
  if (right <= left) return;
  $("annotationStartInput").value = left.toFixed(2);
  $("annotationEndInput").value = right.toFixed(2);
  setAnnotationStatus(`Segment sélectionné: ${left.toFixed(2)} s -> ${right.toFixed(2)} s`);
}

function bindAnnotationPlotSelection() {
  const plot = $("annotationSignalPlot");
  if (!plot || plot.dataset.selectionBound === "1") return;
  plot.dataset.selectionBound = "1";
  if (typeof plot.on === "function") {
    plot.removeAllListeners?.("plotly_click");
    plot.on("plotly_selected", event => {
      setAnnotationRangeFromPlotPoints(event?.points || []);
    });
    plot.on("plotly_click", event => {
      const x = Number(event?.points?.[0]?.x);
      if (!Number.isFinite(x)) return;
      if (state.annotationClickTarget === "start") {
        setAnnotationStart(x);
      } else {
        setAnnotationEnd(x);
      }
    });
  }
}

function renderAnnotationsTable() {
  const container = $("annotationsTable");
  if (!container) return;
  if (!state.annotations.length) {
    container.innerHTML = '<div class="empty">Aucun segment sauvegardé pour ce fichier</div>';
    return;
  }
  container.innerHTML = `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Début</th>
            <th>Fin</th>
            <th>Label</th>
            <th>Confiance</th>
            <th>Version</th>
            <th>Commentaire</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${state.annotations.map(annotation => `
            <tr>
              <td>${Number(annotation.start_time_sec).toFixed(2)} s</td>
              <td>${Number(annotation.end_time_sec).toFixed(2)} s</td>
              <td><span class="pill ok">${escapeHtml(annotation.label)}</span></td>
              <td>${annotation.confidence ?? "-"}</td>
              <td>v${escapeHtml(annotation.version_number || 1)}</td>
              <td>${escapeHtml(annotation.comment || "")}</td>
              <td>
                <button type="button" class="secondary annotation-edit" data-annotation-id="${escapeHtml(annotation.annotation_id)}">Éditer</button>
                <button type="button" class="danger annotation-delete" data-annotation-id="${escapeHtml(annotation.annotation_id)}">Supprimer</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
  container.querySelectorAll(".annotation-edit").forEach(button => {
    button.addEventListener("click", () => editAnnotation(button.dataset.annotationId));
  });
  container.querySelectorAll(".annotation-delete").forEach(button => {
    button.addEventListener("click", () => {
      wrapAction(() => deleteAnnotationById(button.dataset.annotationId), "Annotation supprimée")();
    });
  });
}

function formatSeconds(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${numeric.toFixed(2)} s` : "-";
}

function formatNumber(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "-";
  if (Math.abs(numeric) >= 1000) return numeric.toFixed(0);
  if (Math.abs(numeric) >= 10) return numeric.toFixed(2);
  return numeric.toFixed(3);
}

function annotationDate(value) {
  return value ? String(value).slice(0, 10) : "";
}

function filteredAnnotationCatalog() {
  const label = $("annotationCatalogLabelSelect")?.value || "";
  const fileFilter = ($("annotationCatalogFileInput")?.value || "").trim().toLowerCase();
  const dateFrom = $("annotationCatalogDateFromInput")?.value || "";
  const dateTo = $("annotationCatalogDateToInput")?.value || "";
  const minDuration = Number($("annotationCatalogMinDurationInput")?.value);
  const maxDuration = Number($("annotationCatalogMaxDurationInput")?.value);
  return state.annotationCatalog.filter(annotation => {
    const date = annotationDate(annotation.recorded_at);
    const fileName = `${annotation.source_dxd_name || ""} ${annotation.resampled_json_name || ""}`.toLowerCase();
    const duration = Number(annotation.duration_sec);
    if (label && annotation.label !== label) return false;
    if (fileFilter && !fileName.includes(fileFilter)) return false;
    if (dateFrom && (!date || date < dateFrom)) return false;
    if (dateTo && (!date || date > dateTo)) return false;
    if (Number.isFinite(minDuration) && duration < minDuration) return false;
    if (Number.isFinite(maxDuration) && duration > maxDuration) return false;
    return true;
  });
}

function renderAnnotationLabelSummary() {
  renderTable(
    "annotationLabelSummaryTable",
    [
      { key: "label", label: "Label", render: row => `<span class="pill ok">${escapeHtml(row.label)}</span>` },
      { key: "annotation_count", label: "Segments" },
      { key: "file_count", label: "Fichiers" },
      { key: "total_duration_sec", label: "Durée cumulée", render: row => formatSeconds(row.total_duration_sec) },
      { key: "last_used_at", label: "Dernier usage", render: row => escapeHtml(row.last_used_at || "-") },
    ],
    state.annotationLabelSummary,
    "Aucun label annoté"
  );
}

function renderAnnotationCatalog() {
  const rows = filteredAnnotationCatalog();
  renderTable(
    "annotationCatalogTable",
    [
      {
        key: "source_dxd_name",
        label: "Fichier",
        render: row => `<button type="button" class="link-button annotation-open" data-annotation-id="${escapeHtml(row.annotation_id)}">${escapeHtml(row.resampled_json_name || row.source_dxd_name)}</button>`,
      },
      { key: "recorded_at", label: "Date", render: row => escapeHtml(annotationDate(row.recorded_at) || "-") },
      { key: "label", label: "Label", render: row => `<span class="pill ok">${escapeHtml(row.label)}</span>` },
      { key: "start_time_sec", label: "Début", render: row => formatSeconds(row.start_time_sec) },
      { key: "end_time_sec", label: "Fin", render: row => formatSeconds(row.end_time_sec) },
      { key: "duration_sec", label: "Durée", render: row => formatSeconds(row.duration_sec) },
      { key: "comment", label: "Commentaire", render: row => escapeHtml(row.comment || "") },
    ],
    rows,
    "Aucune annotation dans le filtre"
  );
  $("annotationCatalogStatus").textContent = `${rows.length} annotation(s) affichée(s), ${state.annotationCatalog.length} total.`;
  document.querySelectorAll(".annotation-open").forEach(button => {
    button.addEventListener("click", () => {
      wrapAction(() => openAnnotationFromCatalog(button.dataset.annotationId), "Annotation ouverte")();
    });
  });
}

function selectedDynamicChannels() {
  return Array.from($("dynamicAnalysisChannelSelect")?.selectedOptions || [])
    .map(option => option.value);
}

function selectedDynamicLabels() {
  return Array.from($("dynamicAnalysisLabelSelect")?.selectedOptions || [])
    .map(option => option.value);
}

function dynamicOutputSchema() {
  const raw = $("dynamicAnalysisOutputSchemaInput")?.value.trim() || "{}";
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error("Schéma de sortie attendu invalide: JSON attendu.");
  }
}

function renderDynamicChannelOptions() {
  const select = $("dynamicAnalysisChannelSelect");
  if (!select) return;
  const previous = new Set(selectedDynamicChannels());
  const channels = state.explorationChannels.length ? state.explorationChannels : state.annotationChannels;
  select.innerHTML = channels.length
    ? channels.map(channel => `<option value="${escapeHtml(channel.value)}">${escapeHtml(channel.label || channel.value)}</option>`).join("")
    : '<option value="">Aucun canal disponible</option>';
  Array.from(select.options).forEach((option, index) => {
    option.selected = previous.has(option.value) || (!previous.size && index < 2);
  });
}

function renderDynamicLabelOptions() {
  const select = $("dynamicAnalysisLabelSelect");
  const categorySelect = $("dynamicAnalysisLabelCategorySelect");
  const previous = new Set(selectedDynamicLabels());
  if (select) {
    select.innerHTML = state.annotationLabels.length
      ? state.annotationLabels.map(label => `<option value="${escapeHtml(label)}">${escapeHtml(label)}</option>`).join("")
      : '<option value="">Aucun label disponible</option>';
    Array.from(select.options).forEach(option => {
      option.selected = previous.has(option.value) || !previous.size;
    });
  }
  if (categorySelect) {
    const previousCategory = categorySelect.value;
    categorySelect.innerHTML = state.annotationLabels.length
      ? state.annotationLabels.map(label => `<option value="${escapeHtml(label)}">${escapeHtml(label)}</option>`).join("")
      : '<option value="">Aucun label disponible</option>';
    categorySelect.value = state.annotationLabels.includes(previousCategory)
      ? previousCategory
      : (state.annotationLabels[0] || "");
  }
}

function renderDynamicPromptOptions() {
  const select = $("dynamicAnalysisPromptSelect");
  if (!select) return;
  const previous = select.value;
  select.innerHTML = [
    '<option value="">Protocole courant non sauvegardé</option>',
    ...state.dynamicPrompts.map(prompt => `<option value="${escapeHtml(prompt.dynamic_analysis_id)}">${escapeHtml(prompt.name)} · ${escapeHtml(prompt.label_category)}</option>`),
  ].join("");
  select.value = state.dynamicPrompts.some(prompt => prompt.dynamic_analysis_id === previous)
    ? previous
    : (state.dynamicSelectedAnalysisId || "");
}

function dynamicAnalysisPayload() {
  const dynamicAnalysis = state.dynamicAnalyses.find(item => item.dynamic_analysis_id === $("dynamicAnalysisPromptSelect")?.value);
  return {
    name: $("dynamicAnalysisNameInput")?.value.trim() || "Analyse dynamique",
    provider: "dry_run",
    model: null,
    prompt_id: null,
    system_prompt: $("dynamicAnalysisSystemPromptInput")?.value || "",
    user_prompt: $("dynamicAnalysisUserPromptInput")?.value || "",
    channels: selectedDynamicChannels(),
    labels: [dynamicAnalysis?.label_category || $("dynamicAnalysisLabelCategorySelect")?.value || selectedDynamicLabels().filter(Boolean)[0]].filter(Boolean),
    output_schema: dynamicOutputSchema(),
    context_before_sec: Number($("dynamicContextBeforeInput")?.value || 0),
    context_after_sec: Number($("dynamicContextAfterInput")?.value || 0),
    max_segments: Number($("dynamicMaxSegmentsInput")?.value || 25),
    max_points_per_segment: Number($("dynamicMaxPointsInput")?.value || 250),
  };
}

function renderDynamicContext(context) {
  state.dynamicContext = context;
  const summary = context?.summary || {};
  const summaryRows = [
    ["Segments", summary.segment_count ?? 0],
    ["Fichiers", summary.file_count ?? 0],
    ["Segments ignorés", summary.skipped_segment_count ?? 0],
    ["Canaux", (summary.channels || []).join(", ") || "-"],
    ["Labels", (summary.labels || []).join(", ") || "-"],
  ];
  const segmentRows = (context?.segments || []).slice(0, 6).map(segment => {
    const channels = Object.entries(segment.signal_context?.channels || {})
      .map(([name, channel]) => {
        const stats = channel.stats || {};
        const metrics = channel.metrics || {};
        return `${name}: amplitude ${formatNumber(stats.amplitude)}, pic ${formatNumber(metrics.peak_abs)}`;
      })
      .join(" · ");
    return `
      <tr>
        <td>${escapeHtml(segment.file_name || segment.file_id || "-")}</td>
        <td>${escapeHtml(segment.label || "-")}</td>
        <td>${formatNumber(segment.start_time_sec)} - ${formatNumber(segment.end_time_sec)}</td>
        <td>${escapeHtml(channels || "-")}</td>
      </tr>
    `;
  }).join("");
  $("dynamicContextSummary").innerHTML = `
    <div class="summary-grid">
      ${summaryRows.map(([label, value]) => `
        <div>
          <div class="label">${escapeHtml(label)}</div>
          <div class="value">${escapeHtml(value)}</div>
        </div>
      `).join("")}
    </div>
    <div class="table-wrap" style="margin-top:12px;">
      <table>
        <thead>
          <tr>
            <th>Fichier</th>
            <th>Label</th>
            <th>Segment (s)</th>
            <th>Résumé canaux</th>
          </tr>
        </thead>
        <tbody>${segmentRows || '<tr><td colspan="4">Aucun segment dans le contexte.</td></tr>'}</tbody>
      </table>
    </div>
  `;
  $("dynamicContextPreview").textContent = JSON.stringify(context || {}, null, 2);
}

function renderDynamicRuns() {
  renderTable(
    "dynamicAnalysisRunsTable",
    [
      {
        key: "name",
        label: "Annotation",
        render: row => `<button type="button" class="link-button dynamic-run-open" data-run-id="${escapeHtml(row.prediction_id)}">${escapeHtml(row.annotation_id)}</button>`,
      },
      { key: "created_at", label: "Date" },
      { key: "status", label: "Statut", render: row => `<span class="pill">${escapeHtml(row.status)}</span>` },
      { key: "input_context", label: "Fichier", render: row => escapeHtml(row.input_context?.segment?.file_name || "-") },
      { key: "confidence", label: "Confiance", render: row => escapeHtml(row.confidence || "-") },
    ],
    state.dynamicRuns,
    "Aucune prédiction"
  );
  document.querySelectorAll(".dynamic-run-open").forEach(button => {
    button.addEventListener("click", () => selectDynamicRun(button.dataset.runId));
  });
}

function selectDynamicRun(runId) {
  const run = state.dynamicRuns.find(item => item.prediction_id === runId || item.run_id === runId);
  if (!run) return;
  state.dynamicSelectedRunId = runId;
  state.dynamicSelectedPredictionId = run.prediction_id || "";
  renderDynamicContext(run.context || {
    summary: {
      segment_count: 1,
      file_count: 1,
      skipped_segment_count: 0,
      channels: Object.keys(run.input_context?.segment?.signal_context?.channels || {}),
      labels: [run.response_json?.label_category].filter(Boolean),
    },
    segments: run.input_context?.segment ? [run.input_context.segment] : [],
  });
  $("dynamicAnalysisResult").innerHTML = renderMarkdownLite(run.response_markdown);
  $("dynamicAnalysisCorrectionInput").value = run.response_markdown || "";
  $("saveDynamicAnalysisVersionBtn").disabled = false;
  renderDynamicRuns();
}

async function openAnnotationFromCatalog(annotationId) {
  const annotation = state.annotationCatalog.find(item => item.annotation_id === annotationId);
  if (!annotation) return;
  showAnnotationStep("annotate");
  if (!state.annotationFiles.some(file => file.file_id === annotation.file_id)) {
    if ($("annotationDateFromInput")) $("annotationDateFromInput").value = "";
    if ($("annotationDateToInput")) $("annotationDateToInput").value = "";
    await loadAnnotationFiles();
  }
  state.annotationFileId = annotation.file_id;
  $("annotationFileSelect").value = annotation.file_id;
  await loadAnnotationChannels();
  await loadAnnotations();
  await refreshAnnotationPlots();
  editAnnotation(annotation.annotation_id);
}

function annotationPayload() {
  const fileId = state.annotationFileId || $("annotationFileSelect")?.value;
  const start = Number($("annotationStartInput")?.value);
  const end = Number($("annotationEndInput")?.value);
  const label = $("annotationLabelSelect")?.value.trim();
  const confidenceValue = $("annotationConfidenceInput")?.value;
  if (!fileId) throw new Error("Aucun fichier sélectionné");
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
    throw new Error("Le segment doit avoir une fin strictement supérieure au début");
  }
  if (!label) throw new Error("Label requis");
  return {
    file_id: fileId,
    start_time_sec: start,
    end_time_sec: end,
    label,
    confidence: confidenceValue === "" ? null : Number(confidenceValue),
    comment: $("annotationCommentInput")?.value || null,
    metadata: {
      source: "app_v2_ui",
      channels: selectedAnnotationChannels(),
    },
  };
}

async function saveAnnotation() {
  const analysisId = currentAnalysisId();
  if (!analysisId) throw new Error("Aucune analyse active");
  const payload = annotationPayload();
  if (state.annotationEditingId) {
    await api(
      `/api/analyses/${encodeURIComponent(analysisId)}/annotations/${encodeURIComponent(state.annotationEditingId)}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          start_time_sec: payload.start_time_sec,
          end_time_sec: payload.end_time_sec,
          label: payload.label,
          confidence: payload.confidence,
          comment: payload.comment,
          metadata: payload.metadata,
        }),
      }
    );
  } else {
    await api(`/api/analyses/${encodeURIComponent(analysisId)}/annotations`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }
  resetAnnotationForm();
  await loadAnnotations();
  await loadAnnotationCatalog();
  await refreshAnnotationPlots();
}

async function deleteAnnotationById(annotationId) {
  if (!annotationId) return;
  const analysisId = currentAnalysisId();
  if (!analysisId) throw new Error("Aucune analyse active");
  await api(
    `/api/analyses/${encodeURIComponent(analysisId)}/annotations/${encodeURIComponent(annotationId)}`,
    { method: "DELETE" }
  );
  if (state.annotationEditingId === annotationId) {
    resetAnnotationForm();
  }
  await loadAnnotations();
  await loadAnnotationCatalog();
  await refreshAnnotationPlots();
}

async function renameAnnotationLabel() {
  const analysisId = currentAnalysisId();
  const labelId = $("annotationRenameOldLabelSelect")?.value;
  const newLabel = $("annotationRenameNewLabelInput")?.value.trim();
  if (!analysisId) throw new Error("Aucune analyse active");
  if (!labelId) throw new Error("Aucun label sélectionné");
  if (!newLabel) throw new Error("Nouveau label requis");
  const existing = state.annotationManagedLabels.find(label => label.label_id === labelId);
  await api(`/api/analyses/${encodeURIComponent(analysisId)}/annotation-labels/${encodeURIComponent(labelId)}`, {
    method: "PATCH",
    body: JSON.stringify({
      name: newLabel,
      description: existing?.description || null,
      color: existing?.color || null,
    }),
  });
  $("annotationRenameNewLabelInput").value = "";
  await loadAnnotations();
  await loadAnnotationCatalog();
  await refreshAnnotationPlots();
}

async function deleteSelectedAnnotationLabel() {
  const analysisId = currentAnalysisId();
  const labelId = $("annotationRenameOldLabelSelect")?.value;
  const label = state.annotationManagedLabels.find(item => item.label_id === labelId);
  if (!analysisId) throw new Error("Aucune analyse active");
  if (!labelId || !label) throw new Error("Aucun label sélectionné");
  if (!window.confirm(`Supprimer le label "${label.name}" ? Si le label est utilisé, ses annotations seront aussi supprimées.`)) {
    setStatus("Suppression annulée");
    return;
  }
  await api(`/api/analyses/${encodeURIComponent(analysisId)}/annotation-labels/${encodeURIComponent(labelId)}?delete_annotations=true`, {
    method: "DELETE",
  });
  await loadAnnotations();
  await loadAnnotationCatalog();
  await refreshAnnotationPlots();
}

async function createAnnotationLabel() {
  const analysisId = currentAnalysisId();
  const name = $("annotationNewLabelInput")?.value.trim();
  if (!analysisId) throw new Error("Aucune analyse active");
  if (!name) throw new Error("Nom de label requis");
  await api(`/api/analyses/${encodeURIComponent(analysisId)}/annotation-labels`, {
    method: "POST",
    body: JSON.stringify({
      name,
      description: $("annotationNewLabelDescriptionInput")?.value.trim() || null,
      color: $("annotationNewLabelColorInput")?.value || null,
    }),
  });
  $("annotationNewLabelInput").value = "";
  $("annotationNewLabelDescriptionInput").value = "";
  await loadAnnotationCatalog();
  $("annotationLabelSelect").value = name;
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
    state.annotationFiles = [];
    state.annotationChannels = [];
    state.annotationFileId = "";
    state.annotations = [];
    state.annotationLabels = [];
    state.annotationManagedLabels = [];
    state.annotationEditingId = "";
    state.annotationCatalog = [];
    state.annotationLabelSummary = [];
    state.dynamicPrompts = [];
    state.dynamicRuns = [];
    state.dynamicContext = null;
    state.dynamicSelectedRunId = "";
    state.validatedStructure = null;
    renderAll();
    return;
  }
  state.analysis = await api(`/api/analyses/${encodeURIComponent(analysisId)}`);
  state.selectedChannels = new Set();
  state.anomalies = [];
  state.annotationEditingId = "";
  await Promise.all([loadFiles(), loadEvents(), loadChannels()]);
  renderAll();
  await loadExplorationDateRange();
  await loadExplorationFiles();
  await loadAnnotationDateRange();
  await loadAnnotationFiles();
  await loadAnnotationCatalog();
  await loadDynamicAnalysis();
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
  state.annotationFiles = [];
  state.annotationChannels = [];
  state.annotationFileId = "";
  state.annotations = [];
  state.annotationLabels = [];
  state.annotationManagedLabels = [];
  state.annotationEditingId = "";
  state.annotationCatalog = [];
  state.annotationLabelSummary = [];
  state.dynamicPrompts = [];
  state.dynamicRuns = [];
  state.dynamicContext = null;
  state.dynamicSelectedRunId = "";
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
    if (button.dataset.view === "annotations") {
      wrapAction(async () => {
        await loadAnnotationDateRange();
        await loadAnnotationFiles();
        await loadAnnotationCatalog();
        resizeAnnotationPlotsSoon();
      }, "Annotations chargées")();
    }
    if (button.dataset.view === "dynamic-analysis") {
      wrapAction(loadDynamicAnalysis, "Analyse dynamique chargée")();
    }
  });

  $("analysisWorkflowTabs")?.addEventListener("click", event => {
    const button = event.target.closest("button[data-workflow-step]");
    if (!button || button.disabled) return;
    showWorkflowStep(button.dataset.workflowStep);
  });
  $("explorationTabs")?.addEventListener("click", event => {
    const button = event.target.closest("button[data-exploration-step]");
    if (!button) return;
    showExplorationStep(button.dataset.explorationStep);
    if (button.dataset.explorationStep === "parametric") {
      wrapAction(async () => {
        await loadParametricDateRange();
        await loadParametricFiles();
        await refreshParametric();
      }, "Vision paramétrique chargée")();
    }
  });
  $("annotationTabs")?.addEventListener("click", event => {
    const button = event.target.closest("button[data-annotation-step]");
    if (!button) return;
    showAnnotationStep(button.dataset.annotationStep);
    if (button.dataset.annotationStep === "catalog") {
      wrapAction(loadAnnotationCatalog, "Catalogue annotations chargé")();
    }
  });
  $("dynamicAnalysisTabs")?.addEventListener("click", event => {
    const button = event.target.closest("button[data-dynamic-step]");
    if (!button) return;
    showDynamicAnalysisStep(button.dataset.dynamicStep);
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
    await refreshParametric();
  }, "Exploration chargée"));
  ["explorationDateFromInput", "explorationDateToInput"].forEach(id => {
    const input = $(id);
    ["input", "change"].forEach(eventName => {
      input?.addEventListener(eventName, scheduleExplorationDateFilter);
    });
  });
  $("explorationPrevBtn")?.addEventListener("click", wrapAction(() => goToRelativeExplorationFile(-1), "Fichier précédent"));
  $("explorationNextBtn")?.addEventListener("click", wrapAction(() => goToRelativeExplorationFile(1), "Fichier suivant"));
  $("parametricFileSelect")?.addEventListener("change", wrapAction(async () => {
    state.parametricFileId = $("parametricFileSelect").value;
    await loadParametricChannels();
    await refreshParametric();
  }, "Vision paramétrique chargée"));
  ["parametricDateFromInput", "parametricDateToInput"].forEach(id => {
    $(id)?.addEventListener("change", wrapAction(async () => {
      await loadParametricFiles();
      await refreshParametric();
    }, "Fichiers filtrés"));
  });
  $("parametricPrevBtn")?.addEventListener("click", wrapAction(() => goToRelativeParametricFile(-1), "Fichier précédent"));
  $("parametricNextBtn")?.addEventListener("click", wrapAction(() => goToRelativeParametricFile(1), "Fichier suivant"));
  $("annotationFileSelect")?.addEventListener("change", wrapAction(async () => {
    state.annotationFileId = $("annotationFileSelect").value;
    resetAnnotationForm();
    await loadAnnotationChannels();
    await loadAnnotations();
    await refreshAnnotationPlots();
  }, "Annotations chargées"));
  ["annotationDateFromInput", "annotationDateToInput"].forEach(id => {
    const input = $(id);
    ["input", "change"].forEach(eventName => {
      input?.addEventListener(eventName, scheduleAnnotationDateFilter);
    });
  });
  $("annotationPrevBtn")?.addEventListener("click", wrapAction(() => goToRelativeAnnotationFile(-1), "Fichier précédent"));
  $("annotationNextBtn")?.addEventListener("click", wrapAction(() => goToRelativeAnnotationFile(1), "Fichier suivant"));
  $("annotationMaxPointsInput")?.addEventListener("change", wrapAction(refreshAnnotationPlots, "Signal annotable chargé"));
  $("annotationStartInput")?.addEventListener("change", () => {
    setAnnotationStart(Number($("annotationStartInput").value));
  });
  $("annotationEndInput")?.addEventListener("change", () => {
    setAnnotationEnd(Number($("annotationEndInput").value));
  });
  $("annotationEndRangeInput")?.addEventListener("input", () => {
    setAnnotationEnd(Number($("annotationEndRangeInput").value));
  });
  $("annotationClickStartBtn")?.addEventListener("click", () => setAnnotationClickTarget("start"));
  $("annotationClickEndBtn")?.addEventListener("click", () => setAnnotationClickTarget("end"));
  [
    "annotationCatalogDateFromInput",
    "annotationCatalogDateToInput",
    "annotationCatalogLabelSelect",
    "annotationCatalogFileInput",
    "annotationCatalogMinDurationInput",
    "annotationCatalogMaxDurationInput",
  ].forEach(id => {
    const node = $(id);
    ["input", "change"].forEach(eventName => {
      node?.addEventListener(eventName, renderAnnotationCatalog);
    });
  });
  $("createAnnotationLabelBtn")?.addEventListener("click", wrapAction(createAnnotationLabel, "Label créé"));
  $("renameAnnotationLabelBtn")?.addEventListener("click", wrapAction(renameAnnotationLabel, "Label renommé"));
  $("deleteAnnotationLabelBtn")?.addEventListener("click", wrapAction(deleteSelectedAnnotationLabel, "Label supprimé"));
  $("dynamicAnalysisPromptSelect")?.addEventListener("change", () => {
    const prompt = state.dynamicPrompts.find(item => item.dynamic_analysis_id === $("dynamicAnalysisPromptSelect").value);
    if (!prompt) return;
    state.dynamicSelectedAnalysisId = prompt.dynamic_analysis_id;
    $("dynamicAnalysisPromptNameInput").value = prompt.name || "";
    $("dynamicAnalysisProtocolDescriptionInput").value = `Catégorie: ${prompt.label_category || "-"}`;
    $("dynamicAnalysisSystemPromptInput").value = prompt.system_prompt || "";
    if ($("dynamicAnalysisLabelCategorySelect")) $("dynamicAnalysisLabelCategorySelect").value = prompt.label_category || "";
    $("dynamicAnalysisOutputSchemaInput").value = JSON.stringify(prompt.output_schema || {}, null, 2);
    renderDynamicChannelOptions();
    Array.from($("dynamicAnalysisChannelSelect")?.options || []).forEach(option => {
      option.selected = (prompt.selected_channels || []).includes(option.value);
    });
    wrapAction(loadDynamicAnalysis, "Analyse dynamique chargée")();
  });
  $("saveDynamicPromptBtn")?.addEventListener("click", wrapAction(saveDynamicPrompt, "Protocole sauvegardé"));
  $("buildDynamicContextBtn")?.addEventListener("click", wrapAction(buildDynamicContext, "Contexte construit"));
  $("runDynamicAnalysisBtn")?.addEventListener("click", wrapAction(runDynamicAnalysis, "Analyse dynamique lancée"));
  $("saveDynamicAnalysisVersionBtn")?.addEventListener("click", wrapAction(saveDynamicAnalysisVersion, "Correction sauvegardée"));
  $("saveAnnotationBtn")?.addEventListener("click", wrapAction(saveAnnotation, "Annotation sauvegardée"));
  $("resetAnnotationBtn")?.addEventListener("click", () => {
    resetAnnotationForm();
    setAnnotationStatus("Nouveau segment");
  });
  const explorationChannelSelect = $("explorationChannelSelect");
  ["input", "change", "click", "mouseup", "keyup"].forEach(eventName => {
    explorationChannelSelect?.addEventListener(eventName, () => {
      setTimeout(refreshExplorationFromChannelSelection, 0);
    });
  });
  const parametricChannelSelect = $("parametricChannelSelect");
  ["input", "change", "click", "mouseup", "keyup"].forEach(eventName => {
    parametricChannelSelect?.addEventListener(eventName, () => {
      setTimeout(refreshParametricFromChannelSelection, 0);
    });
  });
  const annotationChannelSelect = $("annotationChannelSelect");
  ["input", "change", "click", "mouseup", "keyup"].forEach(eventName => {
    annotationChannelSelect?.addEventListener(eventName, () => {
      setTimeout(refreshAnnotationFromChannelSelection, 0);
    });
  });
  ["explorationMaxPointsInput", "explorationMultiAxisInput", "explorationSegmentSourceSelect", "explorationLabelSelect"].forEach(id => {
    $(id)?.addEventListener("change", wrapAction(refreshExploration, "Exploration chargée"));
  });
  $("parametricScopeSelect")?.addEventListener("change", wrapAction(async () => {
    updateParametricScopeUi();
    await refreshParametric();
  }, "Vision paramétrique chargée"));
  ["parametricMaxPointsInput", "parametricScatterInput"].forEach(id => {
    $(id)?.addEventListener("change", wrapAction(refreshParametric, "Vision paramétrique chargée"));
  });
  document.addEventListener("keydown", event => {
    const activeView = document.querySelector(".view.active");
    if (!activeView) return;
    if (activeView.id === "view-annotations") {
      if (event.target && ["INPUT", "SELECT", "TEXTAREA"].includes(event.target.tagName)) return;
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        wrapAction(() => goToRelativeAnnotationFile(-1), "Fichier précédent")();
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        wrapAction(() => goToRelativeAnnotationFile(1), "Fichier suivant")();
      }
      return;
    }
    if (activeView.id !== "view-exploration") return;
    const activeExplorationStep = document.querySelector(".exploration-step.active");
    if (!activeExplorationStep || !["exploration-temporal", "exploration-parametric"].includes(activeExplorationStep.id)) return;
    if (event.target && ["INPUT", "SELECT", "TEXTAREA"].includes(event.target.tagName)) return;
    if (activeExplorationStep.id === "exploration-parametric" && $("parametricScopeSelect")?.value === "filtered") return;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      const action = activeExplorationStep.id === "exploration-parametric"
        ? () => goToRelativeParametricFile(-1)
        : () => goToRelativeExplorationFile(-1);
      wrapAction(action, "Fichier précédent")();
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      const action = activeExplorationStep.id === "exploration-parametric"
        ? () => goToRelativeParametricFile(1)
        : () => goToRelativeExplorationFile(1);
      wrapAction(action, "Fichier suivant")();
    }
  });
  window.addEventListener("resize", () => {
    resizePlots(["explorationSignalPlot", "explorationTrajectoryPlot", "parametricPlot", "annotationSignalPlot", "annotationTrajectoryPlot"]);
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
