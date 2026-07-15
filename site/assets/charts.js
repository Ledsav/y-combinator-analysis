// Hand-built D3 chart helpers for the Phase 13 site. Each render*
// function takes a DOM container and data already shaped by
// scripts/export_site_data.py, and draws an SVG chart with a hover
// tooltip. Color always follows the two-hue model: technical = denim,
// practical = gold -- never a third "brand" accent.

const CHART_COLORS = {
  technical: "#2B4C7E",
  practical: "#C08A2E",
  ink: "#1B1B18",
  inkMuted: "#5C594F",
  surface: "#F1EFE6",
};

function makeTooltip(container) {
  return d3.select(container).append("div").attr("class", "chart-tooltip");
}

function showTooltip(tooltip, event, html, rect) {
  tooltip.style("opacity", 1).html(html)
    .style("left", event.clientX - rect.left + 12 + "px")
    .style("top", event.clientY - rect.top - 12 + "px");
}

function hideTooltip(tooltip) {
  tooltip.style("opacity", 0);
}

/* -- Split-bar signature element ---------------------------------------- */

function renderSplitBar(container, technical, practical, opts) {
  opts = opts || {};
  const maxScale = opts.maxScale || 100;
  const total = technical + practical;
  const wrap = d3.select(container).append("div").attr("class", "split-bar");
  const track = wrap.append("div").attr("class", "split-bar__track");
  track.append("div").attr("class", "split-bar__technical")
    .style("width", (technical / maxScale * 100) + "%");
  track.append("div").attr("class", "split-bar__practical")
    .style("width", (practical / maxScale * 100) + "%");
  wrap.append("span").attr("class", "split-bar__total mono").text(total.toFixed(1));
  return wrap.node();
}

/* -- Score distribution: histogram + median/p90 lines + complexity bands - */

function renderHistogram(container, bins, opts) {
  opts = opts || {};
  const width = container.clientWidth;
  const height = opts.height || 320;
  const margin = { top: 20, right: 20, bottom: 32, left: 36 };
  const svg = d3.select(container).append("svg").attr("width", width).attr("height", height);

  const x = d3.scaleLinear()
    .domain([bins[0].start, bins[bins.length - 1].end])
    .range([margin.left, width - margin.right]);
  const y = d3.scaleLinear()
    .domain([0, d3.max(bins, d => d.count)]).nice()
    .range([height - margin.bottom, margin.top]);

  const tooltip = makeTooltip(container);
  const rect = container.getBoundingClientRect();

  svg.selectAll(".bar").data(bins).join("rect")
    .attr("x", d => x(d.start) + 1)
    .attr("width", d => Math.max(0, x(d.end) - x(d.start) - 2))
    .attr("y", d => y(d.count))
    .attr("height", d => y(0) - y(d.count))
    .attr("rx", 2)
    .attr("fill", CHART_COLORS.technical)
    .on("mousemove", (event, d) => showTooltip(tooltip, event,
      `${d.start}&ndash;${d.end}: <strong>${d.count}</strong> companies`, rect))
    .on("mouseleave", () => hideTooltip(tooltip));

  [{ value: opts.median, label: "median", dash: null },
   { value: opts.p90, label: "p90", dash: "4,3" }].forEach((ref, i) => {
    if (ref.value == null) return;
    svg.append("line")
      .attr("x1", x(ref.value)).attr("x2", x(ref.value))
      .attr("y1", margin.top).attr("y2", height - margin.bottom)
      .attr("stroke", i === 0 ? CHART_COLORS.ink : CHART_COLORS.inkMuted)
      .attr("stroke-width", i === 0 ? 2 : 1.5)
      .attr("stroke-dasharray", ref.dash);
    svg.append("text")
      .attr("x", x(ref.value) + 6).attr("y", margin.top + 12 + i * 16)
      .attr("class", "mono").attr("font-size", "11px")
      .text(`${ref.label} ${ref.value}`);
  });

  svg.append("g").attr("transform", `translate(0,${height - margin.bottom})`)
    .call(d3.axisBottom(x).ticks(6))
    .call(g => g.selectAll("text").attr("class", "mono").attr("font-size", "11px"));
  svg.append("g").attr("transform", `translate(${margin.left},0)`)
    .call(d3.axisLeft(y).ticks(4))
    .call(g => g.select(".domain").remove())
    .call(g => g.selectAll("text").attr("class", "mono").attr("font-size", "11px"));
}

/* -- Technical vs Practical scatter -------------------------------------- */

function renderScatter(container, points, opts) {
  opts = opts || {};
  const width = container.clientWidth;
  const height = opts.height || 360;
  const margin = { top: 20, right: 20, bottom: 36, left: 36 };
  const svg = d3.select(container).append("svg").attr("width", width).attr("height", height);

  const x = d3.scaleLinear().domain([0, d3.max(points, d => d.x) || 1]).nice()
    .range([margin.left, width - margin.right]);
  const y = d3.scaleLinear().domain([0, d3.max(points, d => d.y) || 1]).nice()
    .range([height - margin.bottom, margin.top]);

  const tooltip = makeTooltip(container);
  const rect = container.getBoundingClientRect();

  svg.selectAll(".dot").data(points).join("circle")
    .attr("cx", d => x(d.x)).attr("cy", d => y(d.y))
    .attr("r", 4)
    .attr("fill", CHART_COLORS.technical)
    .attr("fill-opacity", 0.45)
    .on("mousemove", (event, d) => showTooltip(tooltip, event,
      `<strong>${d.name}</strong><br>Technical: ${d.x}<br>Practical: ${d.y}`, rect))
    .on("mouseleave", () => hideTooltip(tooltip));

  svg.append("g").attr("transform", `translate(0,${height - margin.bottom})`)
    .call(d3.axisBottom(x).ticks(5))
    .call(g => g.selectAll("text").attr("class", "mono").attr("font-size", "11px"));
  svg.append("g").attr("transform", `translate(${margin.left},0)`)
    .call(d3.axisLeft(y).ticks(5))
    .call(g => g.select(".domain").remove())
    .call(g => g.selectAll("text").attr("class", "mono").attr("font-size", "11px"));

  svg.append("text").attr("x", width - margin.right).attr("y", margin.top)
    .attr("text-anchor", "end").attr("class", "mono").attr("font-size", "11px")
    .attr("fill", CHART_COLORS.inkMuted).text("technical →");
  svg.append("text").attr("x", margin.left).attr("y", margin.top - 4)
    .attr("class", "mono").attr("font-size", "11px")
    .attr("fill", CHART_COLORS.inkMuted).text("↑ practical");

  if (opts.medianX != null && opts.medianY != null) {
    svg.append("line")
      .attr("x1", x(opts.medianX)).attr("x2", x(opts.medianX))
      .attr("y1", margin.top).attr("y2", height - margin.bottom)
      .attr("stroke", CHART_COLORS.inkMuted).attr("stroke-width", 1)
      .attr("stroke-dasharray", "3,3").attr("opacity", 0.5);
    svg.append("line")
      .attr("y1", y(opts.medianY)).attr("y2", y(opts.medianY))
      .attr("x1", margin.left).attr("x2", width - margin.right)
      .attr("stroke", CHART_COLORS.inkMuted).attr("stroke-width", 1)
      .attr("stroke-dasharray", "3,3").attr("opacity", 0.5);
    svg.append("text")
      .attr("x", width - margin.right - 4).attr("y", margin.top + 14)
      .attr("text-anchor", "end").attr("class", "mono").attr("font-size", "10px")
      .attr("fill", CHART_COLORS.inkMuted).text("high on both");
    svg.append("text")
      .attr("x", margin.left + 4).attr("y", height - margin.bottom - 6)
      .attr("class", "mono").attr("font-size", "10px")
      .attr("fill", CHART_COLORS.inkMuted).text("low on both");
  }

  if (opts.annotation) {
    svg.append("text")
      .attr("x", margin.left).attr("y", 14)
      .attr("class", "mono").attr("font-size", "11px")
      .attr("fill", CHART_COLORS.inkMuted).text(opts.annotation);
  }
}

/* -- Ranked bars (industry top/bottom) ------------------------------------ */

function renderRankedBars(container, records, opts) {
  opts = opts || {};
  const width = container.clientWidth;
  const barHeight = 28;
  const height = records.length * barHeight + 20;
  const margin = { top: 10, right: 60, bottom: 10, left: 180 };
  const svg = d3.select(container).append("svg").attr("width", width).attr("height", height);

  const x = d3.scaleLinear().domain([0, d3.max(records, d => d.mean_complexity)]).nice()
    .range([margin.left, width - margin.right]);
  const y = d3.scaleBand().domain(records.map(d => d.industry))
    .range([margin.top, height - margin.bottom]).padding(0.3);

  const tooltip = makeTooltip(container);
  const rect = container.getBoundingClientRect();

  svg.selectAll(".bar").data(records).join("rect")
    .attr("x", x(0)).attr("y", d => y(d.industry))
    .attr("width", d => x(d.mean_complexity) - x(0))
    .attr("height", y.bandwidth())
    .attr("rx", 3)
    .attr("fill", CHART_COLORS.ink)
    .attr("fill-opacity", (d, i) => 0.9 - i * 0.08)
    .on("mousemove", (event, d) => showTooltip(tooltip, event,
      `<strong>${d.industry}</strong><br>${d.mean_complexity} avg, ${d.count} companies`, rect))
    .on("mouseleave", () => hideTooltip(tooltip));

  svg.selectAll(".label").data(records).join("text")
    .attr("x", margin.left - 8).attr("y", d => y(d.industry) + y.bandwidth() / 2 + 4)
    .attr("text-anchor", "end").attr("font-size", "12px").text(d => d.industry);

  svg.selectAll(".value").data(records).join("text")
    .attr("x", d => x(d.mean_complexity) + 6).attr("y", d => y(d.industry) + y.bandwidth() / 2 + 4)
    .attr("class", "mono").attr("font-size", "12px").attr("fill", CHART_COLORS.inkMuted)
    .text(d => d.mean_complexity);
}

/* -- Complexity by batch (line, with an annotation callout) --------------- */

function renderLineChart(container, series, opts) {
  opts = opts || {};
  const width = container.clientWidth;
  const height = opts.height || 300;
  const margin = { top: 30, right: 20, bottom: 32, left: 36 };
  const svg = d3.select(container).append("svg").attr("width", width).attr("height", height);

  const x = d3.scalePoint().domain(series.map(d => d.batch))
    .range([margin.left, width - margin.right]);
  const y = d3.scaleLinear().domain([0, d3.max(series, d => d.mean_complexity)]).nice()
    .range([height - margin.bottom, margin.top]);

  const line = d3.line().x(d => x(d.batch)).y(d => y(d.mean_complexity));
  svg.append("path").datum(series).attr("d", line)
    .attr("fill", "none").attr("stroke", CHART_COLORS.technical).attr("stroke-width", 2);

  const tooltip = makeTooltip(container);
  const rect = container.getBoundingClientRect();

  svg.selectAll(".dot").data(series).join("circle")
    .attr("cx", d => x(d.batch)).attr("cy", d => y(d.mean_complexity)).attr("r", 4)
    .attr("fill", CHART_COLORS.technical)
    .on("mousemove", (event, d) => showTooltip(tooltip, event,
      `<strong>${d.batch}</strong><br>${d.mean_complexity} avg complexity`, rect))
    .on("mouseleave", () => hideTooltip(tooltip));

  const tickEvery = Math.ceil(series.length / 12);
  svg.append("g").attr("transform", `translate(0,${height - margin.bottom})`)
    .call(d3.axisBottom(x).tickValues(series.map(d => d.batch).filter((_, i) => i % tickEvery === 0)))
    .call(g => g.selectAll("text").attr("class", "mono").attr("font-size", "10px"));
  svg.append("g").attr("transform", `translate(${margin.left},0)`)
    .call(d3.axisLeft(y).ticks(4))
    .call(g => g.select(".domain").remove())
    .call(g => g.selectAll("text").attr("class", "mono").attr("font-size", "11px"));

  if (opts.annotation) {
    svg.append("text").attr("x", margin.left).attr("y", 14)
      .attr("class", "mono").attr("font-size", "11px").attr("fill", CHART_COLORS.inkMuted)
      .text(opts.annotation);
  }
}

/* -- Complexity by status (compact bar comparison) ------------------------- */

function renderBarCompare(container, records, opts) {
  opts = opts || {};
  const width = container.clientWidth;
  const height = opts.height || 220;
  const margin = { top: 20, right: 20, bottom: 32, left: 36 };
  const svg = d3.select(container).append("svg").attr("width", width).attr("height", height);

  const x = d3.scaleBand().domain(records.map(d => d.status))
    .range([margin.left, width - margin.right]).padding(0.35);
  const y = d3.scaleLinear().domain([0, d3.max(records, d => d.mean_complexity)]).nice()
    .range([height - margin.bottom, margin.top]);

  svg.selectAll(".bar").data(records).join("rect")
    .attr("x", d => x(d.status)).attr("width", x.bandwidth())
    .attr("y", d => y(d.mean_complexity)).attr("height", d => y(0) - y(d.mean_complexity))
    .attr("rx", 3).attr("fill", CHART_COLORS.ink).attr("fill-opacity", 0.85);

  svg.selectAll(".value").data(records).join("text")
    .attr("x", d => x(d.status) + x.bandwidth() / 2).attr("y", d => y(d.mean_complexity) - 6)
    .attr("text-anchor", "middle").attr("class", "mono").attr("font-size", "12px")
    .text(d => d.mean_complexity);

  svg.append("g").attr("transform", `translate(0,${height - margin.bottom})`)
    .call(d3.axisBottom(x))
    .call(g => g.selectAll("text").attr("font-size", "12px"));
}

/* -- Correlation heatmap: diverging technical<->practical, + table view --- */

function renderHeatmap(container, columns, values, opts) {
  opts = opts || {};
  const width = container.clientWidth;
  const cell = Math.min(48, (width - 160) / columns.length);
  const margin = { top: 120, right: 20, bottom: 20, left: 140 };
  const height = margin.top + cell * columns.length + margin.bottom;
  const svg = d3.select(container).append("svg").attr("width", width).attr("height", height);

  const color = d3.scaleLinear()
    .domain([-1, 0, 1])
    .range([CHART_COLORS.practical, CHART_COLORS.surface, CHART_COLORS.technical]);

  const tooltip = makeTooltip(container);
  const rect = container.getBoundingClientRect();

  columns.forEach((rowLabel, i) => {
    columns.forEach((colLabel, j) => {
      const v = values[i][j];
      svg.append("rect")
        .attr("x", margin.left + j * cell).attr("y", margin.top + i * cell)
        .attr("width", cell - 2).attr("height", cell - 2)
        .attr("fill", color(v))
        .on("mousemove", (event) => showTooltip(tooltip, event,
          `<strong>${rowLabel} × ${colLabel}</strong><br>r = ${v}`, rect))
        .on("mouseleave", () => hideTooltip(tooltip));
      if (Math.abs(v) >= 0.4 && rowLabel !== colLabel) {
        svg.append("text")
          .attr("x", margin.left + j * cell + cell / 2).attr("y", margin.top + i * cell + cell / 2 + 4)
          .attr("text-anchor", "middle").attr("class", "mono").attr("font-size", "10px")
          .text(v.toFixed(2));
      }
    });
  });

  columns.forEach((label, i) => {
    svg.append("text")
      .attr("x", margin.left - 6).attr("y", margin.top + i * cell + cell / 2 + 4)
      .attr("text-anchor", "end").attr("font-size", "10px").text(label.replace("_score", ""));
    svg.append("text")
      .attr("transform", `translate(${margin.left + i * cell + cell / 2},${margin.top - 6}) rotate(-45)`)
      .attr("text-anchor", "start").attr("font-size", "10px").text(label.replace("_score", ""));
  });

  if (opts.tableToggleContainer) {
    const btn = d3.select(opts.tableToggleContainer).append("button").text("Show as table");
    let showingTable = false;
    btn.on("click", () => {
      showingTable = !showingTable;
      svg.style("display", showingTable ? "none" : "block");
      d3.select(container).select("table").remove();
      if (showingTable) {
        const table = d3.select(container).append("table").attr("class", "explorer-table");
        const thead = table.append("thead").append("tr");
        thead.append("th").text("");
        columns.forEach(c => thead.append("th").text(c.replace("_score", "")));
        const tbody = table.append("tbody");
        columns.forEach((rowLabel, i) => {
          const tr = tbody.append("tr");
          tr.append("td").text(rowLabel.replace("_score", ""));
          values[i].forEach(v => tr.append("td").attr("class", "mono").text(v.toFixed(2)));
        });
      }
      btn.text(showingTable ? "Show as chart" : "Show as table");
    });
  }
}
