---
document_id: fm6-tcga-wsi-preprocessing-and-aggregation-protocol
owner_project: quantitative_foundation_model_validation
document_type: protocol
status: active
created: 2026-08-15
canonical_path: projects/quantitative_foundation_model_validation/docs/protocols/fm6-tcga-wsi-preprocessing-and-aggregation-protocol-ko.md
---

# FM6 TCGA WSI 전처리·환자 집계 잠금 프로토콜

## 1. 범위

본 문서는 TCGA-PRAD current-GDC 개발 source 392명/80 events의 영상 QC와 향후 embedding
추출 단위를 outcome 확인 전에 고정한다. encoder, probe, disease head 학습 또는 H2 실행을
승인하지 않는다.

## 2. Source와 분석단위

- source WSI는 QFM development manifest에 등록된 GDC file UUID 437장만 허용한다.
- split, bootstrap, endpoint와 최종 representation의 단위는 환자다.
- 같은 환자의 모든 WSI는 같은 fold에 둔다.
- 환자당 1–9장의 slide 수가 학습 가중치가 되지 않도록 환자마다 총 가중치 1을 부여한다.
- outer fold는 seed `260815`의 5-fold이며 BCR event와 exact ISUP의 결합 strata로
  고정한다. 단 event–ISUP 1은 1명뿐이므로 event–ISUP 2와만 사전 결합한다. CHIMERA는
  fold 생성에 사용하지 않고 전체를 external로 보존한다. event·ISUP strata와 fold 크기를
  보존하는 subject swap으로 치료 documented 수의 fold 간 차이를 1명 이하로 맞춘다.

## 3. 영상 무결성과 기술 QC

1. GDC `file_id`, `file_size`, `md5sum`을 모두 일치시킨다.
2. TIFF/SVS header와 lowest-pyramid thumbnail decode가 실패한 파일은 사용하지 않고 실패
   상태를 보존한다. 임의의 대체 slide를 outcome을 보고 선택하지 않는다.
3. Aperio description의 slide별 MPP를 사용한다. MPP가 없거나 비정상인 slide에는 명목
   배율을 대신 넣지 않고 `not_evaluable`을 부여한다.
4. scanner ID, MPP, pyramid, tissue proxy와 TCGA tissue-source-site는 기술적 교란층이며
   biological marker로 해석하지 않는다.

## 4. 물리 FOV와 tile 표본

- 두 encoder에는 동일 중심좌표와 **394.24 micrometre** 정사각형 source FOV를 사용한다.
- native crop edge는 `394.24 / slide_mpp`로 계산하고 경계 좌표는 좌상단 floor·우하단 ceil
  규칙으로 고정한다. resize interpolation과 최종 encoder input size는 embedding 실행
  protocol에서 model weight hash와 함께 별도 고정한다.
- tissue candidate 좌표는 outcome, ISUP, BCR, 치료를 읽지 않는 고정 알고리즘으로 만든다.
- slide별 candidate가 많으면 file UUID에서 파생한 고정 seed로 최대 동일 개수까지
  subsample한다. tile 수가 적은 slide를 복제하지 않는다.

## 5. Tumor-region 경계

TCGA에는 이 source package와 독립적으로 검증된 tumor mask가 없고 CHIMERA mask는
foreground/background tissue mask다. 따라서 다음을 구분한다.

- whole-tissue embedding과 BCR disease-head 방법 개발은 별도 승인 후 가능 후보다.
- ISUP H1, ISUP subspace, targeted erasure와 ISUP-specific residual 주장은 독립 tumor-region
  annotation 또는 검증된 고정 detector의 sensitivity/specificity·실패 로그가 등록되기 전까지
  잠근다.
- weakly supervised attention이나 ISUP/BCR label로 선택한 tile을 독립 tumor truth로
  재사용하지 않는다.

## 6. Slide·환자 집계

Primary 집계는 다음 순서다.

1. slide 내부 eligible tile embedding을 동일 가중 mean으로 집계한다.
2. 환자 내부 slide representation을 동일 가중 mean으로 집계한다.
3. 환자당 한 행을 disease head에 입력한다.

Sensitivity는 slide-level median과 train-fold-only attention pooling으로 제한한다. attention
pooling을 사용할 경우 external CHIMERA에 재학습 없이 적용하고 primary mean 결과와 방향이
다르면 기능적 활용을 주장하지 않는다. max pooling이나 outcome-aware 대표 slide 선택은
primary에서 금지한다.

## 7. 현재 gate

다음 조건을 모두 만족하면 `FM6_PREPROCESSING_ENTRY_CANDIDATE`다.

- 437/437 GDC MD5 검증
- 437/437 header·thumbnail decode와 MPP 또는 명시적 not-evaluable 판정
- patient/slide membership hash와 392명/80 events 재대조
- 5-fold patient manifest hash와 fold별 event·ISUP balance 저장
- 기술 QC 분포 및 실패 로그 저장

이는 embedding 또는 H2 승인과 다르다. ISUP 기능적 활용은 tumor-region, endpoint
harmonization, disease-head 최소 유효성, power와 CHIMERA embargo gate를 추가로 통과해야 한다.
