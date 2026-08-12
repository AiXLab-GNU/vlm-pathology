# Major-revision analysis execution summary

**실행일:** 2026-08-03
**기준 계획:** `paper/revision_analysis_plan.md`

## 결론

엄격한 nested/refit 분석은 기존 in-sample confounder 결론을 약화시켰다. PTEN과 AR은
각 target에 대한 pooled association 자체는 남지만, grade-only 모델에 대한 held-out
증분은 지지되지 않는다. Post-hoc marker 7은 grade-only 대비 증분만 유지하며, 표준
임상변수와 site까지 포함하면 증분이 없다.

| 분석 | Held-out 증분 (95% CI) | Refit permutation p | 17-test BH q |
|---|---:|---:|---:|
| PTEN, grade-only | ΔAUROC +0.019 (−0.025, +0.068) | 0.203 | 0.314 |
| AR, grade-only | ΔR² +0.004 (−0.036, +0.042) | 0.176 | 0.299 |
| Marker 7, grade-only | ΔC-index +0.062 (+0.008, +0.119) | 0.0100 | 0.028 |
| Marker 7, fully adjusted | ΔC-index +0.002 (−0.012, +0.015) | 0.305 | 0.399 |

Permutation 유효 반복은 앞의 세 행이 2,000/2,000, fully adjusted가 1,998/2,000이다.
후자의 두 실패는 surgical-margin separation에 따른 Cox 수렴 실패이며 0으로 대체하지
않았다.

## 임상 계층 M0--M5

| 모델 | n / events | Held-out C-index (95% CI) |
|---|---:|---:|
| M0 grade | 270 / 57 | 0.645 (0.556, 0.729) |
| M1 grade+age | 270 / 57 | 0.652 (0.563, 0.738) |
| M2 grade+PSA+pT | 165 / 31 | 0.687 (0.589, 0.788) |
| M3 M2+margin | 153 / 30 | 0.855 (0.808, 0.902) |
| M4 M3+site | 153 / 30 | 0.881 (0.820, 0.935) |
| M5 M4+marker7 | 153 / 30 | 0.879 (0.815, 0.934) |

Paired M5−M4 ΔC-index는 −0.0024 (95% CI −0.0118, +0.0064)다. PSA missingness가
103/270 (38%), margin missingness가 53/270 (20%)로 complete-case 감소의 주원인이다.

## Endpoint 및 생존 민감도

- 500 TCGA case 전체 provenance 표를 생성했고, 기존 `bcr.csv`는 재생성 전후 SHA-256이
  동일했다(493 labels, 111 events).
- 엄격 recurrence-only 정의는 반드시 더 이른 tumor-free 방문 뒤 later with-tumor를
  요구한다. 전체 qualifying event는 11건; embedded cohort는 n=220, 7 events뿐이다.
  Marker7 C-index=0.655, 5-year td-AUROC=0.566으로 방향은 양수지만 근거가 매우 희박하다.
- 표준 PFS: n=270/42 events, C-index=0.586, 5-year td-AUROC=0.610.
- 표준 DFS: n=192/11 events, C-index=0.605, 5-year td-AUROC=0.592.
- 원 endpoint의 td-AUROC는 1년 0.740에서 5년 0.636으로 감소하며, 3/5년 calibration은
  외부계수의 위험도를 상당히 과대예측한다.

## 재현성 및 산출물

- 임상 sample JSON을 저장소 상대경로에 공개 API로 재생성; `/tmp/claude-*` Python 참조 0개.
- `resources/projects/prostate_biomarker_validation/model_workspace/statistical_corrections_summary.csv`에 encoder, validation type, reliability tier,
  기존 13-test q와 revision 17-test q를 모두 보존.
- SPOP patient AUROC 0.519 (95% CI 0.408--0.627); 80% power MDE AUROC=0.661. 따라서
  “큰 효과는 지지되지 않음”이지 작은 효과의 부재를 증명한 것은 아니다.
- 동일 90-slide/85-patient/seed grid(tiles 16/32/64 × mpp 0.44/0.88/1.76)에서 PTEN
  AUROC 0.488--0.643, AR ρ 0.114--0.355 (R² −0.074~+0.175), SPOP AUROC
  0.341--0.601. AR은 방향은 양수지만 크기가 가변적이고, SPOP은 chance 양쪽을 오간다.
- 원고 claim, 17-test supplement, nested forest figure, reliability map을 갱신하고
  XeLaTeX build를 통과했다.

## Virchow 교차검증 (2026-08-03 추가)

7단계 착수 전에, nested confounder audit의 PTEN/AR 약화 결과가 CONCH 특이적인지
확인하기 위해 같은 nested bootstrap 파이프라인을 Virchow 임베딩(같은 300슬라이드
universe, 재임베딩 불필요)으로 재실행했다(`pilot_confounder_audit_nested_virchow.py`).

| 분석 | CONCH Δ (95% CI) | Virchow Δ (95% CI) |
|---|---:|---:|
| PTEN, grade-only (ΔAUROC) | +0.019 (−0.025, +0.068) | +0.035 (−0.013, +0.087) |
| AR, grade-only (ΔR²) | +0.004 (−0.036, +0.042) | +0.019 (−0.015, +0.051) |

두 인코더 모두 같은 정성적 결론(작고, 양의 방향이나, CI가 0을 포함)에 수렴한다 —
CONCH 임베딩 특이적 아티팩트가 아니라는 근거. 마커7은 재검증하지 않았다(Virchow
zero-shot이 이미 독립적으로 실패했으므로 추가 정보 없음). 원고(`results.tex`
confounder-audit 절, `discussion.tex`)에 반영하고 XeLaTeX build 재확인(21페이지,
에러 0).

## 남은 범위

Multiple imputation, Virchow 5-seed/128-tile/tumor-enriched 확장, bootstrap ΔBrier는
우선순위 낮음으로 보류. 9-section 원고 재구성(P3)은 Virchow 교차검증까지 완료돼
착수 가능하다고 판단(2026-08-03).
