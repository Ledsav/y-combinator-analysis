async function loadLanding() {
  const [summary, companies] = await Promise.all([
    fetch("data/summary.json").then((r) => r.json()),
    fetch("data/companies.json").then((r) => r.json()),
  ]);

  document.getElementById("stat-count").textContent = summary.company_count.toLocaleString();
  renderSplitBar(
    document.getElementById("stat-median"),
    summary.median_technical_score,
    summary.median_practical_score,
    { maxScale: 100 }
  );
  document.getElementById("stat-correlation").textContent =
    "r = " + summary.technical_practical_correlation;
  document.getElementById("stat-top-industry-name").textContent = summary.top_industry.industry;
  document.getElementById("stat-top-industry-value").textContent =
    summary.top_industry.mean_complexity + " avg";
  document.getElementById("generated-at").textContent = summary.generated_at;

  const sample = companies
    .filter((_, i) => i % 16 === 0)
    .map((c) => ({ x: c.technical_score, y: c.practical_score, name: c.name }));
  renderScatter(document.getElementById("teaser-scatter"), sample, { height: 280 });
}

loadLanding();
