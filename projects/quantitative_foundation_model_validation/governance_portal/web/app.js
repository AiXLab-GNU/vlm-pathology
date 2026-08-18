let state = null;
let csrfToken = "";
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

function pill(text) {
  const lower = String(text).toLowerCase();
  const cls = lower.includes("pass") || lower.includes("go") ? "pass" : lower.includes("amber") || lower.includes("conditional") ? "amber" : lower.includes("lock") || lower.includes("stop") ? "lock" : "";
  return `<span class="pill ${cls}">${esc(text)}</span>`;
}

function table(rows, columns) {
  if (!rows?.length) return "<p>표시할 항목이 없습니다.</p>";
  return `<table><thead><tr>${columns.map(c => `<th>${esc(c.label)}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr>${columns.map(c => `<td>${c.render ? c.render(row[c.key], row) : esc(row[c.key])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function render(data) {
  state = data;
  csrfToken = data.csrf_token;
  $("#draft-decision").textContent = data.g8.finalized ? "G8 CONDITIONAL GO · FINAL" : data.draft_decision;
  $("#protocol-id").textContent = data.protocol_id;
  const tiers = data.summary.medical_metrics || {};
  $("#t1-count").textContent = tiers.T1 ?? tiers.t1 ?? "1";
  $("#analysis-count").textContent = data.summary.analysis_measures;
  $("#combination-count").textContent = data.summary.candidate_combinations;
  $("#approved-list").innerHTML = data.approved_combinations.map(x => `<li>${esc(x)}</li>`).join("");
  $("#prohibited-list").innerHTML = data.permanent_prohibitions.map(x => `<li>${esc(x)}</li>`).join("");
  $("#combination-table").innerHTML = table(data.combinations, [
    {key:"combination_id",label:"ID"},{key:"model",label:"Model"},{key:"target",label:"Target"},
    {key:"input_fov_um",label:"Input FOV µm"},{key:"target_role",label:"Role"},
    {key:"m8_recommendation",label:"M8 recommendation",render:v=>pill(v)},
    {key:"unresolved_requirement",label:"추가 요구사항"}
  ]);
  $("#question-list").innerHTML = data.questions.map((q, i) => `<details class="question" ${i===0?"open":""}><summary><span class="question-id">${esc(q.question_id)}</span><span class="question-title">${esc(q.question)}</span>${pill(q.status)}</summary><div class="question-answer"><p>${esc(q.integrated_answer)}</p><small>Claim limit · ${esc(q.claim_limit)}</small></div></details>`).join("");
  const fm1 = data.fm1 || {available:false};
  $("#fm1-status").textContent = fm1.available ? "FM1 registry audit complete · H2 execution remains locked" : "FM1 산출물이 아직 없습니다.";
  $("#fm1-medical").textContent = fm1.summary?.medical_metric_count ?? "—";
  $("#fm1-analysis").textContent = fm1.summary?.analysis_measure_count ?? "—";
  $("#fm1-h1").textContent = fm1.summary?.immediately_executable_descriptive_H1 ?? "—";
  $("#fm1-h2").textContent = fm1.summary?.H2_pairs_executable_now ?? "—";
  $("#fm1-links").innerHTML = fm1.available ? fm1.outputs.map(name => `<a href="/api/fm1/${encodeURIComponent(name)}" target="_blank" rel="noopener">${esc(name)}</a>`).join("") : "";
  for (const stage of ["fm2","fm3","fm4","fm5"]) {
    const milestone = data.main_study?.[stage] || {available:false,outputs:[]};
    $(`#${stage}-status`).textContent = milestone.available ? milestone.status : "산출물 없음";
    $(`#${stage}-links`).innerHTML = milestone.available ? milestone.outputs.map(name => `<a href="/api/main-study/${stage}/${encodeURIComponent(name)}" target="_blank" rel="noopener">${esc(name)}</a>`).join("") : "";
  }
  const fm4 = data.main_study?.fm4 || {};
  $("#fm4-mde").textContent = fm4.available_power?.minimum_detectable_abs_rho_80pct_power ? `|ρ| ${fm4.available_power.minimum_detectable_abs_rho_80pct_power}` : "—";
  const fm4Approval = data.fm4_scope_approval || {};
  $("#fm4-snapshot-hash").textContent = fm4Approval.evidence_snapshot_sha256 || "—";
  $("#fm4-approval-state").textContent = fm4Approval.finalized ? "APPROVED" : fm4Approval.ready_to_finalize ? "READY" : fm4Approval.latest ? String(fm4Approval.latest.decision).toUpperCase() : "PENDING";
  $("#fm4-approval-message").textContent = fm4Approval.finalized ? "제한적 exploratory/descriptive FM4 실행 범위가 확정되었습니다." : fm4Approval.ready_to_finalize ? "현재 snapshot에 대한 Approve 판정이 기록되었습니다. 최종 확정할 수 있습니다." : fm4Approval.latest && !fm4Approval.evidence_current ? "판정 후 근거가 변경되었습니다. 현재 snapshot을 다시 검토하십시오." : "현재 evidence snapshot에 대한 연구책임자 판정이 필요합니다.";
  $("#finalize-fm4").disabled = !fm4Approval.ready_to_finalize || fm4Approval.finalized;
  if (fm4Approval.finalized) {
    $("#fm4-approval-form").querySelectorAll("input, select, textarea, button").forEach(element => { element.disabled = true; });
    $("#fm4-approval-form button[type='submit']").textContent = "FM4 승인 확정됨";
  }
  $("#boundary-grid").innerHTML = data.scientific_boundaries.map(x => `<article class="boundary ${x.can_approval_resolve?"resolvable":"evidence"}"><span class="tag">${x.can_approval_resolve?"APPROVAL CAN RESOLVE":"ADDITIONAL EVIDENCE REQUIRED"}</span><h3>${esc(x.issue)}</h3><p>${esc(x.current_evidence)}</p><b>${esc(x.effect)}</b><p>해결: ${esc(x.resolution)}</p></article>`).join("");
  $("#snapshot-hash").textContent = data.g8.evidence_snapshot_sha256;
  $("#evidence-list").innerHTML = data.evidence_files.map(name => `<a href="/api/evidence/${encodeURIComponent(name)}" target="_blank" rel="noopener">${esc(name)}</a>`).join("");
  $("#risk-count").textContent = `(${data.risks.length})`;
  $("#risk-table").innerHTML = table(data.risks,[{key:"risk_id",label:"ID"},{key:"severity",label:"Severity",render:v=>pill(v)},{key:"scope",label:"Scope"},{key:"observed",label:"Observed"},{key:"impact",label:"Impact"},{key:"disposition",label:"Disposition"},{key:"owner",label:"Owner"}]);

  const roles = Object.entries(data.g8.roles);
  $("#role-grid").innerHTML = roles.map(([id,r]) => `<article class="role ${r.present&&r.evidence_current?"complete":""}"><span>${esc(id)} · ${r.required?"REQUIRED":"ADVISORY"}</span><strong>${esc(r.label)}</strong><small>${r.present ? `${esc(r.reviewer_name)} · ${esc(r.decision)}${r.evidence_current?"":" · 근거 변경됨"}` : r.required ? "최종 승인 대기" : "선택 자문"}</small></article>`).join("");
  const requiredCount = data.g8.required_role_count;
  const current = roles.filter(([,r]) => r.required && r.present && r.evidence_current && r.decision === "conditional_go").length;
  $("#approval-progress").textContent = `${current} / ${requiredCount}`;
  $("#progress-bar").style.width = `${current/requiredCount*100}%`;
  $("#g8-message").textContent = data.g8.finalized ? "G8이 최종 확정되었습니다. P0-M9 실행이 가능합니다." : data.g8.ready_to_finalize ? "연구책임자가 현재 근거를 Conditional Go로 승인했습니다." : "연구책임자의 최신 Conditional Go 판정이 필요합니다.";
  $("#finalize-g8").disabled = !data.g8.ready_to_finalize || data.g8.finalized;

  const m9 = data.g9.status || {status:"not_started"};
  $("#m9-status").textContent = String(m9.status || "not_started").toUpperCase().replaceAll("_"," ");
  $("#m9-detail").textContent = m9.error || (m9.attempt_id ? `${m9.attempt_id} · mismatch ${m9.mismatch_count ?? "—"}` : "G8 확정 후 별도 출력 디렉터리에서 전체 GPU 단계와 source/output hash 감사를 실행합니다.");
  const running = m9.status === "running" || data.m9_launcher?.running;
  $("#run-m9").disabled = !data.g8.finalized || running || data.g9.finalized;
  $("#handoff-result").innerHTML = data.g9.finalized ? `<div class="result-pass"><b>P0-G9 PASS</b> · FM1, 범위 제한 FM2와 descriptive FM3 인계 bundle이 고정되었습니다.</div>` : "";
  $("#last-updated").textContent = `refreshed ${new Date().toLocaleString("ko-KR")}`;
}

function toast(message, error=false) {
  const node = $("#toast"); node.textContent = message; node.className = error ? "show error" : "show";
  setTimeout(() => node.className="", 4200);
}

async function refresh(silent=false) {
  try {
    const response = await fetch("/api/status", {cache:"no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "상태를 불러오지 못했습니다.");
    render(data);
  } catch (error) { if (!silent) toast(error.message, true); }
}

async function post(path, payload) {
  const response = await fetch(path,{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":csrfToken},body:JSON.stringify(payload)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "요청이 실패했습니다.");
  return data;
}

$("#approval-form").addEventListener("submit", async event => {
  event.preventDefault();
  const formElement = event.currentTarget;
  const form = new FormData(formElement);
  const submitButton = formElement.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  const payload = Object.fromEntries(form.entries());
  ["reviewed_evidence","accept_scope","accept_risks","accept_prohibitions","identity_attested"].forEach(key => payload[key]=form.has(key));
  try { await post("/api/approval",payload); toast("판정 기록이 append-only ledger에 저장되었습니다."); formElement.reset(); await refresh(); }
  catch(error){ toast(error.message,true); }
  finally { submitButton.disabled = false; }
});

$("#finalize-g8").addEventListener("click", async () => {
  try { await post("/api/finalize-g8",{confirmation:$("#g8-confirmation").value}); toast("P0-G8이 최종 확정되었습니다."); await refresh(); }
  catch(error){ toast(error.message,true); }
});

$("#fm4-approval-form").addEventListener("submit", async event => {
  event.preventDefault();
  const formElement = event.currentTarget;
  const form = new FormData(formElement);
  const submitButton = formElement.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  const payload = Object.fromEntries(form.entries());
  ["reviewed_fm4_packet","accept_exploratory_scope","accept_power_limit","accept_fm4_prohibitions","fm4_identity_attested"].forEach(key => payload[key]=form.has(key));
  try { await post("/api/fm4-scope-approval",payload); toast("FM4 범위 판정이 append-only ledger에 저장되었습니다."); formElement.reset(); await refresh(); }
  catch(error){ toast(error.message,true); }
  finally { submitButton.disabled = false; }
});

$("#finalize-fm4").addEventListener("click", async () => {
  try { await post("/api/finalize-fm4-scope",{confirmation:$("#fm4-confirmation").value}); toast("FM4 제한적 실행 범위가 최종 승인되었습니다."); await refresh(); }
  catch(error){ toast(error.message,true); }
});

$("#run-m9").addEventListener("click", async () => {
  try { const result=await post("/api/run-m9",{confirmation:$("#m9-confirmation").value}); toast(`P0-M9 clean rerun을 시작했습니다 (PID ${result.pid}).`); await refresh(); }
  catch(error){ toast(error.message,true); }
});

refresh();
setInterval(() => refresh(true), 5000);
