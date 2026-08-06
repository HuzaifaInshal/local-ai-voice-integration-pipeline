// -------------------------------------------------------------
// CHARTS ENGINE & FULL-SCREEN MODAL CONTROLLER
// -------------------------------------------------------------

let currentModalChartEvent = null;

function openChartModal(event) {
  if (!event) return;
  const chartModal = document.getElementById("chartModal");
  const modalChartTitle = document.getElementById("modalChartTitle");
  const modalChartMeta = document.getElementById("modalChartMeta");
  const modalChartCanvas = document.getElementById("modalChartCanvas");

  if (!chartModal || !modalChartCanvas) return;

  currentModalChartEvent = event;
  modalChartTitle.textContent = event.title || "Visualization";
  modalChartMeta.textContent = chartMetaText(event);

  chartModal.classList.add("active");
  document.body.style.overflow = "hidden";

  setTimeout(() => {
    const rect = modalChartCanvas.getBoundingClientRect();
    modalChartCanvas.width = rect.width * (window.devicePixelRatio || 1);
    modalChartCanvas.height = rect.height * (window.devicePixelRatio || 1);
    drawChart(modalChartCanvas, event);
  }, 50);
}

function closeChartModal() {
  const chartModal = document.getElementById("chartModal");
  if (chartModal) {
    chartModal.classList.remove("active");
  }
  document.body.style.overflow = "";
  currentModalChartEvent = null;
}

document.addEventListener("DOMContentLoaded", () => {
  const chartModal = document.getElementById("chartModal");
  const modalCloseBtn = document.getElementById("modalCloseBtn");
  const modalPngBtn = document.getElementById("modalPngBtn");
  const modalChartCanvas = document.getElementById("modalChartCanvas");

  if (modalCloseBtn) {
    modalCloseBtn.addEventListener("click", closeChartModal);
  }
  if (chartModal) {
    chartModal.addEventListener("click", (e) => {
      if (e.target === chartModal) closeChartModal();
    });
  }
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && chartModal && chartModal.classList.contains("active")) {
      closeChartModal();
    }
  });
  if (modalPngBtn) {
    modalPngBtn.addEventListener("click", () => {
      if (currentModalChartEvent && modalChartCanvas) {
        downloadCanvasPng(modalChartCanvas, currentModalChartEvent.title || "chart");
      }
    });
  }
});

function chartMetaText(event) {
  const source = event.source_columns || {};
  if (event.chart_type === "pie" || event.chart_type === "donut") {
    return `${event.chart_type} • ${source.label || "label"} by ${source.value || "value"}`;
  }
  if (event.chart_type === "scatter") {
    return `scatter • ${source.x || "x"} vs ${source.y || "y"}`;
  }
  const series = source.series ? ` grouped by ${source.series}` : "";
  return `${event.chart_type || "chart"} • ${source.x || "x"} vs ${source.y || "y"}${series}`;
}

function downloadCsv(event) {
  const columns = event.columns || [];
  const rows = event.rows || [];
  const lines = [columns.map(csvCell).join(",")];
  rows.forEach(row => {
    lines.push(columns.map(column => csvCell(row[column] ?? "")).join(","));
  });
  downloadBlob(lines.join("\n"), safeFilename(event.title || "table") + ".csv", "text/csv;charset=utf-8");
}

function csvCell(value) {
  const text = String(value ?? "");
  if (/[",\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function downloadCanvasPng(canvas, title) {
  const link = document.createElement("a");
  link.download = safeFilename(title || "chart") + ".png";
  link.href = canvas.toDataURL("image/png");
  link.click();
}

function downloadBlob(content, filename, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function safeFilename(value) {
  return String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80) || "download";
}

function drawChart(canvas, event) {
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const chartType = event.chart_type || "bar";

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.font = "12px Inter, sans-serif";

  if (chartType === "pie" || chartType === "donut") {
    drawPieDonutChart(ctx, event, width, height, chartType === "donut");
    return;
  }
  if (chartType === "scatter") {
    drawScatterChart(ctx, event, width, height);
    return;
  }
  if (chartType === "horizontal_bar") {
    drawHorizontalBarChart(ctx, event, width, height);
    return;
  }
  if (chartType === "line") {
    drawLineChart(ctx, event, width, height);
    return;
  }

  drawBarChart(ctx, event, width, height);
}

function drawAxes(ctx, width, height, pad, min, max) {
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const range = Math.max(max - min, 1);
  ctx.strokeStyle = "#e5e7eb";
  ctx.fillStyle = "#6b7280";
  ctx.lineWidth = 1;

  for (let i = 0; i <= 4; i++) {
    const y = pad.top + (plotH * i / 4);
    const value = max - (range * i / 4);
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
    ctx.fillText(formatAxisNumber(value), 8, y + 4);
  }

  ctx.strokeStyle = "#cbd5e1";
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, pad.top + plotH);
  ctx.lineTo(width - pad.right, pad.top + plotH);
  ctx.stroke();
  return { plotW, plotH, range };
}

function drawBarChart(ctx, event, width, height) {
  const labels = event.labels || [];
  const datasets = event.datasets || [];
  const values = datasets.flatMap(dataset => dataset.data || []).filter(value => Number.isFinite(Number(value))).map(Number);
  if (!labels.length || !values.length) return;

  const pad = { top: 18, right: 20, bottom: 62, left: 58 };
  const max = Math.max(...values, 1);
  const min = 0;
  const { plotW, plotH, range } = drawAxes(ctx, width, height, pad, min, max);
  const gap = 8;
  const groupW = Math.max(14, (plotW - gap * (labels.length - 1)) / labels.length);
  const barW = Math.max(5, groupW / Math.max(datasets.length, 1) - 3);

  labels.forEach((label, index) => {
    datasets.forEach((dataset, datasetIndex) => {
      const value = Number((dataset.data || [])[index]);
      if (!Number.isFinite(value)) return;
      const x = pad.left + index * (groupW + gap) + datasetIndex * (barW + 3);
      const h = Math.max(1, ((value - min) / range) * plotH);
      const y = pad.top + plotH - h;
      ctx.fillStyle = chartColor(datasetIndex);
      ctx.fillRect(x, y, barW, h);
    });
    drawXAxisLabel(ctx, label, pad.left + index * (groupW + gap) + groupW / 2, pad.top + plotH + 18, groupW + gap);
  });
}

function drawHorizontalBarChart(ctx, event, width, height) {
  const labels = event.labels || [];
  const dataset = (event.datasets || [])[0] || {};
  const values = (dataset.data || []).map(Number).filter(Number.isFinite);
  if (!labels.length || !values.length) return;

  const pad = { top: 18, right: 34, bottom: 28, left: 132 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const max = Math.max(...values, 1);
  const barH = Math.max(10, plotH / labels.length - 8);

  ctx.strokeStyle = "#e5e7eb";
  ctx.fillStyle = "#6b7280";
  for (let i = 0; i <= 4; i++) {
    const x = pad.left + plotW * i / 4;
    ctx.beginPath();
    ctx.moveTo(x, pad.top);
    ctx.lineTo(x, pad.top + plotH);
    ctx.stroke();
    ctx.fillText(formatAxisNumber(max * i / 4), x - 10, height - 8);
  }

  labels.forEach((label, index) => {
    const value = Number((dataset.data || [])[index]);
    if (!Number.isFinite(value)) return;
    const y = pad.top + index * (barH + 8);
    const w = Math.max(1, value / max * plotW);
    ctx.fillStyle = "#3b82f6";
    ctx.fillRect(pad.left, y, w, barH);
    ctx.fillStyle = "#6b7280";
    ctx.textAlign = "right";
    ctx.fillText(shortLabel(label, 18), pad.left - 10, y + barH * 0.7);
  });
  ctx.textAlign = "left";
}

function drawLineChart(ctx, event, width, height) {
  const labels = event.labels || [];
  const datasets = event.datasets || [];
  const values = datasets.flatMap(dataset => dataset.data || []).filter(value => Number.isFinite(Number(value))).map(Number);
  if (!labels.length || !values.length) return;

  const pad = { top: 18, right: 24, bottom: 62, left: 58 };
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const { plotW, plotH, range } = drawAxes(ctx, width, height, pad, min, max);

  datasets.forEach((dataset, datasetIndex) => {
    ctx.strokeStyle = chartColor(datasetIndex);
    ctx.fillStyle = chartColor(datasetIndex);
    ctx.lineWidth = 2;
    ctx.beginPath();
    let hasStarted = false;
    labels.forEach((label, index) => {
      const value = Number((dataset.data || [])[index]);
      if (!Number.isFinite(value)) return;
      const x = pad.left + (labels.length === 1 ? plotW / 2 : index * plotW / (labels.length - 1));
      const y = pad.top + plotH - ((value - min) / range) * plotH;
      if (!hasStarted) {
        ctx.moveTo(x, y);
        hasStarted = true;
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();
    labels.forEach((label, index) => {
      const value = Number((dataset.data || [])[index]);
      if (!Number.isFinite(value)) return;
      const x = pad.left + (labels.length === 1 ? plotW / 2 : index * plotW / (labels.length - 1));
      const y = pad.top + plotH - ((value - min) / range) * plotH;
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();
      if (datasetIndex === 0) drawXAxisLabel(ctx, label, x, pad.top + plotH + 18, 90);
    });
  });
}

function drawScatterChart(ctx, event, width, height) {
  const dataset = (event.datasets || [])[0] || {};
  const points = dataset.data || [];
  const xs = points.map(point => Number(point.x)).filter(Number.isFinite);
  const ys = points.map(point => Number(point.y)).filter(Number.isFinite);
  if (!xs.length || !ys.length) return;

  const pad = { top: 18, right: 24, bottom: 48, left: 68 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const rangeX = Math.max(maxX - minX, 1);
  const rangeY = Math.max(maxY - minY, 1);
  drawAxes(ctx, width, height, pad, minY, maxY);

  ctx.fillStyle = "#2563eb";
  points.forEach(point => {
    const xVal = Number(point.x);
    const yVal = Number(point.y);
    if (!Number.isFinite(xVal) || !Number.isFinite(yVal)) return;
    const x = pad.left + ((xVal - minX) / rangeX) * plotW;
    const y = pad.top + plotH - ((yVal - minY) / rangeY) * plotH;
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
  });
}

function drawPieDonutChart(ctx, event, width, height, isDonut) {
  const labels = event.labels || [];
  const dataset = (event.datasets || [])[0] || {};
  const values = (dataset.data || []).map(Number);
  const total = values.reduce((sum, value) => Number.isFinite(value) ? sum + Math.max(value, 0) : sum, 0);
  if (!labels.length || total <= 0) return;

  const cx = width * 0.38;
  const cy = height / 2;
  const radius = Math.min(height * 0.34, width * 0.26);
  let start = -Math.PI / 2;
  values.forEach((value, index) => {
    if (!Number.isFinite(value) || value <= 0) return;
    const angle = (value / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, radius, start, start + angle);
    ctx.closePath();
    ctx.fillStyle = chartColor(index);
    ctx.fill();
    start += angle;
  });

  if (isDonut) {
    ctx.beginPath();
    ctx.fillStyle = "#ffffff";
    ctx.arc(cx, cy, radius * 0.58, 0, Math.PI * 2);
    ctx.fill();
  }

  const legendX = width * 0.68;
  let legendY = 42;
  labels.slice(0, 10).forEach((label, index) => {
    ctx.fillStyle = chartColor(index);
    ctx.fillRect(legendX, legendY - 10, 10, 10);
    ctx.fillStyle = "#374151";
    ctx.fillText(`${shortLabel(label, 24)} (${formatAxisNumber(values[index] || 0)})`, legendX + 16, legendY);
    legendY += 20;
  });
}

function drawXAxisLabel(ctx, label, x, y, maxWidth) {
  const text = String(label ?? "");
  const shortened = text.length > 18 ? text.slice(0, 15) + "..." : text;
  ctx.save();
  ctx.fillStyle = "#6b7280";
  ctx.textAlign = "center";
  ctx.translate(x, y);
  ctx.rotate(-Math.PI / 7);
  ctx.fillText(shortened, 0, 0, maxWidth);
  ctx.restore();
}

function formatAxisNumber(value) {
  if (Math.abs(value) >= 1000000000) return (value / 1000000000).toFixed(1) + "B";
  if (Math.abs(value) >= 1000000) return (value / 1000000).toFixed(1) + "M";
  if (Math.abs(value) >= 1000) return (value / 1000).toFixed(1) + "K";
  return Number(value).toFixed(value % 1 === 0 ? 0 : 1);
}

function shortLabel(value, maxLength) {
  const text = String(value ?? "");
  return text.length > maxLength ? text.slice(0, maxLength - 3) + "..." : text;
}

function chartColor(index) {
  const colors = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#14b8a6", "#f97316", "#64748b"];
  return colors[index % colors.length];
}
