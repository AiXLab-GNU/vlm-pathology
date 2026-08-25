---
document_id: fm8-residual-discovery-entry-audit-report
owner_project: quantitative_foundation_model_validation
document_type: report
status: complete
created: 2026-08-25
canonical_path: projects/quantitative_foundation_model_validation/milestones/fm8_residual_discovery_entry_audit/outputs/fm8-residual-discovery-entry-audit-report.md
---

# FM8 residual-discovery entry audit report

## Final decision: NO-GO

FM8 본 residual-discovery 연구와 blinded pathology review를 시작할 자격이 없다. 필수
G4 shortcut-metadata gate가 FAIL이고, G6 blinded-review legality/reproducibility와 residual
stability가 NOT-EVALUABLE이다. 이 판정은 논문 1을 재개하지 않으며 기존 FM6 결과나
Virchow--CHIMERA encoder-specific whole-tissue T를 변경하지 않는다.

## Evidence inventory

`fm8_artifact_availability_matrix.csv` 10행과
`fm8_source_evidence_manifest.csv` 20행을 생성했다. 확인된 핵심 수치는
다음과 같다.

- PRECISE FM2--FM5: 25명, 27 sessions, 1,218 paired tiles. 두 encoder의 crop hash,
  embedding row와 5개 환자 fold는 일치하지만 scanner/stain과 disease outcome/head가 없다.
- TCGA source: 392명/80 events, 437 WSI, 27,968 paired 394.24 µm tiles. OOF score는 encoder별
  392행이고 paired patient table은 784행이다. Age는 encoder-row 기준 8/784, path-T는
  18/784 결측이다. Scanner ID는 23/437 slides에서 missing이다.
- TCGA site-heldout: 7개 eligible TSS site, 289명/69 events. 이는 독립 external cohort가
  아니라 내부 site transport다.
- LEOPARD: 508명/87 events, 32,512 paired tiles. 두 encoder embedding과 outcome은 있으나
  ISUP/Gleason, treatment와 임상/기술 panel이 없어 동일 residual recurrence는 NOT-EVALUABLE이다.
- CHIMERA: 95명/27 events, 190 WSI, 12,160 paired tiles. ISUP/Gleason은 3/95 source
  discrepancy이고 earlier therapy는 93/95가 blank다. MPP와 tissue mask fraction은 있으나
  site/stain/scanner/color/blur/fold/compression은 없다.

모든 위 CSV의 row count, unique patient 수, key duplicate, fold independence, missing cell과
SHA-256은 `fm8_source_integrity_audit.csv` 13행에 연결했다.

## Estimands and source lock

Rscore은 환자 단위 `S_k-g_k(M,C,Q)`, Rrepr은 paired tile 단위 `(I-P_M,k)Z_k`로 분리했다.
모든 normalization, imputation, regularization, rank와 projection은 source outer-training
fold 안에서만 적합하고 환자는 OOF residual을 한 번만 받는다. Rrepr ranking scalar는
head-projected `Trepr_k`로 별도 고정했다. 두 encoder embedding component를 직접 대응시키지
않는다.

Threshold는 source OOF q10/q90, discordance는 encoder percentile gap 0.50, seed는 260825,
sampling cap은 환자당 8/slide당 2/환자당 4 slides다. Target cohort에서는 refit,
recalibration, threshold/quota/rank 변경을 금지한다. 이 규칙은 NO-GO 해소 전 실행되지 않는다.

Known panel은 ISUP 중심이며 알려진 병리를 모두 제거하지 않는다. 허용 해석은
`residual after the available prespecified metric panel`뿐이다. Whole-tissue residual을
tumor-specific residual이나 biomarker로 부르지 않는다.

## Gate decisions

| Gate | Decision | Evidence-linked reason |
|---|---|---|
| G1 separate leakage-free Rrepr/Rscore | PASS | TCGA paired embeddings, OOF score, five patient folds and locked protocol |
| G2 source threshold/sampling lock | PASS | q10/q90, percentile gap, caps, quotas and seed fixed before residual execution |
| G3 paired encoder comparison | PASS | PRECISE, TCGA, LEOPARD and CHIMERA paired audits |
| G4 shortcut metadata sufficient | **FAIL** | stain/color, blur/fold, tumor amount/purity, specimen and external site/scanner gaps |
| G5 independent recurrence feasible | PASS, numeric only | CHIMERA supports same-panel numeric application; morphology promotion remains blocked |
| G6 lawful reproducible blinded package | **NOT-EVALUABLE** | no pathologist burden/approval, reviewer access record or written CHIMERA review clearance |
| G7 limited-panel interpretation | PASS | explicit available-panel and whole-tissue ceiling |
| R1 residual stability | **NOT-EVALUABLE** | no residual manifest or fold/seed/rank stability result |
| R2 cross-project source provenance | **FAIL** | age/path-T source points to PBV generated model workspace |

`fm8_gate_decision_matrix.csv` 9행이 machine-readable authority다. 필수
gate 하나라도 FAIL이면 NO-GO이므로 G4만으로도 전체 NO-GO다. NOT-EVALUABLE은 GO로
간주하지 않는다.

## Shortcut and external recurrence

Shortcut matrix 15행 중 cross-cohort PASS는 MPP/FOV와 tissue
fraction/area뿐이다. Tissue mask는 tumor mask가 아니며 실패한 independent detector gate를
대체하지 않는다. Shortcut과 morphology를 구분할 수 없는 item은 review candidate로
승격할 수 없다.

CHIMERA raw paired artifact는 두 encoder의 numeric recurrence 적용을 허용하지만 prior
Virchow-only functional T는 common residual gate가 아니다. LEOPARD는 동일 M,C,Q가 없어
source-locked residual recurrence가 NOT-EVALUABLE이다. Endpoint threshold와 censoring
equivalence가 없으므로 TCGA와 CHIMERA patient-level pooling은 금지한다.

## Blinded review feasibility

Encoder/residual/outcome/site masking, seeded random order, matched controls, not-evaluable
preservation, patient-clustered reviewer split, hidden WSI provenance와 repeat/adjudication
schema는 설계 가능하다. 그러나 pathologist 승인, review sample size와 minutes/item,
repeat fraction, adjudicator, IRB/DUA/access role 및 CHIMERA patient-level image review 권한이
없다. 이 증거가 문서화되기 전 package 생성·export와 실제 판독을 시작하지 않는다.

## Required next work

`fm8_blocker_action_list.csv` 8행의 우선순서를 따른다. 먼저 shortcut
metadata와 QFM/shared covariate provenance를 hash-lock한다. 그 다음에만 source-only
residual stability를 감사하고, 마지막으로 review governance와 burden을 승인한다. 모든
필수 gate가 PASS가 된 새 entry audit 없이는 FM8 본 연구 또는 두 번째 논문 workstream을
개시하지 않는다.

## Reproducibility

이 audit은 기존 artifacts를 읽기만 했고 residual, target outcome tuning 또는 GPU 분석을
수행하지 않았다. Nonvolatile clean-rerun status는 `PASS_EXACT_HASH`다. 실행 seed, Python
version, input/output SHA-256와 volatile execution-time 제외 규칙은
`fm8_entry_audit_run_config.json`에 저장한다.
