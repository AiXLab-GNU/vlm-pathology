# PRECISE PNI 전문의 Contour Protocol v1.0

- 문서일: 2026-08-11
- 승인일: 2026-08-11
- 상태: **승인됨 — M6 contour package 구현 및 전문의 contour 수집에 사용**
- 연구 단계: M6 전문의 신경·암–신경 interface contour 준비
- 적용 범위: M5에서 공식 잠금된 선택 PRECISE 신경 후보 14건
- 선행 설계: `projects/precise_pni_candidate_triage/docs/designs/2026-08-06-precise-pni-morphology-rereview-design.md`

## 1. 목적

이 protocol의 목적은 임시 nerve circle이 아니라 병리전문의가 승인한 실제 신경 외곽과 암–신경 interface를 일관된 좌표계와 객체 정의로 수집하는 것이다. 승인 contour는 후속 M7에서 신경 크기, 접촉 길이, 포위율 및 공간 gradient를 계산하기 위한 기준으로 사용한다.

현재 단계는 선택된 14개 focus의 방법개발 pilot이다. 이 contour로 PRECISE 환자의 PNI 형태 분포, whole-slide PNI 음성, 민감도, 예후 또는 외부 타당성을 추정하지 않는다.

## 2. 선행 잠금 상태

M5 결과는 `resources/data/shared/opendataset/PRECISE/pni_morphology_rereview/locked/`에 잠겼다.

- 전체 focus: 14
- 필수값 누락: 0
- 논리 충돌: 0
- `eligible_for_contouring`: 13
- `adjudication_required`: 1
- `wider_context_required`: 0
- `not_evaluable`: 0
- adjudication 대상: `MORPH-003` / `PRECISE-PNI-004`, locked `pni_status=probable`

PNI-negative nerve control 6건은 자동 제외하지 않는다. locked morphology label은 변경하지 않으며, contour 단계의 추가 판단은 별도 adjudication 표에 기록한다.

## 3. 승인된 운영 결정

다음 운영안은 2026-08-11 사용자 승인에 따라 protocol v1.0으로 고정한다.

| 결정 항목 | 승인된 기본안 | 승인 상태 |
|---|---|---|
| 1차 contour 대상 | `eligible_for_contouring` 13건 전부 | 승인 |
| Probable PNI | `MORPH-003`은 1차 contour와 분리해 adjudication 수행 | 승인 |
| Absent nerve control | 6건 전부 신경 contour 대상에 포함 | 승인 |
| 기본 영상 근거 | H&E level-0 WSI | 승인 |
| IHC 사용 | H&E adjudication 후에도 불명확한 경우에만 별도 기록 후 허용 | 승인 |
| 신경 경계 | 실제 신경 외곽 경계를 필수 polygon으로 기록 | 승인 |
| Perineural-space 경계 | primary 필수 객체로 요구하지 않음 | 승인 |
| 암 경계 | definite PNI에서는 상호작용에 직접 관련된 암 경계를 필수 기록 | 승인 |
| 접촉/포위 경계 | 신경 외곽을 따라 별도 line 객체로 기록 | 승인 |
| Multiple-nerve field | 각 관련 신경을 별도 객체로 그리고 index nerve를 명시 | 승인 |
| 저장 형식 | QuPath 호환 GeoJSON과 CSV manifest | 승인 |
| 좌표 기준 | 원본 H&E WSI level-0 pixel, 좌상단 원점 | 승인 |
| 모델 정보 노출 | score, rank, stratum 및 모델 출력 비노출 유지 | 승인 |

## 4. 대상과 판독 순서

### 4.1 Primary contour set

M5 `contour_eligibility_table.csv`에서 `eligible_for_contouring`으로 잠긴 13건을 대상으로 한다. definite PNI와 absent nerve control을 모두 포함한다.

### 4.2 Adjudication set

`MORPH-003`은 probable PNI이므로 primary 13건과 섞지 않는다.

1. H&E만으로 probable/definite/absent/uncertain/not-evaluable을 재평가한다.
2. H&E만으로 결정할 수 없을 때에만 HMWCK/AMACR 연속절편 참고를 허용한다.
3. IHC 사용 여부, 등록 QC, 판단 근거를 별도 adjudication record에 남긴다.
4. 결과가 definite 또는 absent로 adjudicated되고 contour 가능하면 승인 contour set에 추가한다.
5. locked morphology table은 덮어쓰지 않는다.

### 4.3 Case 표시

- 전문의 화면의 기본 식별자는 `temporary_id`이다.
- candidate ID, subject/slide mapping은 private manifest에만 둔다.
- locked PNI status, locked overall relation 및 contour task는 post-lock 작업 정보로 표시할 수 있다.
- 이전 모델 score, rank, stratum 및 frozen prompt 결과는 표시하지 않는다.
- provisional nerve circle을 사용할 경우 `locator_only=true`인 점선 탐색 표식으로만 표시하고 승인 contour로 저장하지 않는다.

## 5. 좌표계와 영상

- 기준 영상: 원본 PRECISE H&E OME-TIFF
- 좌표계: WSI level-0 pixel 좌표
- 원점: 영상 좌상단 `(0, 0)`
- 축: `x`는 오른쪽, `y`는 아래쪽으로 증가
- annotation 좌표는 level-0에서 저장하며 export 과정에서 임의 resampling하지 않는다.
- 10개 대상 H&E WSI의 OME metadata에서 확인된 pixel size는 모두 다음과 같다.
  - `PhysicalSizeX = 0.243283965700919 µm/pixel`
  - `PhysicalSizeY = 0.243283965700919 µm/pixel`
- 실제 package build 시 WSI별 width, height, MPP 및 SHA256을 private manifest에 다시 기록한다.
- 길이·면적의 µm 변환은 GeoJSON을 변경하지 않고 후속 파생 분석에서 수행한다.

## 6. Annotation 객체 정의

각 객체는 전역적으로 고유한 `annotation_id`를 가져야 한다. 권고 형식은 `{temporary_id}-{object_type}-{NNN}`이다.

### 6.1 필수 객체

1. `nerve_outer_boundary`
   - Geometry: Polygon
   - 실제 평가 대상 신경의 외곽 경계
   - 모든 contour 대상 focus에서 최소 1개 필수
   - fascicle 일부가 아니라 형태계측에 사용할 신경 단면 전체 경계를 우선한다.

2. `tumor_boundary`
   - Geometry: Polygon 또는 MultiPolygon
   - 해당 신경과 직접 상호작용하는 암샘/암세포 집단의 경계
   - definite PNI focus에서 필수
   - absent control에서 관련 암이 시야에 없으면 생략하되 `no_related_tumor_visible=true`를 기록한다.

3. `contact_segment`
   - Geometry: LineString
   - 암과 신경이 직접 접촉한다고 판단한 신경 외곽 구간
   - touching 또는 surrounding/encasement 관계에서 필수
   - contact가 없으면 빈 geometry를 만들지 않고 `not_applicable`로 기록한다.

### 6.2 조건부 객체

- `encasement_arc`: surrounding/encasement에서 신경 외곽을 따라 포위된 구간의 LineString
- `intraneural_region`: 신경 내부 암이 확인될 때 해당 영역의 Polygon
- `longitudinal_tracking_segment`: 신경 장축을 따라가는 암–신경 관계의 LineString
- `branch_point`: 침범된 분지점의 Point
- `additional_nerve_boundary`: multiple-nerve field에서 index nerve 외 관련 신경의 Polygon

현재 locked rereview에서 intraneural, longitudinal-tracking 및 branch-point `yes`는 0건이다. 따라서 해당 객체가 없더라도 PRECISE 전체에 이러한 형태가 없다는 의미가 아니다.

## 7. Index nerve와 multiple-nerve 처리

- candidate locator와 가장 직접적으로 대응하는 신경을 `object_role=index`로 지정한다.
- 같은 300-µm 평가 영역에서 동일 암–신경 상호작용에 참여하거나 multiplicity 판정에 필요한 신경은 각각 별도 polygon으로 그린다.
- 각 신경은 독립 `annotation_id`를 가진다.
- index가 불명확하면 임의 선택하지 않고 `index_nerve_uncertain=true` 및 이유를 기록해 QC로 보낸다.
- provisional circle은 index 탐색 보조일 뿐 실제 신경 경계가 아니다.

## 8. 경계 불명확성과 artifact 처리

- 경계가 H&E에서 보이지 않는 구간을 직선으로 임의 연결하지 않는다.
- 부분 contour만 가능하면 `contour_completeness=partial`과 이유를 기록한다.
- crush, fold, tear, blur, out-of-focus, tissue loss 및 절단면 한계는 각각 명시한다.
- 완전한 신경 외곽이 보이지 않아 형태계측이 불가능하면 `contour_status=not_evaluable`로 둔다.
- `uncertain` 또는 `not_evaluable`을 `no`로 변환하지 않는다.
- 자동/초안 contour가 사용되면 `source=automated_draft`와 전문의의 `approved`, `modified`, `rejected` 상태를 모두 기록한다.

## 9. GeoJSON feature 속성

각 feature의 `properties`에는 최소 다음 항목이 필요하다.

- `annotation_id`
- `temporary_id`
- `candidate_id` — private export에만 포함
- `image_id` — private export에만 포함
- `object_type`
- `object_role`
- `parent_annotation_id` — 해당할 때
- `reviewer_id`
- `review_stage`: `primary_contour`, `adjudication`, `qc_revision`
- `evidence_mode`: `H&E_only`, `H&E_plus_IHC`
- `source`: `pathologist_drawn`, `automated_draft`
- `approval_status`: `draft`, `approved`, `modified`, `rejected`, `not_evaluable`
- `contour_completeness`: `complete`, `partial`, `not_evaluable`
- `revision_number`
- `reviewer_notes`

자유 메모의 공란은 허용하지만 필수 상태값의 공란은 허용하지 않는다.

## 10. Case-level 상태표

GeoJSON과 별도로 `contour_review_status.csv`에 다음을 기록한다.

- temporary/candidate/image ID
- locked PNI status와 overall relation
- M5 contour disposition
- index nerve annotation ID
- required-object completeness
- contour status 및 approval status
- adjudication 필요 여부와 결과
- IHC 사용 여부 및 registration QC
- partial/not-evaluable 이유
- reviewer ID, revision number 및 review timestamp

## 11. 자동 QC

QC는 오류를 자동 수정하지 않고 flag만 생성한다.

### 11.1 Identity와 completeness

- manifest와 annotation의 case ID 일치
- 중복 case ID, annotation ID 및 candidate ID 금지
- 모든 primary 대상 case의 status row 존재
- 승인 case의 필수 객체 존재
- reviewer ID, approval status 및 revision 존재

### 11.2 Geometry

- 빈 geometry 금지
- polygon 최소 3개 고유 vertex 및 닫힌 ring
- polygon self-intersection 금지
- LineString 최소 2개 고유 point
- 모든 좌표가 해당 WSI level-0 범위 안에 존재
- NaN, infinite 및 음수 좌표 금지
- parent-child annotation reference 유효성 확인

### 11.3 병리·논리 일관성

- `contact_segment`는 대응 nerve/tumor boundary가 있어야 한다.
- `encasement_arc`는 surrounding/encasement 또는 별도 adjudication 근거가 있어야 한다.
- intraneural/longitudinal/branch 객체는 해당 stage의 판정과 함께 기록한다.
- absent control의 nerve contour는 허용하며 자동 제외하지 않는다.
- partial 또는 not-evaluable contour에서 확정 직경·접촉 길이 계산을 금지한다.

### 11.4 Sanity flag

- nerve area, perimeter, major/minor diameter 및 aspect ratio를 계산해 극단값을 수동 확인 대상으로 표시한다.
- contact/encasement line과 nerve boundary의 QC 거리 허용치는 `1.0 µm`로 고정하며 자동 snap 또는 수정에는 사용하지 않는다.
- sanity flag는 병리 label이나 contour를 자동 변경하지 않는다.

## 12. 버전과 provenance

다음 파일을 M6 package의 최소 산출물로 권고한다.

- `private_contour_case_manifest.csv`
- `contour_review_template.geojson`
- `contour_review_status_template.csv`
- `CONTOUR_REVIEW_README_KO.md`
- `contour_qc_report.csv`
- `contour_run_config.json`

Run configuration에는 입력 절대경로와 SHA256, WSI hash/크기/MPP, morphology lock hash, protocol version, 도구와 소프트웨어 버전, 실행시각, reviewer/revision provenance 및 self-reference를 제외한 출력 hash를 기록한다.

원본 전문의 판독, locked morphology table, WSI, provisional annotation 및 이전 contour는 덮어쓰지 않는다. 각 수정은 revision이 증가하는 새 산출물로 저장한다.

## 13. 구현 전 기술 게이트

1. [x] 본 protocol의 3절 결정표 승인
2. [x] 대체 annotation 도구로 독립 실행형 `precise_pni_contour_review.html` 확정
3. [ ] 한 개 WSI에서 HTML GeoJSON export와 level-0 좌표 round-trip smoke test
4. [x] synthetic geometry로 validator 단위 테스트
5. [ ] 한 개 eligible focus의 workflow dry run과 좌표 확인
6. [ ] dry run 산출물 폐기 여부 및 정식 revision 시작점 기록
7. [x] 13건 primary package와 1건 adjudication package를 분리 생성

## 14. 완료 기준

- protocol version이 승인 상태로 변경됨
- primary 13건의 전문의 승인 nerve contour가 존재함
- definite PNI의 필수 tumor/contact/encasement 객체가 존재함
- `MORPH-003` adjudication 결과가 별도 기록됨
- geometry와 identity QC가 통과하거나 unresolved flag가 명시됨
- provisional locator와 pathologist-approved contour가 구분됨
- 모든 입력·출력 hash와 revision provenance가 기록됨
- 승인 contour가 없는 focus에서는 확정 형태계측을 수행하지 않음
