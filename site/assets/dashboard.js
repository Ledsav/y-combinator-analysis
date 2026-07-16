async function loadDashboard() {
  const [summary, companies] = await Promise.all([
    fetch("data/summary.json").then((r) => r.json()),
    fetch("data/companies.json").then((r) => r.json()),
  ]);

  document.getElementById("kpi-count").textContent = summary.company_count.toLocaleString();
  renderSplitBar(
    document.getElementById("kpi-median"),
    summary.median_technical_score,
    summary.median_practical_score,
    { maxScale: 100 }
  );
  document.getElementById("kpi-sigma").textContent = summary.sigma_complexity;
  document.getElementById("kpi-top-industry-name").textContent = summary.top_industry.industry;
  document.getElementById("kpi-top-industry-value").textContent =
    summary.top_industry.mean_complexity + " avg";

  const sorted = companies.map((c) => c.complexity_score).sort((a, b) => a - b);
  const p90 = sorted[Math.floor(sorted.length * 0.9)];
  renderHistogram(document.getElementById("chart-distribution"), summary.distribution_bins, {
    median: summary.median_complexity,
    p90: Math.round(p90 * 10) / 10,
  });

  const technicalValues = companies.map((c) => c.technical_score).sort((a, b) => a - b);
  const practicalValues = companies.map((c) => c.practical_score).sort((a, b) => a - b);
  renderScatter(
    document.getElementById("chart-scatter"),
    companies.map((c) => ({ x: c.technical_score, y: c.practical_score, name: c.name })),
    {
      medianX: technicalValues[Math.floor(technicalValues.length / 2)],
      medianY: practicalValues[Math.floor(practicalValues.length / 2)],
      annotation: "r = " + summary.technical_practical_correlation + " — nearly uncorrelated",
    }
  );

  renderRankedBars(
    document.getElementById("chart-industry"),
    summary.industry_ranking.top.concat(summary.industry_ranking.bottom)
  );

  renderLineChart(document.getElementById("chart-batch"), summary.mean_by_batch, {
    annotation: "Complexity has risen across batches, earliest to most recent.",
  });

  renderBarCompare(document.getElementById("chart-status"), summary.mean_by_status);

  const successStrict = summary.success_correlation.strict;
  renderBarCompare(document.getElementById("chart-success-strict"), successStrict.mean_by_group, {
    annotation: `r = ${successStrict.r_complexity} (n=${successStrict.count}, ${(successStrict.rate * 100).toFixed(1)}%)`,
  });
  const successBroad = summary.success_correlation.broad;
  renderBarCompare(document.getElementById("chart-success-broad"), successBroad.mean_by_group, {
    annotation: `r = ${successBroad.r_complexity} (n=${successBroad.count}, ${(successBroad.rate * 100).toFixed(1)}%)`,
  });

  renderHeatmap(
    document.getElementById("chart-heatmap"),
    summary.correlation_matrix.columns,
    summary.correlation_matrix.values,
    { tableToggleContainer: document.getElementById("chart-heatmap-toggle") }
  );

  initExplorer(companies);
}

function initExplorer(records) {
  let sortKey = "complexity_score";
  let sortAsc = false;
  const PAGE_SIZE = 50;
  let visibleCount = PAGE_SIZE;
  const tbody = document.getElementById("explorer-body");
  const searchBox = document.getElementById("explorer-search");
  const batchFilter = document.getElementById("explorer-batch");
  const statusFilter = document.getElementById("explorer-status");
  const countLabel = document.getElementById("explorer-count");
  const loadMoreBtn = document.getElementById("explorer-load-more");

  function unique(values) {
    return Array.from(new Set(values)).sort();
  }
  function addOptions(select, values) {
    values.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      select.appendChild(opt);
    });
  }
  addOptions(batchFilter, unique(records.map((r) => r.batch)));
  addOptions(statusFilter, unique(records.map((r) => r.status)));

  function currentFilters() {
    return {
      search: searchBox.value.trim().toLowerCase(),
      batch: batchFilter.value,
      status: statusFilter.value,
    };
  }
  function matches(r, f) {
    if (f.search && !r.name.toLowerCase().includes(f.search)) return false;
    if (f.batch && r.batch !== f.batch) return false;
    if (f.status && r.status !== f.status) return false;
    return true;
  }

  function render() {
    const f = currentFilters();
    const filtered = records.filter((r) => matches(r, f));
    filtered.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null) return 1;
      if (bv == null) return -1;
      if (av < bv) return sortAsc ? -1 : 1;
      if (av > bv) return sortAsc ? 1 : -1;
      return 0;
    });

    const visible = filtered.slice(0, visibleCount);
    const fragment = document.createDocumentFragment();
    visible.forEach((r) => {
      const tr = document.createElement("tr");
      const nameCell = document.createElement("td");
      nameCell.textContent = r.name;
      const batchCell = document.createElement("td");
      batchCell.textContent = r.batch;
      const statusCell = document.createElement("td");
      statusCell.textContent = r.status;
      const industriesCell = document.createElement("td");
      industriesCell.textContent = (r.industries_list || []).join(", ");
      const scoreCell = document.createElement("td");
      renderSplitBar(scoreCell, r.technical_score, r.practical_score);
      tr.append(nameCell, batchCell, statusCell, industriesCell, scoreCell);
      fragment.appendChild(tr);
    });
    tbody.innerHTML = "";
    tbody.appendChild(fragment);
    countLabel.textContent = visible.length + " of " + filtered.length + " companies";

    const remaining = filtered.length - visible.length;
    loadMoreBtn.hidden = remaining <= 0;
    if (remaining > 0) {
      loadMoreBtn.textContent = `Load more (${Math.min(PAGE_SIZE, remaining)} of ${remaining} remaining)`;
    }
  }

  document.querySelectorAll("#explorer-table thead th[data-key]").forEach((th) => {
    th.setAttribute("tabindex", "0");
    th.setAttribute("role", "button");
    const toggleSort = () => {
      const key = th.getAttribute("data-key");
      if (sortKey === key) {
        sortAsc = !sortAsc;
      } else {
        sortKey = key;
        sortAsc = true;
      }
      render();
    };
    th.addEventListener("click", toggleSort);
    th.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleSort();
      }
    });
  });
  loadMoreBtn.addEventListener("click", () => {
    visibleCount += PAGE_SIZE;
    render();
  });
  [searchBox, batchFilter, statusFilter].forEach((el) => el.addEventListener("input", () => {
    visibleCount = PAGE_SIZE;
    render();
  }));
  render();
}

loadDashboard();
