# 정량 지표–질병 적용 카탈로그 및 문헌 서베이

버전 0.3.0 · 조사 기준일 2026-08-11

## 결론부터

기존 113개 목록은 의료 측정치와 모델평가·통계·QC가 섞인 legacy measure registry다.
새 의료 정량지표는 clinician-native T1부터 model-derived T4까지 분리하며, AUROC,
R², bootstrap과 hash는 의료 tier에서 제외한다. 질병 적용 역할은 다음과 같이 나뉜다.

1. 실제 임상 assay와 병리 형태를 전제로 한 **진단 보조**: 전립선 AMACR–basal-cell
   panel, 유두상 신세포암 IHC panel. 패키지의 chromogen 수치는 임상 IHC가 아닌
   연구용 proxy이므로 외부 assay가 반드시 필요하다.
2. **후보 triage**: 현재 프로젝트에서 실행 준비가 된 것은 고정 PRECISE 전립선암
   PNI 후보 순위화뿐이다. whole-slide PNI 진단 또는 임상 진단기로 해석하지 않는다.
3. **병리·예후 특징**: 여러 암종의 PNI morphology와 nerve-interface geometry.
   PNI의 예후 관련 문헌은 있지만 이 패키지의 전립선 모델이 타 암종에 전이된다는
   근거는 아니다.
4. **질병 비특이 평가·통계·QC**: AUROC, AP, calibration, bootstrap, 생존분석,
   재현성 지표. 모델을 평가하지만 스스로 질병을 진단하지 않는다.

## 조사 방법과 해석 원칙

- PubMed에 등재된 systematic review/meta-analysis를 우선하고, multi-cohort validation,
  panel study, 방법개발 연구를 보완적으로 사용했다.
- 지표 이름이 유사하다는 이유만으로 전이를 주장하지 않았다. `package_readiness`로
  현재 사용 가능, 외부 panel 필요, 연구 전용, 미검증 전이, contour 대기, 현재 설계상
  미지지를 분리했다.
- `diagnostic_adjuvant`는 전문의 형태 판독 및 외부 임상검사와 함께 쓰는 보조 역할이다.
  `prognostic_stratification`은 암의 존재를 진단한다는 뜻이 아니다.
- 문헌이 PNI의 임상 중요성을 보여도, 본 패키지의 후보점수·NMS·threshold를 다른
  장기나 암종에 재사용할 수 있다는 뜻은 아니다.
- 기계 판독 가능한 세부 근거와 제한은 `disease_metric_uses.tsv`, 조합은
  `metric_combinations.tsv`, 인용 메타데이터는 `survey_references.tsv`가 기준이다.

## 질병·용도 카탈로그

| 질병/용도 ID | 임상·연구 역할 | 패키지 준비도 | 핵심 지표군 | 해석 |
|---|---|---|---|---|
| `prostate_adenocarcinoma` | 진단 보조 | 외부 panel 필요 | AMACR/HMWCK chromogen·양성분율 | 실제 AMACR + HMWCK/p63 + H&E 형태의 panel 근거이며 package 값은 proxy |
| `prostate_pni` | 후보 triage | 현재 프로젝트 사용 가능 | 3개 component score, 고정 combined score, NMS rank, capture/coverage | PRECISE 선택 후보의 병리 검토 우선순위만 지원 |
| `prostate_pni` | 형태 annotation | contour 완료 전 유예 | 관계·방향·추적·branch 범주, nerve 면적/직경, 포위·접촉·거리 | 선택된 14 focus의 pilot; 분포·예후 추정 불가 |
| `prostate_grade` | grade 연구 특징 | 연구 전용 | lumen, nuclear density, GLCM texture, Spearman, QWK | 단순 형태 특징은 Gleason pattern 또는 cribriform 정의가 아님 |
| `prostate_recurrence` | 예후모형 평가 | 연구 전용 | C-index, td-AUC, IBS, calibration, paired delta | 지표 자체는 진단·치료결정 규칙이 아님 |
| `prostate_pten_erg` | 분자 screening 연구 | 연구 전용 | cosine, AUROC, correlation, R², bootstrap | IHC/FISH/분자검사를 대체하지 않음 |
| `prostate_ar_activity` | 분자 phenotype 연구 | 연구 전용 | correlation, R², site delta, stability | site/scanner 분리가 해결되지 않음 |
| `prostate_spop` | 변이 screening audit | 현재 설계상 미지지 | AUROC, MDE, chance-or-worse, stability | frozen primary configuration으로 mutation 진단 불가 |
| `papillary_renal_cell_carcinoma` | 감별 진단 보조 | 외부 panel 필요 | AMACR proxy + lumen shape | 실제 AMACR은 CK7/CAIX/TFE3 및 형태와 panel 해석 필요 |
| `colorectal_pni` | 병리 고위험/예후 특징 | 문헌 지지·전이 미검증 | PNI 범주, nerve diameter, 포위·접촉·거리 | CRC용 schema 및 판독 재현성을 새로 검증해야 함 |
| `colorectal_pni_prediction` | 후보선별 연구 | 연구 전용 | texture, nuclear density, AUROC, bootstrap | CT/MRI radiomics와 H&E feature를 동일시할 수 없음 |
| `pancreatic_pni` | 병리 고위험/예후 특징 | 문헌 지지·전이 미검증 | PNI morphology–geometry | PDAC nerve plexus 문맥과 암종별 annotation 필요 |
| `head_neck_squamous_cell_carcinoma` | 병리 고위험/예후 특징 | 문헌 지지·전이 미검증 | PNI morphology–geometry | subsite, HPV, intra/extratumoral PNI 층화 필요 |
| `oral_squamous_cell_carcinoma` | 병리 고위험/예후 특징 | 문헌 지지·전이 미검증 | PNI, nerve diameter, distance, contact | 고전 PNI와 단순 근접효과를 분리해야 함 |
| `adenoid_cystic_carcinoma` | 병리 고위험/예후 특징 | 문헌 지지·전이 미검증 | PNI morphology–geometry | salivary-gland 전문 판독 필요 |
| `gastric_pni` | 병리 고위험/예후 특징 | 문헌 지지·전이 미검증 | PNI, 포위·접촉·거리 | 위암 진단지표가 아니며 현 contour 미검증 |
| `cholangiocarcinoma_pni` | 병리 고위험/예후 특징 | 문헌 지지·전이 미검증 | PNI, nerve diameter, 포위·접촉·거리 | 해부학적 subtype 및 연구 이질성 고려 필요 |
| `cutaneous_squamous_cell_carcinoma_pni` | 병리 고위험/예후 특징 | 문헌 지지·전이 미검증 | PNI, nerve diameter, 접촉·거리 | clinical PNI와 incidental microscopic PNI 구분 필요 |
| `general_histopathology` | 특징 탐색 | 연구 전용 | nuclear, texture, lumen, embedding | 새 질병별 truth·학습·외부검증 없이는 진단 의미 없음 |

## 추천 조합 20개

| ID | 조합 | 대상 | 준비도/필수 조건 |
|---|---|---|---|
| `C001` | AMACR–HMWCK PIN4 유사 panel | 전립선 선암 진단 보조 | 실제 AMACR/HMWCK/p63와 H&E 전문 판독 필요 |
| `C002` | 고정 PRECISE PNI triage | 전립선 PNI 후보 검토 | 현재 프로젝트 범위에서 사용 가능; 고정 점수/NMS 변경 금지 |
| `C003` | PNI 형태–접촉–거리 profile | 전립선 PNI 구조화 | 형태 label lock 후 전문의 contour 필요 |
| `C004` | gland–nuclear–texture grade panel | Gleason/ISUP 연구 | 환자 분리 학습과 외부 cohort 필요 |
| `C005` | recurrence discrimination–calibration suite | 전립선 재발모형 평가 | endpoint/censoring lock와 임상 공변량 필요 |
| `C006` | PTEN–ERG molecular screening audit | 전립선 분자상태 연구 | IHC/FISH truth, grade 보정, 외부 cohort 필요 |
| `C007` | AR signal–site audit | AR activity 연구 | AR assay와 site/scanner metadata 필요 |
| `C008` | SPOP 약효과–검출한계 audit | SPOP 가능성 평가 | 현재 frozen primary는 미지지 |
| `C009` | renal morphology–IHC panel | 유두상 RCC 감별 보조 | 실제 AMACR/CK7/CAIX/TFE3 및 renal morphology 필요 |
| `C010` | CRC PNI morphology–geometry transfer | 대장직장암 PNI 연구 | CRC-specific protocol과 전문의 검증 필요 |
| `C011` | CRC texture/radiomics PNI panel | CRC PNI 예측 연구 | modality별 새 모델과 외부검증 필요 |
| `C012` | PDAC neural-invasion transfer | 췌관 선암 PNI 연구 | PDAC-specific annotation; 전립선 점수 재사용 금지 |
| `C013` | 두경부 PNI extent panel | HNSCC PNI 예후 연구 | subsite/HPV/PNI 위치 층화 필요 |
| `C014` | 범용 형태–embedding discovery | 새 질환 feature 탐색 | 질병별 truth·외부 cohort·site metadata 필요 |
| `C015` | serial H&E–AMACR–HMWCK spatial profile | 전립선 PNI 공간 phenotype | registration QC와 전문의 contour 통과 후만 계산 |
| `C016` | 구강암 PNI proximity–extent panel | OSCC PNI 연구 | 고전 PNI와 단순 근접효과 분리 필요 |
| `C017` | 선양낭성암 PNI extent panel | ACC PNI 예후 연구 | salivary-gland 판독과 cohort 재검증 필요 |
| `C018` | 위암 PNI morphology–interface panel | 위선암 PNI 예후 연구 | 병기·절제연 보정과 증분평가 필요 |
| `C019` | 담관암 PNI subtype–extent panel | 담관암 PNI 예후 연구 | 해부학적 subtype 층화와 새 검증 필요 |
| `C020` | 피부 SCC PNI risk-feature panel | cSCC PNI 예후 연구 | clinical/incidental PNI와 nerve caliber 구분 필요 |

## 의료 tier와 legacy analysis measure를 빠짐없이 해석하는 방법

모든 의료 지표와 legacy analysis measure는 `all_metric_disease_scopes()`에서 정확히
한 행을 받는다. 문헌 또는 프로젝트 설계에 직접 연결된 값에는 질병 ID와 역할이 붙고,
나머지는 tier 또는 domain에 따라 보수적으로 분류한다.

- `T1`: clinician-native 의료 기준축
- `T2`: clinician-anchored 파생계측
- `T3`: 연구용 computational image/spatial proxy
- `T4`: 모델 파생 score/rank/representation

- `model_evaluation`, `survival`, `inference`, `descriptive`, `reproducibility`:
  질병 비특이 방법; 직접 진단용 아님.
- `candidate_generation`: PRECISE 전립선 PNI triage 전용 구현.
- `pni_audit`: 선택된 표본의 ranking 평가; 진단용 아님.
- `morphology`, `contour`: cross-cancer PNI 연구 후보; 암종별 검증 필요.
- `spatial_pilot`: 전립선 serial-section 탐색 특징; 임상 assay 아님.
- 그 외 image feature: 비특이 형태 특징; 질병별 학습·외부검증 필요.

CSV 전체표 생성:

```bash
vlm-pathology-metrics export-survey --directory survey_export
```

이 명령은 `all_metric_disease_scopes.csv`, `disease_metric_uses.csv`,
`metric_combinations.csv`, `survey_references.csv`를 만든다.

## 핵심 문헌

- 전립선 AMACR 진단 보조: [2025 systematic review/meta-analysis](https://pubmed.ncbi.nlm.nih.gov/40605376/), [AMACR/HMWCK/p63 panel study](https://pubmed.ncbi.nlm.nih.gov/31548949/)
- 전립선 PNI와 재발: [2026 systematic review/meta-analysis](https://pubmed.ncbi.nlm.nih.gov/41726852/)
- 전립선 texture CAD 및 cribriform: [texture review](https://pubmed.ncbi.nlm.nih.gov/25055385/), [cribriform meta-analysis](https://pubmed.ncbi.nlm.nih.gov/36216967/)
- H&E 기반 PTEN/ERG: [multi-cohort study](https://pubmed.ncbi.nlm.nih.gov/37307876/), [ERG/PTEN pathology review](https://pubmed.ncbi.nlm.nih.gov/37168967/)
- CRC PNI: [pathology systematic review](https://pubmed.ncbi.nlm.nih.gov/26426380/), [radiomics meta-analysis](https://pubmed.ncbi.nlm.nih.gov/39841228/)
- 두경부·구강·선양낭성암 PNI: [HNSCC meta-analysis](https://pubmed.ncbi.nlm.nih.gov/39061154/), [OSCC meta-analysis](https://pubmed.ncbi.nlm.nih.gov/37958235/), [ACC meta-analysis](https://pubmed.ncbi.nlm.nih.gov/27727107/)
- 췌장·위·담관 PNI: [PDAC meta-analysis](https://pubmed.ncbi.nlm.nih.gov/28317579/), [gastric meta-analysis](https://pubmed.ncbi.nlm.nih.gov/31980559/), [cholangiocarcinoma meta-analysis](https://pubmed.ncbi.nlm.nih.gov/42349784/)
- 피부 편평상피암 PNI: [cSCC meta-analysis](https://pubmed.ncbi.nlm.nih.gov/26762219/)
- 신세포암 AMACR panel: [large renal-tumor cohort](https://pubmed.ncbi.nlm.nih.gov/22009118/), [RCC IHC panel study](https://pubmed.ncbi.nlm.nih.gov/30023184/)
- 연속 tumor–nerve 공간 특징: [PNI biology/outcome study](https://pubmed.ncbi.nlm.nih.gov/29800815/)
- 전립선 3D nuclear feature: [method-development study](https://pubmed.ncbi.nlm.nih.gov/37232213/)

## 사용 금지선

- `ready_project`를 임상 검증으로 번역하지 않는다.
- PNI 예후 연관성을 암 자체의 진단 정확도로 표현하지 않는다.
- 미판독 후보를 음성으로 바꾸지 않는다.
- 선택된 reviewed sample의 AUROC/AP를 모집단 또는 whole-slide 성능으로 일반화하지 않는다.
- 실제 IHC assay 없이 package chromogen proxy를 진단 cutoff로 사용하지 않는다.
- 타 암종에는 전립선 prompt, exemplar, weight, 좌표, NMS, window를 그대로 전이하지 않는다.
