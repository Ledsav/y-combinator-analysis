function renderEtlFlow(container, steps) {
  const wrap = d3.select(container).append("div").attr("class", "pipeline-flow");
  steps.forEach((step, i) => {
    const card = wrap
      .append("div")
      .attr("class", "pipeline-stage-card" + (step.optional ? " pipeline-stage-card--optional" : ""));
    card.append("div").attr("class", "pipeline-stage-card__name").text(step.name);
    card.append("div").attr("class", "mono").style("font-size", "0.7rem").text(step.module);
    card
      .append("div")
      .attr("class", "mono")
      .style("font-size", "0.7rem")
      .style("color", "var(--color-ink-muted)")
      .text("→ " + step.output_dir);
    if (step.optional) {
      card.append("span").attr("class", "pipeline-stage-card__tag").text("off by default");
    }
    if (i < steps.length - 1) {
      wrap.append("div").attr("class", "pipeline-arrow").text("→");
    }
  });
}

function renderScoringEngine(container, buckets) {
  const dimensions = {};
  buckets.forEach((b) => {
    dimensions[b.dimension] = (dimensions[b.dimension] || 0) + b.params.points;
  });

  const wrap = d3.select(container).append("div").attr("class", "scoring-engine");
  const bucketsCol = wrap.append("div").attr("class", "scoring-engine__buckets");
  buckets.forEach((b) => {
    const card = bucketsCol.append("div").attr("class", "bucket-card");
    card.append("div").attr("class", "bucket-card__name").text(b.name);
    const source = b.raw_feature ? b.raw_feature : "combine: " + b.combine;
    card.append("div").attr("class", "mono").style("font-size", "0.75rem").text(source);
    card
      .append("div")
      .attr("class", "mono")
      .style("font-size", "0.75rem")
      .style("color", "var(--color-ink-muted)")
      .text(b.method + " → " + b.params.points + " pts");
  });

  wrap.append("div").attr("class", "scoring-engine__arrow").text("→");

  const totalsCol = wrap.append("div").attr("class", "scoring-engine__totals");
  Object.entries(dimensions).forEach(([dim, points]) => {
    const card = totalsCol.append("div").attr("class", "bucket-card");
    card.append("div").attr("class", "bucket-card__name").text(dim + "_score");
    card
      .append("div")
      .attr("class", "mono")
      .style("font-size", "0.75rem")
      .text(points + " pt budget");
  });

  wrap.append("div").attr("class", "scoring-engine__arrow").text("→");

  const total = Object.values(dimensions).reduce((a, b) => a + b, 0);
  const complexityCol = wrap.append("div").attr("class", "scoring-engine__total");
  complexityCol.append("div").attr("class", "bucket-card__name").text("complexity_score");
  renderSplitBar(complexityCol.node(), dimensions.technical || 0, dimensions.practical || 0, {
    maxScale: total,
  });
}

async function loadPipeline() {
  const pipeline = await fetch("data/pipeline.json").then((r) => r.json());
  renderEtlFlow(document.getElementById("diagram-etl-flow"), pipeline.steps);
  renderScoringEngine(document.getElementById("diagram-scoring-engine"), pipeline.buckets);
}

loadPipeline();
