(function () {
  "use strict";

  const catalog = window.METRIC_CATALOG;
  if (!catalog) {
    document.body.innerHTML = "<p class=\"load-error\">카탈로그 데이터를 불러오지 못했습니다. scripts/build_web_catalog.py를 먼저 실행하세요.</p>";
    return;
  }

  const TIER_COLORS = {
    T1: "#d6533f",
    T2: "#df8b3b",
    T3: "#67a797",
    T4: "#547bb4",
  };
  const STATUS_COLORS = {
    active: "#29896f",
    exploratory: "#b97927",
    deferred: "#7c7784",
  };
  const STATUS_LABELS = {
    active: "Active",
    exploratory: "Exploratory",
    deferred: "Deferred",
  };
  const TIER_DESCRIPTIONS = {
    T1: "의료진 또는 검사실이 환자 데이터에 직접 기록하는 의료 기준 변수입니다.",
    T2: "T1 값이나 고정 annotation에서 명시적 산식으로 계산되는 임상 앵커 파생값입니다.",
    T3: "영상·공간·형태 분석으로 산출되는 연구용 계산 특징 또는 biomarker proxy입니다.",
    T4: "모델 score, rank, representation처럼 추론 과정에서 생성되는 모델 파생값입니다.",
  };
  const DOMAIN_LABELS = {
    candidate_generation: "후보 생성",
    clinician_review: "전문의 검토",
    data_integrity: "데이터 무결성",
    descriptive: "기술통계",
    embedding_geometry: "표현 공간",
    evaluation: "모델 평가",
    inference: "추론통계",
    model_evaluation: "모델 평가",
    model_output: "모델 출력",
    morphology: "형태 재검토",
    pathology: "병리",
    patient_level: "환자 수준",
    pni_audit: "PNI 감사",
    ranking: "순위 평가",
    reproducibility: "재현성",
    spatial_pilot: "공간 pilot",
    statistics: "통계·불확실성",
    survival: "생존분석",
  };

  const metricById = new Map(catalog.medical.map((metric) => [metric.metric_id, metric]));
  const childrenById = new Map(catalog.medical.map((metric) => [metric.metric_id, []]));
  catalog.medical.forEach((metric) => {
    metric.parent_metric_ids.forEach((parentId) => childrenById.get(parentId).push(metric));
  });

  const state = {
    tier: "ALL",
    status: "ALL",
    query: "",
    graphAnchor: "ALL",
    selectedId: metricById.has("pathology.cancer_extent_percent")
      ? "pathology.cancer_extent_percent"
      : catalog.medical[0].metric_id,
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function setText(id, value) {
    document.getElementById(id).textContent = value;
  }

  const SVG_NS = "http://www.w3.org/2000/svg";

  function svgElement(tag, attributes = {}, textContent = "") {
    const element = document.createElementNS(SVG_NS, tag);
    Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, String(value)));
    if (textContent) element.textContent = textContent;
    return element;
  }

  function truncated(value, maximum) {
    return value.length > maximum ? `${value.slice(0, maximum - 1)}…` : value;
  }

  function metricNode(metric, selected) {
    if (!metric) {
      return '<p class="lineage-empty">연결된 지표가 없습니다.</p>';
    }
    return `
      <button class="lineage-node${selected ? " selected" : ""}" type="button"
        data-metric-id="${escapeHtml(metric.metric_id)}" style="--node-color:${TIER_COLORS[metric.tier]}">
        <b>${escapeHtml(metric.name_ko)}</b>
        <small>${escapeHtml(metric.metric_id)}</small>
      </button>`;
  }

  function renderSummary() {
    const summary = catalog.summary;
    setText("medical-total", summary.medical_total);
    setText("tier1-total", summary.tier_counts.T1 || 0);
    setText("analysis-total", summary.analysis_total);
    setText("legacy-total", summary.legacy_total);
    setText("analysis-big-total", summary.analysis_total);
  }

  function renderTierMap() {
    const container = document.getElementById("tier-map");
    container.innerHTML = catalog.tier_meta.map((meta) => `
      <button class="tier-card" type="button" data-tier="${meta.tier}"
        style="--tier:${TIER_COLORS[meta.tier]}">
        <span class="tier-index">${meta.tier}</span>
        <h3>${escapeHtml(meta.name_ko)}</h3>
        <span class="tier-en">${escapeHtml(meta.name)}</span>
        <p class="tier-desc">${escapeHtml(TIER_DESCRIPTIONS[meta.tier])}</p>
        <div class="tier-footer"><span>${escapeHtml(meta.short)}</span><strong>${catalog.summary.tier_counts[meta.tier] || 0}</strong></div>
      </button>`).join("");

    container.addEventListener("click", (event) => {
      const card = event.target.closest("[data-tier]");
      if (!card) return;
      state.tier = card.dataset.tier;
      renderFilters();
      renderMetricGrid();
      document.getElementById("explorer").scrollIntoView({ behavior: "smooth" });
    });
  }

  function graphMetricSet() {
    if (state.graphAnchor === "ALL") return new Set(catalog.medical.map((metric) => metric.metric_id));
    const visible = new Set([state.graphAnchor]);
    const queue = [state.graphAnchor];
    while (queue.length) {
      const current = queue.shift();
      (childrenById.get(current) || []).forEach((child) => {
        if (!visible.has(child.metric_id)) {
          visible.add(child.metric_id);
          queue.push(child.metric_id);
        }
      });
    }
    return visible;
  }

  function renderNetworkControls() {
    const anchors = catalog.medical
      .filter((metric) => metric.tier === "T1" && childrenById.get(metric.metric_id).length)
      .sort((left, right) => (
        childrenById.get(right.metric_id).length - childrenById.get(left.metric_id).length
        || left.name_ko.localeCompare(right.name_ko, "ko")
      ));
    const select = document.getElementById("network-anchor-filter");
    select.innerHTML = [
      `<option value="ALL">전체 의료 지표 (${catalog.medical.length})</option>`,
      ...anchors.map((metric) => (
        `<option value="${escapeHtml(metric.metric_id)}">${escapeHtml(metric.name_ko)} · ${childrenById.get(metric.metric_id).length}개 파생</option>`
      )),
    ].join("");
    select.value = state.graphAnchor;
    document.getElementById("network-legend").innerHTML = catalog.tier_meta.map((meta) => `
      <span><i style="--legend-color:${TIER_COLORS[meta.tier]}"></i>${meta.tier}</span>`).join("");
  }

  function networkOrder(metrics, tier, catalogIndex) {
    const tierMetrics = metrics.filter((metric) => metric.tier === tier);
    if (tier === "T1") return tierMetrics;
    return tierMetrics.sort((left, right) => {
      const parentScore = (metric) => {
        const indexes = metric.parent_metric_ids.map((id) => catalogIndex.get(id) ?? catalog.medical.length);
        return indexes.reduce((total, value) => total + value, 0) / indexes.length;
      };
      return parentScore(left) - parentScore(right)
        || left.domain.localeCompare(right.domain)
        || left.metric_id.localeCompare(right.metric_id);
    });
  }

  function setNetworkHighlight(metricId) {
    const connected = new Set([
      metricId,
      ...metricById.get(metricId).parent_metric_ids,
      ...(childrenById.get(metricId) || []).map((metric) => metric.metric_id),
    ]);
    document.querySelectorAll("#metric-network .network-node").forEach((node) => {
      node.classList.toggle("related", connected.has(node.dataset.metricId));
      node.classList.toggle("dimmed", !connected.has(node.dataset.metricId));
    });
    document.querySelectorAll("#metric-network .network-edge").forEach((edge) => {
      const related = edge.dataset.source === metricId || edge.dataset.target === metricId;
      edge.classList.toggle("related", related);
      edge.classList.toggle("dimmed", !related);
    });
  }

  function clearNetworkHighlight() {
    document.querySelectorAll("#metric-network .related, #metric-network .dimmed").forEach((element) => {
      element.classList.remove("related", "dimmed");
    });
  }

  function updateNetworkSelection() {
    document.querySelectorAll("#metric-network .network-node").forEach((node) => {
      node.classList.toggle("selected", node.dataset.metricId === state.selectedId);
    });
  }

  function renderMetricNetwork() {
    const visibleIds = graphMetricSet();
    const metrics = catalog.medical.filter((metric) => visibleIds.has(metric.metric_id));
    const tiers = ["T1", "T2", "T3", "T4"];
    const catalogIndex = new Map(catalog.medical.map((metric, index) => [metric.metric_id, index]));
    const ordered = Object.fromEntries(tiers.map((tier) => [tier, networkOrder(metrics, tier, catalogIndex)]));
    const edges = metrics.flatMap((metric) => metric.parent_metric_ids
      .filter((parentId) => visibleIds.has(parentId))
      .map((parentId) => ({ source: parentId, target: metric.metric_id })));
    const maximumRows = Math.max(1, ...tiers.map((tier) => ordered[tier].length));
    const width = 1160;
    const top = 82;
    const rowStep = 43;
    const nodeWidth = 235;
    const nodeHeight = 35;
    const availableHeight = Math.max(300, (maximumRows - 1) * rowStep);
    const height = top + availableHeight + 55;
    const xByTier = { T1: 16, T2: 313, T3: 610, T4: 907 };
    const positions = new Map();
    tiers.forEach((tier) => {
      const rows = ordered[tier];
      const usedHeight = Math.max(0, (rows.length - 1) * rowStep);
      const start = top + (availableHeight - usedHeight) / 2;
      rows.forEach((metric, index) => positions.set(metric.metric_id, {
        x: xByTier[tier],
        y: start + index * rowStep,
      }));
    });

    const svg = document.getElementById("metric-network");
    svg.replaceChildren();
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("height", height);
    svg.append(
      svgElement("title", { id: "network-svg-title" }, "의료 정량지표 T1에서 T4까지의 계보 그래프"),
      svgElement("desc", { id: "network-svg-description" }, `${metrics.length}개 지표와 ${edges.length}개 parent 연결을 Tier별 열로 표시합니다.`),
    );

    tiers.forEach((tier) => {
      const meta = catalog.tier_meta.find((item) => item.tier === tier);
      const x = xByTier[tier];
      svg.append(
        svgElement("line", { class: "network-column-guide", x1: x, y1: 67, x2: x, y2: height - 22 }),
        svgElement("text", {
          class: "network-column-tier", x, y: 31, style: `--column-color:${TIER_COLORS[tier]}`,
        }, `${tier} · ${ordered[tier].length}`),
        svgElement("text", { class: "network-column-name", x, y: 50 }, meta.name),
      );
    });

    const edgeLayer = svgElement("g", { class: "network-edge-layer", "aria-hidden": "true" });
    edges.forEach((edge) => {
      const source = positions.get(edge.source);
      const target = positions.get(edge.target);
      const sourceMetric = metricById.get(edge.source);
      const targetMetric = metricById.get(edge.target);
      const startX = source.x + nodeWidth;
      const startY = source.y + nodeHeight / 2;
      const endX = target.x;
      const endY = target.y + nodeHeight / 2;
      const bend = Math.max(35, (endX - startX) * .48);
      edgeLayer.append(svgElement("path", {
        class: "network-edge",
        d: `M ${startX} ${startY} C ${startX + bend} ${startY}, ${endX - bend} ${endY}, ${endX} ${endY}`,
        "data-source": edge.source,
        "data-target": edge.target,
        style: `--edge-color:${TIER_COLORS[targetMetric.tier] || TIER_COLORS[sourceMetric.tier]}`,
      }));
    });
    svg.append(edgeLayer);

    tiers.forEach((tier) => ordered[tier].forEach((metric) => {
      const position = positions.get(metric.metric_id);
      const group = svgElement("g", {
        class: "network-node",
        transform: `translate(${position.x} ${position.y})`,
        tabindex: "0",
        role: "button",
        "aria-label": `${metric.tier} ${metric.name_ko}, ${metric.metric_id}`,
        "data-metric-id": metric.metric_id,
        style: `--node-color:${TIER_COLORS[metric.tier]}`,
      });
      group.append(
        svgElement("title", {}, `${metric.name_ko} (${metric.name_en})\n${metric.metric_id}`),
        svgElement("rect", { class: "node-body", width: nodeWidth, height: nodeHeight, rx: 8 }),
        svgElement("rect", { class: "node-accent", width: 4, height: nodeHeight, rx: 2 }),
        svgElement("text", { class: "network-node-name", x: 13, y: 14 }, truncated(metric.name_ko, 22)),
        svgElement("text", { class: "network-node-id", x: 13, y: 27 }, truncated(metric.metric_id, 36)),
        svgElement("circle", {
          class: "network-node-status", cx: nodeWidth - 12, cy: 11, r: 3,
          fill: STATUS_COLORS[metric.status] || STATUS_COLORS.deferred,
        }),
      );
      group.addEventListener("mouseenter", () => setNetworkHighlight(metric.metric_id));
      group.addEventListener("mouseleave", clearNetworkHighlight);
      group.addEventListener("focus", () => setNetworkHighlight(metric.metric_id));
      group.addEventListener("blur", clearNetworkHighlight);
      group.addEventListener("click", () => selectMetric(metric.metric_id, true));
      group.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectMetric(metric.metric_id, true);
        }
      });
      svg.append(group);
    }));
    setText("network-node-count", metrics.length);
    setText("network-edge-count", edges.length);
    updateNetworkSelection();
  }

  function renderFilters() {
    const filters = document.getElementById("tier-filters");
    filters.innerHTML = ["ALL", "T1", "T2", "T3", "T4"].map((tier) => `
      <button type="button" data-filter-tier="${tier}" class="${state.tier === tier ? "active" : ""}"
        aria-pressed="${state.tier === tier}">${tier}</button>`).join("");
  }

  function filteredMetrics() {
    const query = state.query.trim().toLocaleLowerCase("ko");
    return catalog.medical.filter((metric) => {
      if (state.tier !== "ALL" && metric.tier !== state.tier) return false;
      if (state.status !== "ALL" && metric.status !== state.status) return false;
      if (!query) return true;
      const haystack = [
        metric.metric_id,
        metric.name_ko,
        metric.name_en,
        metric.domain,
        metric.source_type,
        metric.clinical_use,
      ].join(" ").toLocaleLowerCase("ko");
      return haystack.includes(query);
    });
  }

  function renderMetricGrid() {
    const metrics = filteredMetrics();
    const grid = document.getElementById("metric-grid");
    const empty = document.getElementById("empty-state");
    setText("result-count", metrics.length);
    empty.hidden = metrics.length !== 0;
    grid.innerHTML = metrics.map((metric) => `
      <button class="metric-card" type="button" data-metric-id="${escapeHtml(metric.metric_id)}"
        style="--card-tier:${TIER_COLORS[metric.tier]};--status-color:${STATUS_COLORS[metric.status] || STATUS_COLORS.deferred}">
        <span class="metric-meta">
          <span class="metric-tier">${metric.tier}</span>
          <span class="status-pill">${STATUS_LABELS[metric.status] || escapeHtml(metric.status)}</span>
        </span>
        <h3>${escapeHtml(metric.name_ko)}</h3>
        <p class="metric-en">${escapeHtml(metric.name_en)}</p>
        <code class="metric-id">${escapeHtml(metric.metric_id)}</code>
      </button>`).join("");
  }

  function renderLineage() {
    const metric = metricById.get(state.selectedId);
    const parents = metric.parent_metric_ids.map((id) => metricById.get(id)).filter(Boolean);
    const children = childrenById.get(metric.metric_id) || [];
    document.getElementById("lineage-graph").innerHTML = `
      <div class="lineage-stage">
        <span>${parents.length ? "Upstream parent" : "Clinical anchor"}</span>
        ${parents.length ? parents.map((parent) => metricNode(parent, false)).join("") : '<p class="lineage-empty">최상위 의료 기준축입니다.<br>상위 parent가 없습니다.</p>'}
      </div>
      <div class="lineage-arrow" aria-hidden="true">→</div>
      <div class="lineage-stage">
        <span>Selected metric</span>
        ${metricNode(metric, true)}
      </div>
      <div class="lineage-arrow" aria-hidden="true">→</div>
      <div class="lineage-stage">
        <span>Direct children · ${children.length}</span>
        ${children.length ? children.map((child) => metricNode(child, false)).join("") : '<p class="lineage-empty">직접 파생된 하위 지표가 없습니다.</p>'}
      </div>`;

    document.getElementById("metric-detail").style.setProperty("--tier-color", TIER_COLORS[metric.tier]);
    document.getElementById("metric-detail").innerHTML = `
      <span class="detail-tier">${metric.tier} · ${escapeHtml(metric.tier_name)}</span>
      <h3>${escapeHtml(metric.name_ko)}</h3>
      <p class="detail-en">${escapeHtml(metric.name_en)}</p>
      <p class="detail-text">${escapeHtml(metric.interpretation)}</p>
      <dl class="detail-list">
        <div><dt>Metric ID</dt><dd>${escapeHtml(metric.metric_id)}</dd></div>
        <div><dt>Domain</dt><dd>${escapeHtml(metric.domain)}</dd></div>
        <div><dt>Unit</dt><dd>${escapeHtml(metric.unit_or_scale)}</dd></div>
        <div><dt>Analysis unit</dt><dd>${escapeHtml(metric.analysis_unit)}</dd></div>
        <div><dt>Source</dt><dd>${escapeHtml(metric.source_type)}</dd></div>
        <div><dt>Use boundary</dt><dd>${escapeHtml(metric.clinical_use)}</dd></div>
      </dl>`;
  }

  function selectMetric(metricId, scroll) {
    if (!metricById.has(metricId)) return;
    state.selectedId = metricId;
    renderLineage();
    updateNetworkSelection();
    if (scroll) {
      document.querySelector(".lineage-section").scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function renderAnalysis() {
    const counts = Object.entries(catalog.summary.analysis_domain_counts)
      .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]));
    const maximum = Math.max(...counts.map(([, count]) => count));
    document.getElementById("analysis-bars").innerHTML = counts.map(([domain, count]) => `
      <div class="analysis-row">
        <label title="${escapeHtml(domain)}">${escapeHtml(DOMAIN_LABELS[domain] || domain.replaceAll("_", " "))}</label>
        <div class="bar-track"><div class="bar" style="width:${(count / maximum) * 100}%"></div></div>
        <strong>${count}</strong>
      </div>`).join("");
  }

  function renderSources() {
    const rows = [
      ...catalog.source.medical.map((path, index) => [`T${index + 1}`, path]),
      ["Analysis", catalog.source.analysis],
      ["Legacy", catalog.source.legacy],
    ];
    document.getElementById("source-paths").innerHTML = rows.map(([label, path]) => `
      <div class="source-path"><span>${escapeHtml(label)}</span><code>${escapeHtml(path)}</code></div>`).join("");
  }

  document.getElementById("tier-filters").addEventListener("click", (event) => {
    const button = event.target.closest("[data-filter-tier]");
    if (!button) return;
    state.tier = button.dataset.filterTier;
    renderFilters();
    renderMetricGrid();
  });
  document.getElementById("network-anchor-filter").addEventListener("change", (event) => {
    state.graphAnchor = event.target.value;
    renderMetricNetwork();
  });
  document.getElementById("metric-search").addEventListener("input", (event) => {
    state.query = event.target.value;
    renderMetricGrid();
  });
  document.getElementById("status-filter").addEventListener("change", (event) => {
    state.status = event.target.value;
    renderMetricGrid();
  });
  document.getElementById("metric-grid").addEventListener("click", (event) => {
    const card = event.target.closest("[data-metric-id]");
    if (card) selectMetric(card.dataset.metricId, true);
  });
  document.getElementById("lineage-graph").addEventListener("click", (event) => {
    const node = event.target.closest("[data-metric-id]");
    if (node) selectMetric(node.dataset.metricId, false);
  });

  renderSummary();
  renderTierMap();
  renderNetworkControls();
  renderMetricNetwork();
  renderFilters();
  renderMetricGrid();
  renderLineage();
  renderAnalysis();
  renderSources();
}());
