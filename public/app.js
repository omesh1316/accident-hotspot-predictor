const API_URL = "/api";
const palette = { fatal: "#d5584e", serious: "#d59a31", slight: "#4a9a70", green: "#287963" };
const charts = {};
let map;
let hotspotLayer;
let dashboardOptions;

function severityColor(label) {
  const name = label.toLowerCase();
  if (name.includes("fatal")) return palette.fatal;
  if (name.includes("serious")) return palette.serious;
  return palette.slight;
}

function fillSelect(select, values, firstLabel) {
  if (!select) return;
  const original = select.value;
  select.replaceChildren();
  if (firstLabel) {
    const allOption = document.createElement("option");
    allOption.value = "All";
    allOption.textContent = firstLabel;
    select.append(allOption);
  }
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  });
  if ([...select.options].some((option) => option.value === original)) select.value = original;
}

function setPredictionOptions(options) {
  dashboardOptions = options;
  fillSelect(document.querySelector("#weatherFilter"), options.weather, "All conditions");
  fillSelect(document.querySelector("#dayFilter"), options.day, "All days");
  fillSelect(document.querySelector("#severityFilter"), options.severity, "All severities");
  const inputs = {
    day_of_week: options.day,
    weather: options.weather,
    road_surface: options.road_surface,
    light_conditions: options.light_conditions,
    cause: options.cause,
    junction_type: options.junction_type,
  };
  Object.entries(inputs).forEach(([name, values]) => fillSelect(document.querySelector(`[name="${name}"]`), values));
  fillSelect(document.querySelector("#hourInput"), Array.from({ length: 24 }, (_, hour) => String(hour).padStart(2, "0")));
  fillSelect(document.querySelector("#vehiclesInput"), Array.from({ length: 10 }, (_, index) => String(index + 1)));
  fillSelect(document.querySelector("#casualtiesInput"), Array.from({ length: 10 }, (_, index) => String(index + 1)));
  document.querySelector("#hourInput").value = "12";
  document.querySelector("#vehiclesInput").value = "2";
  document.querySelector("#casualtiesInput").value = "1";
}

function createChart(id, type, data, options) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  if (charts[id]) {
    charts[id].data = data;
    charts[id].update();
    return;
  }
  charts[id] = new Chart(canvas, { type, data, options });
}

const commonChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 350 },
  plugins: { legend: { labels: { color: "#68766f", boxWidth: 9, boxHeight: 9, usePointStyle: true, pointStyle: "circle", font: { family: "DM Sans", size: 10 } } } },
};
const axisStyle = { border: { display: false }, grid: { color: "#edf1ed", drawTicks: false }, ticks: { color: "#7e8a83", font: { family: "DM Sans", size: 10 } } };

function renderCharts(data) {
  const severityLabels = Object.keys(data.by_severity);
  createChart("severityChart", "doughnut", {
    labels: severityLabels,
    datasets: [{ data: severityLabels.map((label) => data.by_severity[label]), backgroundColor: severityLabels.map(severityColor), borderWidth: 3, borderColor: "#fff", hoverOffset: 5 }],
  }, { ...commonChartOptions, cutout: "68%", plugins: { ...commonChartOptions.plugins, legend: { position: "bottom", labels: commonChartOptions.plugins.legend.labels, padding: 17 } } });

  createChart("dayChart", "bar", {
    labels: data.by_day.map((item) => item.day.slice(0, 3)),
    datasets: [{ data: data.by_day.map((item) => item.count), backgroundColor: "#4b9279", borderRadius: 3, maxBarThickness: 28 }],
  }, { ...commonChartOptions, plugins: { legend: { display: false }, tooltip: { enabled: true } }, scales: { x: { ...axisStyle, grid: { display: false } }, y: { ...axisStyle, beginAtZero: true, ticks: { ...axisStyle.ticks, precision: 0 } } } });

  const weatherRows = data.weather_severity;
  const weatherNames = weatherRows.map((item) => item.weather);
  const outcomeNames = ["Fatal injury", "Serious Injury", "Slight Injury"];
  createChart("weatherChart", "bar", {
    labels: weatherNames,
    datasets: outcomeNames.map((name) => ({ label: name, data: weatherRows.map((item) => item[name]), backgroundColor: severityColor(name), borderRadius: 2, maxBarThickness: 24 })),
  }, { ...commonChartOptions, plugins: { ...commonChartOptions.plugins, legend: { position: "bottom", labels: commonChartOptions.plugins.legend.labels, padding: 12 } }, scales: { x: { ...axisStyle, grid: { display: false }, ticks: { ...axisStyle.ticks, maxRotation: 28, minRotation: 0 } }, y: { ...axisStyle, beginAtZero: true, ticks: { ...axisStyle.ticks, precision: 0 } } } });

  const causes = data.top_causes.slice(0, 8).reverse();
  createChart("causesChart", "bar", {
    labels: causes.map((item) => item.cause),
    datasets: [{ data: causes.map((item) => item.count), backgroundColor: "#d9a653", borderRadius: 3, maxBarThickness: 18 }],
  }, { ...commonChartOptions, indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { ...axisStyle, beginAtZero: true, ticks: { ...axisStyle.ticks, precision: 0 } }, y: { ...axisStyle, grid: { display: false }, ticks: { ...axisStyle.ticks, autoSkip: false } } } });
}

function popupElement(item) {
  const content = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = item.area;
  const count = document.createElement("div");
  count.textContent = `${item.count.toLocaleString()} recorded accidents`;
  content.append(title, count);
  return content;
}

function renderMap(hotspots) {
  if (!window.L) return;
  if (!map) {
    map = L.map("hotspotsMap", { scrollWheelZoom: false }).setView([9.0, 38.7], 10);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "&copy; OpenStreetMap contributors" }).addTo(map);
    hotspotLayer = L.layerGroup().addTo(map);
  }
  hotspotLayer.clearLayers();
  const peak = Math.max(1, ...hotspots.map((item) => item.count));
  hotspots.forEach((item) => {
    const intensity = item.count / peak;
    L.circleMarker([item.latitude, item.longitude], {
      radius: 6 + Math.sqrt(intensity) * 13,
      color: intensity > 0.55 ? palette.fatal : "#c78639",
      weight: 1,
      fillColor: intensity > 0.55 ? palette.fatal : "#e5a74f",
      fillOpacity: 0.32 + intensity * 0.38,
    }).bindPopup(popupElement(item)).addTo(hotspotLayer);
  });
  document.querySelector("#hotspotCount").textContent = `${hotspots.length} AREAS`;
  window.setTimeout(() => map.invalidateSize(), 50);
}

function renderDashboard(data) {
  document.querySelector("#totalMetric").textContent = data.total.toLocaleString();
  document.querySelector("#fatalMetric").textContent = data.fatal.toLocaleString();
  document.querySelector("#seriousMetric").textContent = data.serious.toLocaleString();
  document.querySelector("#slightMetric").textContent = data.slight.toLocaleString();
  renderCharts(data);
  renderMap(data.hotspots);
}

async function loadDashboard() {
  const params = new URLSearchParams({ action: "dashboard" });
  ["weather", "day", "severity"].forEach((key) => {
    const value = document.getElementById(`${key}Filter`).value;
    if (value !== "All") params.set(key, value);
  });
  document.querySelector("#overviewView").classList.add("is-loading");
  try {
    const response = await fetch(`${API_URL}?${params}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Dashboard request failed");
    if (!dashboardOptions) setPredictionOptions(data.options);
    renderDashboard(data);
  } catch (error) {
    showPageError(error.message);
  } finally {
    document.querySelector("#overviewView").classList.remove("is-loading");
  }
}

function showPageError(message) {
  let alert = document.querySelector("#pageError");
  if (!alert) {
    alert = document.createElement("p");
    alert.id = "pageError";
    alert.className = "page-error";
    document.querySelector("main").prepend(alert);
  }
  alert.textContent = message;
}

function setView(view) {
  const prediction = view === "prediction";
  document.querySelector("#overviewView").hidden = prediction;
  document.querySelector("#predictionView").hidden = !prediction;
  document.querySelectorAll(".view-tab").forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  if (prediction) window.scrollTo({ top: 0, behavior: "smooth" });
  if (!prediction && map) window.setTimeout(() => map.invalidateSize(), 50);
}

function showPredictionResult(result) {
  const content = document.querySelector("#resultContent");
  const status = document.querySelector("#resultStatus");
  const kind = result.class === 0 ? "risk-high" : result.class === 1 ? "risk-medium" : "risk-low";
  status.className = `result-status ${kind}`;
  document.querySelector("#riskLabel").textContent = result.class === 0 ? "CRITICAL RISK CLASS" : result.class === 1 ? "ELEVATED RISK CLASS" : "LOWER RISK CLASS";
  document.querySelector("#resultSeverity").textContent = result.severity;
  document.querySelector("#confidenceValue").textContent = `${result.confidence}%`;
  const list = document.querySelector("#probabilityList");
  list.replaceChildren();
  result.probabilities.forEach((probability) => {
    const row = document.createElement("div");
    row.className = "probability-row";
    const details = document.createElement("div");
    const name = document.createElement("span");
    name.className = "probability-name";
    name.textContent = probability.name;
    const track = document.createElement("div");
    track.className = "probability-track";
    const fill = document.createElement("div");
    fill.className = `probability-fill ${probability.name.toLowerCase().includes("fatal") ? "fatal" : probability.name.toLowerCase().includes("serious") ? "serious" : ""}`;
    fill.style.width = `${probability.value}%`;
    track.append(fill);
    details.append(name, track);
    const value = document.createElement("span");
    value.className = "probability-value";
    value.textContent = `${probability.value}%`;
    row.append(details, value);
    list.append(row);
  });
  document.querySelector("#resultEmpty").hidden = true;
  document.querySelector("#resultLoading").hidden = true;
  content.hidden = false;
  window.lucide?.createIcons();
}

async function submitPrediction(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const submitButton = form.querySelector("button[type='submit']");
  const loading = document.querySelector("#resultLoading");
  document.querySelector("#resultEmpty").hidden = true;
  document.querySelector("#resultContent").hidden = true;
  loading.hidden = false;
  submitButton.disabled = true;
  try {
    const payload = Object.fromEntries(new FormData(form).entries());
    ["hour", "num_vehicles", "num_casualties"].forEach((key) => { payload[key] = Number(payload[key]); });
    const response = await fetch(`${API_URL}?action=predict`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Prediction request failed");
    showPredictionResult(result);
  } catch (error) {
    loading.hidden = true;
    document.querySelector("#resultEmpty").hidden = false;
    document.querySelector("#resultEmpty h3").textContent = "Estimate unavailable";
    document.querySelector("#resultEmpty p:last-child").textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.lucide?.createIcons();
  document.querySelectorAll(".view-tab").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
  document.querySelector("#openPrediction").addEventListener("click", () => setView("prediction"));
  ["weatherFilter", "dayFilter", "severityFilter"].forEach((id) => document.getElementById(id).addEventListener("change", loadDashboard));
  document.querySelector("#resetFilters").addEventListener("click", () => {
    ["weatherFilter", "dayFilter", "severityFilter"].forEach((id) => { document.getElementById(id).value = "All"; });
    loadDashboard();
  });
  document.querySelector("#predictionForm").addEventListener("submit", submitPrediction);
  loadDashboard();
});