"use strict";

const state = { data: null, csrfToken: "" };

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

function showToast(message, isError = false) {
  const toast = document.querySelector("#toast");
  if (!toast) return;
  toast.textContent = message;
  toast.className = isError ? "show error" : "show";
  window.setTimeout(() => { toast.className = ""; }, 4200);
}

async function loadPortfolio() {
  const response = await fetch("/api/portfolio", { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok || payload.error) throw new Error(payload.error || "포트폴리오 정보를 읽지 못했습니다.");
  state.data = payload;
  state.csrfToken = payload.csrf_token;
  return payload;
}

function artifactVisual(artifact) {
  if (artifact.kind === "interactive") {
    return `<div class="artifact-visual" aria-hidden="true"><b>T1→T4</b></div>`;
  }
  return `<img src="${escapeHtml(artifact.route)}" alt="${escapeHtml(artifact.label)}" loading="lazy">`;
}

function artifactCard(artifact, preview = false) {
  const css = preview ? "artifact-preview-card" : "artifact-card";
  const owner = artifact.owner === "shared_infrastructure" ? "SHARED METRIC INFRASTRUCTURE" : "PROSTATE BIOMARKER VALIDATION";
  const target = artifact.kind === "interactive" ? ' target="_blank" rel="noopener"' : ' target="_blank" rel="noopener"';
  return `<a class="${css}" href="${escapeHtml(artifact.route)}"${target}>
    ${artifactVisual(artifact)}
    <div class="artifact-copy"><span>${escapeHtml(artifact.label)}</span><h3>${escapeHtml(artifact.title)}</h3><p>${escapeHtml(artifact.description)}</p>${preview ? "" : `<small class="owner">${owner}</small>`}</div>
  </a>`;
}

function renderHome(data) {
  document.querySelector("#portfolio-goal").textContent = data.portfolio.goal;
  document.querySelector("#portfolio-date").textContent = new Date(data.generated_at_utc).toLocaleDateString("ko-KR", { month: "short", day: "2-digit" });
  document.querySelector("#principle-strip").innerHTML = data.portfolio.principles.map((principle, index) => {
    const [lead, ...rest] = principle.split(" ");
    return `<article class="principle-item"><span>0${index + 1}</span><div><b>${escapeHtml(lead)}</b><p>${escapeHtml(rest.join(" "))}</p></div></article>`;
  }).join("");
  document.querySelector("#hero-project-signals").innerHTML = data.projects.map((project) => `<div class="signal-item"><header><b>${escapeHtml(project.slug.toUpperCase())}</b><span>${project.progress_percent}%</span></header><div class="signal-bar"><i style="width:${project.progress_percent}%"></i></div><small>${escapeHtml(project.current_gate.stage)} · ${escapeHtml(project.current_gate.status)}</small></div>`).join("");
  document.querySelector("#project-grid").innerHTML = data.projects.map((project, index) => `<article class="project-card" data-number="0${index + 1}"><span class="project-code">${escapeHtml(project.code)}</span><h3>${escapeHtml(project.korean_name)}</h3><p>${escapeHtml(project.goal)}</p><div class="card-gate"><span>CURRENT GATE</span><b>${escapeHtml(project.current_gate.stage)}</b><div class="progress-track"><i style="width:${project.progress_percent}%"></i></div><div class="card-foot"><span>${project.completed_stages} / ${project.total_stages} stages complete</span><span>${escapeHtml(project.current_gate.status)}</span></div></div><a class="card-link" href="${escapeHtml(project.href)}"><span>프로젝트 상세</span><span>→</span></a></article>`).join("");
  document.querySelector("#artifact-preview").innerHTML = data.artifacts.filter((artifact) => artifact.available).slice(0, 3).map((artifact) => artifactCard(artifact, true)).join("");
}

function renderProject(data, projectId) {
  const project = data.projects.find((item) => item.id === projectId);
  if (!project) throw new Error("등록된 프로젝트 페이지가 아닙니다.");
  const number = String(data.projects.findIndex((item) => item.id === projectId) + 1).padStart(2, "0");
  const reviewCounts = data.review_summary[projectId] || { admin: 0, clinician: 0 };
  document.title = `${project.name} · VLM Pathology`;
  document.querySelector("#project-page").innerHTML = `
    <section class="project-hero" data-number="${number}"><div class="shell"><div class="breadcrumb"><a href="/">PORTFOLIO</a> / ${escapeHtml(project.code)}</div><div class="project-hero-grid"><div><p class="kicker light">${escapeHtml(project.code)}</p><h1>${escapeHtml(project.korean_name)}</h1><p class="goal">${escapeHtml(project.goal)}</p></div><aside class="gate-panel"><span>CURRENT GATE · ${escapeHtml(project.current_gate.order)}</span><b>${escapeHtml(project.current_gate.stage)}</b><p>${escapeHtml(project.current_gate.status)} · ${escapeHtml(project.current_gate.entry_criterion)}</p></aside></div></div></section>
    <section class="section shell project-summary"><div><p class="kicker">MILESTONE PROGRESS</p><div class="progress-ring" style="--progress:${project.progress_percent}%"><div><strong>${project.progress_percent}%</strong><span>${project.completed_stages} / ${project.total_stages} COMPLETE</span></div></div></div><div><p class="kicker">RESEARCH PLAN</p><h2>현재 계획의 세 축</h2><div class="plan-list">${project.plan.map((item) => `<div class="plan-item"><p>${escapeHtml(item)}</p></div>`).join("")}</div></div></section>
    <section class="section shell"><div class="section-heading split-heading"><div><p class="kicker">CANONICAL SEQUENCE</p><h2>마일스톤 진행 상황</h2></div><p>표시 상태는 프로젝트의 00-project-sequence에서 직접 읽습니다. 잠긴 단계는 선행 gate 통과 전 실행하지 않습니다.</p></div><div class="milestone-list">${project.milestones.map((row) => `<article class="milestone-row"><span class="milestone-order">${escapeHtml(row.order)}</span><h3>${escapeHtml(row.stage)}</h3><span class="status-pill ${escapeHtml(row.status_key)}">${escapeHtml(row.status)}</span><p>${escapeHtml(row.entry_criterion)}</p></article>`).join("")}</div></section>
    <section class="section shell"><div class="section-heading split-heading"><div><p class="kicker">REVIEW & SOURCE</p><h2>검토가 필요한 초점</h2></div><p>${escapeHtml(project.review_focus)}</p></div><div class="project-grid"><article class="project-card" data-number="A"><span class="project-code">ADMIN REVIEW</span><h3>운영·근거 완결성</h3><p>현재까지 ${reviewCounts.admin}개의 관리자 설문이 이 프로젝트의 local ledger에 기록되어 있습니다.</p><a class="card-link" href="/admin-review.html?project=${escapeHtml(project.id)}"><span>관리자 검토</span><span>→</span></a></article><article class="project-card" data-number="C"><span class="project-code">CLINICAL REVIEW</span><h3>임상적 타당성·사용성</h3><p>현재까지 ${reviewCounts.clinician}개의 임상의 설문이 기록되어 있습니다. 환자 식별정보는 수집하지 않습니다.</p><a class="card-link" href="/clinician-review.html?project=${escapeHtml(project.id)}"><span>임상의 검토</span><span>→</span></a></article><article class="project-card" data-number="S"><span class="project-code">CANONICAL SOURCES</span><h3>계획과 마일스톤 원본</h3><p><code>${escapeHtml(project.plan_document)}</code><br><br><code>${escapeHtml(project.milestone_document)}</code></p><a class="card-link" href="/artifacts.html"><span>등록 산출물</span><span>→</span></a></article></div></section>
    <aside class="project-boundary shell"><b>CLAIM BOUNDARY</b><p>${escapeHtml(project.boundary)}</p></aside>`;
}

function renderArtifacts(data) {
  const available = data.artifacts.filter((artifact) => artifact.available);
  document.querySelector("#artifact-total").textContent = String(available.length);
  const figures = available.filter((artifact) => artifact.kind === "image");
  document.querySelector("#artifact-grid").innerHTML = figures.length ? figures.map((artifact) => artifactCard(artifact)).join("") : '<div class="loading-panel">현재 workspace에 표시 가능한 figure가 없습니다.</div>';
}

function projectOption(project) {
  return `<option value="${escapeHtml(project.id)}">${escapeHtml(project.korean_name)}</option>`;
}

function renderReview(data) {
  const select = document.querySelector("#project-select");
  select.insertAdjacentHTML("beforeend", data.projects.map(projectOption).join(""));
  const requestedProject = new URLSearchParams(window.location.search).get("project");
  if (requestedProject && data.projects.some((project) => project.id === requestedProject)) select.value = requestedProject;
  const updateContext = () => {
    const project = data.projects.find((item) => item.id === select.value);
    const context = document.querySelector("#review-project-context");
    if (!project) { context.textContent = "프로젝트를 선택하면 현재 gate와 검토 초점을 표시합니다."; return; }
    context.innerHTML = `<span>CURRENT GATE · ${escapeHtml(project.current_gate.status)}</span><b>${escapeHtml(project.current_gate.stage)}</b><span>${escapeHtml(project.review_focus)}</span>`;
  };
  select.addEventListener("change", updateContext);
  updateContext();

  const confidence = document.querySelector("#confidence");
  if (confidence) confidence.addEventListener("input", () => { document.querySelector("#confidence-output").textContent = `${confidence.value} / 5`; });

  document.querySelector("#review-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const button = formElement.querySelector("button[type='submit']");
    const result = document.querySelector("#review-result");
    const payload = Object.fromEntries(new FormData(formElement).entries());
    formElement.querySelectorAll("input[type='checkbox']").forEach((input) => { payload[input.name] = input.checked; });
    if (payload.confidence) payload.confidence = Number(payload.confidence);
    button.disabled = true;
    button.textContent = "기록 중…";
    try {
      const surveyType = document.body.dataset.survey;
      const response = await fetch(`/api/survey/${surveyType}`, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrfToken }, body: JSON.stringify(payload) });
      const responsePayload = await response.json();
      if (!response.ok || responsePayload.error) throw new Error(responsePayload.error || "검토 기록에 실패했습니다.");
      result.hidden = false;
      result.className = "form-result";
      result.textContent = `검토가 기록되었습니다 · ${responsePayload.record.record_sha256.slice(0, 12)}…`;
      showToast("프로젝트 소유 ledger에 검토를 기록했습니다.");
      formElement.querySelector("textarea").value = "";
    } catch (error) {
      result.hidden = false;
      result.className = "form-result error";
      result.textContent = error.message;
      showToast(error.message, true);
    } finally {
      button.disabled = false;
      button.innerHTML = `${document.body.dataset.survey === "admin" ? "관리자" : "임상의"} 검토 제출 <span>→</span>`;
    }
  });
}

async function start() {
  try {
    const data = await loadPortfolio();
    const page = document.body.dataset.page;
    if (page === "home") renderHome(data);
    if (page === "project") renderProject(data, document.body.dataset.project);
    if (page === "artifacts") renderArtifacts(data);
    if (page === "review") renderReview(data);
  } catch (error) {
    showToast(error.message, true);
    const loading = document.querySelector(".loading-panel, .loading");
    if (loading) loading.textContent = `불러오기 실패: ${error.message}`;
  }
}

start();
