맞습니다. 여기서 “조직과 염색”은 전립선 FFPE 조직 블록이나 미염색 연속절편을 확보해 미토콘드리아·신경 표지를 새로 IHC/IF 염색하는 것을 말합니다. 현재 우리가 가진 것은 대부분 이미 스캔된 디지털 영상이므로 새로운 항체 염색을 영상 파일에 추가할 수는 없습니다.

그렇다고 현재 데이터로 아무것도 못 하는 것은 아닙니다. 다만 연구의 결론이 달라집니다.

| 연구 질문 | 현재 데이터로 가능? |
|---|---:|
| PNI를 찾아 전문의 검토를 효율화 | 가능 |
| PNI 주변의 형태학·AMACR 변화 | 탐색적으로 가능 |
| PNI burden과 BCR 연관성 | 가능 |
| PNI와 mitochondrial/OXPHOS RNA signature 연관 | 공개 RNA 추가 시 가능 |
| PNI 암세포의 mitochondrial mass 측정 | 불가능 |
| 신경→암 미토콘드리아 전달 입증 | 불가능 |

현재 보유 자원은 생각보다 괜찮습니다.

- PRECISE: 25명, H&E–HMWCK/AMACR paired WSI 27쌍
- 악성: 18명, 19개 슬라이드
- HMWCK–AMACR 영상은 [data.zip](/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/data/shared/opendataset/PRECISE/data.zip) 안에 있으며 아직 대부분 미추출 상태
- 현재 PNI 후보 120개: [전문의 검토 HTML](/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/data/shared/opendataset/PRECISE/pni_review_120.html)
- TCGA-PRAD: 다운로드된 H&E WSI 300개, 273명
- 이 중 검증된 BCR 자료와 연결되는 환자는 270명, BCR 사건은 57건입니다. [BCR provenance](/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/data/shared/opendataset/TCGA-PRAD-BCR/bcr_label_provenance.csv)

현재 데이터만 사용한다면 다음 연구가 가장 현실적입니다.

1. 전문의가 120개 후보를 `true PNI / nerve adjacency / 비-PNI`로 판독합니다.
2. 악성 19개 HMWCK–AMACR 슬라이드만 선택 추출해 H&E와 정합합니다.
3. 확정 PNI 주변과 같은 환자의 먼 암조직에서 다음을 비교합니다.
   - AMACR 강도
   - 종양세포 밀도와 핵 형태
   - gland architecture
   - 신경과 암의 거리·둘레 포위율
   - CONCH/Virchow embedding 변화
4. TCGA 300개 WSI에 동일한 frozen PNI ranker를 적용하고 상위 후보를 전문의가 확인합니다.
5. 환자별 confirmed PNI burden을 BCR과 연결해 Cox 모델과 ΔC-index/ΔBrier를 분석합니다.
6. 공개 TCGA RNA-seq와 Nature 논문의 GSE 자료를 추가 다운로드해 OXPHOS·TCA·mitochondrial translation signature를 검정합니다. 이것은 새 조직이나 wet lab이 필요한 작업은 아닙니다.

단, AMACR은 지방산 대사와 관련된 전립선암 표지이지만 mitochondrial mass 또는 mitochondrial transfer 표지는 아닙니다. 따라서 현재 데이터에서 허용되는 결론은 다음 정도입니다.

> “전문의가 확인한 전립선 PNI 주변에는 특징적인 형태학적·AMACR-associated metabolic phenotype이 존재하며, PNI burden은 mitochondrial/OXPHOS transcriptional program 및 BCR과 연관될 수 있다.”

반대로 “H&E에서 미토콘드리아 전달을 발견했다” 또는 “PNI 암세포가 신경 미토콘드리아를 획득했다”고 말할 수는 없습니다.

결론적으로, 현재 데이터만으로도 계산병리·가설생성 원저는 가능합니다. 가장 합리적인 순서는 `120개 판독 → paired H&E–AMACR 공간분석 → TCGA PNI/BCR 검증 → 공개 RNA 통합`입니다. 그 결과가 일관되면 새 전립선 조직 염색은 필수 출발점이 아니라, Nature 기전을 직접 검증하기 위한 후속 강화 단계가 됩니다.


------

좋습니다. 제안하신 내용을 연구 문제별로 나누면 다음과 같습니다. 핵심은 PNI를 단순한 양성/음성이 아니라 **어디에, 어떤 형태로, 어느 크기의 신경에서 발생했는가**까지 표현형으로 만드는 것입니다.

## 전체 연구 문제

> 전립선암 PNI의 해부학적 위치, 암–신경 상호작용 형태, 침범된 신경의 크기 및 PNI 부담이 임상병리학적 악성도와 예후를 설명하며, 이러한 특성이 침생검과 전립선전절제술 검체 사이에서 일관되게 관찰되는가?

## 문제 1. 전립선 내부의 PNI 위치

### 1-1. 중심–외곽 분포

확인하려는 질문:

> PNI는 전립선 외곽에 집중되는가? 중심부 PNI는 드물지만 더 특별한 임상적 의미를 갖는가?

구분 후보:

- Peripheral zone
- Transition zone
- Central zone
- Periurethral region
- 전립선 피막 인접부
- 중심부와 외곽부를 거리로 나눈 radial location

여기서 “central PNI”가 무엇을 의미하는지 먼저 고정해야 합니다.

- 해부학적 central zone
- 전립선 중심부
- 요도 주변부

이 세 가지는 서로 다르므로 혼용하면 안 됩니다.

분석 항목:

- 위치별 PNI 발생 빈도
- 중심부 대 외곽부의 PNI 형태 차이
- Gleason grade, 종양량, EPE, 절제면 양성, BCR과의 관계
- 중심부 PNI가 드물지만 고위험 형태인지 여부

## 문제 2. Base–mid–apex 분포

핵심 질문:

> PNI가 방광 쪽 base, 중간부 mid, 배출부 쪽 apex 중 어디에 주로 발생하며, 위치에 따라 임상적 의미가 다른가?

위치 분류:

- Base
- Mid
- Apex
- 필요하면 base–mid, mid–apex 경계
- 좌·우 및 전방·후방 위치

분석 항목:

- Base/mid/apex별 PNI 빈도와 부담
- 위치별 침범 신경의 크기
- 위치별 touch/encasement/intraneural 비율
- Apex PNI와 첨부 절제면 양성의 관계
- Base PNI와 방광경부·정낭침범의 관계
- 외곽부 PNI와 피막외침범의 관계

단, 마지막 세 관계는 사전 가설로 설정한 뒤 검증해야 합니다.

## 문제 3. 침생검의 12-core 위치 패턴

침생검에서는 각 코어의 번호가 해부학적 위치와 연결됩니다.

예시:

- Right/left
- Base/mid/apex
- Medial/lateral
- 경우에 따라 anterior/posterior 또는 표적생검 부위

핵심 질문:

> 어느 생검 위치에서 발견된 PNI가 전립선전절제술의 병리 소견과 예후를 가장 잘 예측하는가?

분석 항목:

- 코어별 PNI 유무와 개수
- PNI 양성 코어 수
- 편측성 대 양측성
- 한 부위 집중형 대 다부위 분산형
- lateral PNI와 medial PNI의 차이
- base·mid·apex PNI의 차이
- systematic core와 MRI-targeted core의 차이
- PNI 위치와 전절제술 EPE 위치의 일치성

중요한 제한은 코어 번호와 실제 채취 위치가 보존되어 있어야 한다는 점입니다. 번호 체계가 기관마다 다를 수 있으므로 원자료의 매핑표가 필요합니다.

## 문제 4. 암–신경 상호작용의 정성적 형태

PNI를 하나의 범주가 아니라 연속적인 침습 과정으로 분류합니다.

### 권장 형태 분류

- **Near**: 암이 신경 가까이에 있지만 직접 접촉하지 않음
- **Touching**: 암이 신경 또는 신경막과 접촉
- **Partial encasement**: 신경 둘레를 부분적으로 둘러쌈
- **Extensive encasement**: 신경 둘레의 상당 부분을 둘러쌈
- **Complete encasement**: 신경을 거의 완전히 둘러쌈
- **Intraneural invasion**: 암이 신경 내부로 침범
- **Longitudinal tracking**: 신경의 장축을 따라 암이 진행

`touching`은 엄격한 의미의 확정 PNI와 구분하는 것이 좋습니다. 따라서 전체 범주명은 우선 **nerve–tumour interaction pattern**으로 두고, 그 안에서 확정 PNI를 별도로 정의할 수 있습니다.

정량화를 위해 포위율도 함께 기록할 수 있습니다.

- 0%
- 1–33%
- 34–66%
- 67–99%
- 100%
- 또는 연속값

## 문제 5. 침범 신경의 크기와 단면 형태

핵심 질문:

> PNI의 임상적 의미가 침범된 신경의 직경과 방향에 따라 달라지는가?

기록할 항목:

- 신경의 최대 직경
- 최소 직경
- 단면적
- 원형도 또는 장단축비
- 횡단면, 사선면, 종단면 여부
- 신경 다발 수
- 단일 신경 대 분지점
- 신경 주위 공간의 확장 여부

직경 등급의 초기 예:

- 소신경: <100 μm
- 중간 신경: 100–300 μm
- 대신경: >300 μm

다만 이 절단값은 문헌 검토와 실제 데이터 분포를 본 뒤 확정하는 것이 좋습니다. 주 분석에서는 직경을 연속변수로 사용하고, 등급은 임상적 해석을 위해 보조적으로 사용하는 편이 안전합니다.

종단면에서는 최대 길이가 신경 직경을 과대평가하므로, 가능하면 **단축 직경 또는 추정 단면적**을 사용해야 합니다.

## 문제 6. PNI의 정량적 부담

정성적 형태와 함께 기존의 정량 지표도 기록합니다.

- 슬라이드당 PNI 병변 수
- 환자당 PNI 병변 수
- PNI 양성 슬라이드 또는 코어 수
- PNI 밀도: 종양 면적당 PNI 수
- 전체 신경 중 암과 접촉한 신경 비율
- PNI 병변의 최대 직경
- 총 암–신경 접촉 길이
- 가장 심한 PNI 형태
- 작은 신경과 큰 신경에서의 PNI 부담

따라서 한 환자의 PNI를 다음처럼 표현할 수 있습니다.

> “PNI 양성”이 아니라 “좌측 apex와 mid-lateral에 집중된 다발성 PNI이며, 중·대형 신경의 extensive encasement와 intraneural invasion을 동반함.”

이것이 연구의 핵심적인 표현형이 됩니다.

## 문제 7. 침생검과 전절제술의 차이

두 검체는 임상적 의미가 다르므로 처음부터 분석을 분리해야 합니다.

### 침생검 연구 질문

> 제한된 조직에서 발견된 PNI의 위치와 형태가 전립선 전체의 공격적인 병리를 예측할 수 있는가?

주요 결과:

- 수술 후 grade upgrading
- upstaging
- EPE
- 정낭침범
- 양성 절제면
- 림프절 전이
- BCR

### 전립선전절제술 연구 질문

> 전립선 전체에서 측정한 PNI의 공간적 분포와 형태가 기존 병리인자 이상의 예후 정보를 제공하는가?

주요 결과:

- 병리학적 병기
- EPE 위치
- 절제면 양성 위치
- 정낭침범
- 종양량
- BCR

따라서 생검과 전절제술을 한 모델에 단순히 섞으면 안 되고, 별도 분석 후 결과를 연결해야 합니다.

## 문제 8. 매칭된 생검–전절제술 분석

가장 가치가 높은 설계입니다.

핵심 질문:

> 생검에서 관찰된 PNI의 위치와 형태가 이후 전절제술에서 확인되는 PNI 및 종양 확산 경로를 얼마나 정확하게 대표하는가?

환자별로 비교할 내용:

- 생검 PNI 유무 ↔ 전절제술 PNI 유무
- 생검 base/mid/apex ↔ 수술 검체의 해당 위치
- 생검 PNI 형태 ↔ 수술 검체의 가장 심한 PNI 형태
- 생검 신경 직경 ↔ 수술 검체 신경 직경
- 생검 PNI 위치 ↔ EPE 및 양성 절제면 위치
- 생검에서 PNI 음성이지만 수술에서는 양성인 경우
- 생검에서 PNI 양성이지만 수술에서는 제한적인 경우

이 분석은 단순한 예후 연구보다 임상적으로 직접적입니다. 생검에서 관찰한 PNI가 수술 범위, 신경보존술 또는 추가 위험평가에 도움이 되는지를 연결할 수 있기 때문입니다.

## 최종적으로 만들 수 있는 통합 PNI 표현형

각 환자를 다음 세 축으로 기술할 수 있습니다.

| 축 | 주요 변수 |
|---|---|
| 해부학적 위치 | central/peripheral, base/mid/apex, 좌우, medial/lateral |
| 침습 형태 | touching, partial/complete encasement, intraneural, longitudinal tracking |
| 부담과 신경 특성 | 병변 수, 밀도, 접촉 길이, 신경 직경, 단면 형태 |

이후 가칭 **PNI topographic–morphologic phenotype**을 정의할 수 있습니다. 그러나 처음부터 하나의 점수로 합치기보다는 각 변수를 독립적으로 분석한 뒤, 재현성 있고 임상적 의미가 있는 요소만 최종 점수에 포함하는 것이 좋습니다.

가장 강한 논문 구조는 다음과 같습니다.

> **생검에서 관찰되는 PNI의 위치·형태·신경 크기 → 전절제술에서의 공간적 일치성과 종양 확산 형태 → 임상 예후**

현재 코호트에서 매칭된 생검–전절제술 검체가 충분하다면, 이 방향은 단순 PNI 정량화보다 훨씬 임상적이고 차별화된 연구가 될 수 있습니다.

--

네, 포함되어 있습니다. 다만 앞서 논의한 **정량화 문제 전체가 여러 항목에 분산**되어 있어 조금 덜 선명하게 보입니다.

현재 제안은 크게 네 축입니다.

1. **PNI 부담 정량화**

   - 환자·슬라이드·생검 코어당 PNI 병변 수
   - PNI 양성 코어 수와 비율
   - 종양 면적당 PNI 밀도
   - 전체 신경 중 침범된 신경의 비율
   - 총 암–신경 접촉 길이
   - 환자 내 최대·평균 신경 포위율
   - multifocality 및 양측성

2. **PNI 형태 정량화**

   - 신경 둘레 포위율(%)
   - 침범 깊이
   - intraneural invasion 유무와 범위
   - longitudinal tracking 길이
   - touching, partial encasement, complete encasement 등의 등급
   - 가장 심한 PNI 형태와 형태별 병변 수

3. **침범 신경 정량화**

   - 최대·최소 직경
   - 단면적
   - 장단축비 및 원형도
   - 소·중·대 신경 등급
   - 신경 크기별 PNI 빈도와 침범 형태

4. **공간적 정량화**

   - peripheral/central 영역별 PNI 수와 밀도
   - base/mid/apex별 PNI 부담
   - 피막·요도·절제면까지의 거리
   - 종양 중심에서 PNI까지의 거리
   - 한 부위 집중형인지 다부위 분산형인지
   - 생검 위치와 전절제술 PNI/EPE 위치의 일치도

따라서 최종 연구는 단순한 정성 분석이 아니라 다음 구조입니다.

> **PNI 양 → PNI 형태 → 신경 크기 → 해부학적 위치 → 병리학적 진행 및 예후**

다만 기존에 말씀드린 정량 점수의 중요한 변수 중 하나인 **PNI focus별 경계와 접촉 길이 측정**을 더 명시적으로 포함해야 합니다. 최종 데이터셋에서는 PNI 병변 하나당 최소한 다음 필드를 기록하는 것이 좋습니다.

```text
patient_id
specimen_type
slide_or_core_id
anatomic_zone
base_mid_apex
laterality
medial_lateral
pni_status
interaction_pattern
encasement_percent
intraneural_invasion
nerve_short_diameter
nerve_cross_section_area
tumour_nerve_contact_length
distance_to_capsule
distance_to_tumour_edge
reviewer
confidence
```

즉, 앞서 제안한 정량화 연구를 버리고 위치 연구를 추가하는 것이 아니라, **기존의 quantitative PNI score를 공간적·형태학적으로 확장하는 연구**입니다.

가칭은 다음처럼 잡는 것이 가장 정확합니다.

> **Spatial and morphometric phenotyping of perineural invasion in prostate cancer**

핵심 산출물은 최종적으로 단순 PNI 양성/음성과 비교되는 다차원 PNI 표현형입니다.

\[
\text{PNI phenotype}
=
\text{burden}
+
\text{topography}
+
\text{interaction morphology}
+
\text{nerve calibre}
\]

이 다차원 표현형이 기존 병리인자 및 단순 PNI 유무보다 전절제술의 불량 병리 소견과 BCR을 더 잘 설명하는지가 최종 검증 문제가 됩니다.

--

네. 실제 파일을 기준으로 보면, **현재 데이터로 풀 수 있는 문제와 해부학적 메타데이터가 없어 풀 수 없는 문제가 명확히 갈립니다.**

## 결론

현재 가능한 핵심 연구는 다음입니다.

> **PNI의 양·형태·신경 직경이 BCR 및 분자 아형과 관련되는가?**

반면 지금 데이터만으로는 다음을 신뢰성 있게 답할 수 없습니다.

> **PNI가 전립선의 peripheral/central zone 또는 base/mid/apex 중 어디에 발생하는가?**
> **생검 PNI 위치가 같은 환자의 전절제술 PNI/EPE 위치와 일치하는가?**

두 문제에는 슬라이드 좌표가 아니라 **검체 채취 위치와 방향 정보**가 필요한데, 현재 로컬 데이터에는 그 연결정보가 없습니다.

---

## 코호트별 가용성

| 코호트 | 검체 및 규모 | PNI 현황 | 임상·분자 정보 | 위치 정보 |
|---|---|---|---|---|
| PRECISE | 25명, 37개 침생검 코어, 27개 H&E WSI | 전문의 확정 7 PNI/7명 | PSA, MRI, Gleason/ISUP, HMWCK-AMACR | 코어의 base/apex, 좌우, zone 없음 |
| Song datasets-02 | WSI 10장, XML 6장 | 기존 마커 17개, 일부 PNI 확인 | 임상·예후 자료 없음 | 검체 종류·해부학적 방향 불명 |
| TCGA-PRAD | 로컬 300 WSI, 273명 | PNI 판독 없음 | 270명 BCR, 57건 event; 병기·분자 자료 | 전절제술 FFPE이지만 선택된 대표 슬라이드이며 base/apex·zone 정보 없음 |
| PCa_Bx_3Dpathology | 50명, 120개 침생검 표본 | PNI 판독 없음 | 수술 후 BCR 정보 | A–F 표본명은 있으나 해부학적 대응표 없음 |
| NADT-Prostate | 39명, 490개 biopsy block/H&E | PNI 판독 없음 | ERG, PTEN, AR, Ki67 등 연속절편·분자자료 | `Bx1A` 등의 번호만 있고 채취 위치 대응표 없음 |

PRECISE가 core needle biopsy 자료라는 점은 원 데이터 설명에도 명시되어 있습니다. [PRECISE 데이터 설명](https://zenodo.org/records/20721779)
TCGA-PRAD의 DX 슬라이드는 전립선전절제술 FFPE 검체이지만 대개 환자당 대표 슬라이드 한 장이며, 전체 전립선 whole-mount가 아닙니다. [TCGA-PRAD 검체 설명](https://pmc.ncbi.nlm.nih.gov/articles/PMC10985477/)

---

# 1. 현재 데이터로 바로 가능한 문제

## 1-1. 확정 PNI의 정성적 형태 분석

PRECISE에서 다음을 분석할 수 있습니다.

- touching
- surrounding/encasement
- intraneural 여부 재판독
- 신경을 따라가는 longitudinal tracking
- 단일 신경과 신경 분지점 침범
- PNI 주변과 원거리 암의 형태 차이

현재 최종 판독은 120개 후보 중:

- nerve present: 14개
- 확정 PNI: 7개
- touching: 4개
- surrounding: 3개

입니다. 최종 판독 원자료는 [precise_pni_review (1).csv](</home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/data/shared/opendataset/PRECISE/precise_pni_review (1).csv>)에 있습니다.

단, 7개는 **방법 개발용 pilot**이지 환자 집단의 대표적인 형태 분포를 추정하기에는 작습니다.

## 1-2. 침범 신경의 직경과 단면 형태

고해상도와 MPP 정보가 있으므로 다음 측정은 가능합니다.

- 신경의 단축 직경
- 장축 직경
- 단면적
- 장단축비
- 횡단·사선·종단면
- 신경 포위율
- 암–신경 접촉 길이

다만 현재 PRECISE 신경 경계는 병리의가 그린 실제 윤곽이 아니라 임시 원형 표시입니다. [nerve_annotations_v1.csv](/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/data/shared/opendataset/PRECISE/pni_spatial_pilot/nerve_annotations_v1.csv)

따라서 정확한 직경·접촉 길이 분석에는 전문의가 신경 경계를 승인하거나 수정해야 합니다.

## 1-3. 동일 슬라이드 내 PNI 근접 암과 원거리 암 비교

현재도 가능합니다.

- 신경 접촉부
- 신경에서 0–25 μm
- 25–100 μm
- 100–500 μm
- 동일 슬라이드 원거리 암

을 비교할 수 있습니다.

PRECISE에는 종양 마스크와 짝지어진 H&E–HMWCK/AMACR가 있어, 다음을 탐색할 수 있습니다.

- 암샘 구조
- 세포·핵 밀도
- AMACR/HMWCK 표현
- CONCH/Virchow 표현형
- PNI 주변의 공간적 gradient

현재 pilot은 7명으로 신뢰구간이 넓고 일관된 AMACR 차이를 보이지 않았습니다. [RESULTS_REPORT.md](/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/data/shared/opendataset/PRECISE/pni_spatial_pilot/RESULTS_REPORT.md)

## 1-4. AI 후보 검색 및 판독 보조

이미 가능한 상태입니다.

- WSI에서 PNI 후보 자동 검색
- 전문의에게 상위 후보 제시
- touch/cover/intraneural 분류 보조
- 신경 경계와 암–신경 접촉 영역 초안 생성

다만 현재 모델은 확정 진단기가 아니라 **후보 선별기**로 사용해야 합니다.

---

# 2. 추가 전문의 판독을 하면 가능한 문제

## 2-1. PNI 정량 부담과 BCR의 관계

TCGA-PRAD에서 다음 질문을 풀 수 있습니다.

> PNI 병변 수, 밀도, 포위율 및 신경 직경이 단순 PNI 유무보다 BCR을 더 잘 설명하는가?

현재 로컬 자료:

- 300 WSI
- 273명
- BCR 분석 가능 270명
- BCR event 57건

필요한 추가 작업:

- TCGA WSI의 PNI 후보 생성
- 전문의 PNI 확인
- 확정 병변 경계 표시
- 환자별 PNI burden 계산

가능한 변수:

- 슬라이드당 PNI 수
- 종양 면적당 PNI 밀도
- 최대/평균 포위율
- 최대 신경 직경
- intraneural invasion
- 환자별 가장 심한 interaction pattern
- 총 암–신경 접촉 길이

이것이 현재 데이터로 가능한 가장 직접적인 임상 연구입니다.

단, TCGA의 슬라이드는 전립선 전체가 아니라 대표 절편이므로 결과는 반드시 **slide-level observed PNI burden**으로 표현해야 합니다. “환자 전체 전립선의 총 PNI 부담”이라고 하면 안 됩니다.

## 2-2. PNI 형태와 분자 아형의 관계

TCGA에는 다음 정보가 있습니다.

- ERG
- PTEN
- SPOP
- AR
- TP53 및 기타 분자변수
- 병기와 Gleason
- BCR

따라서 다음을 검정할 수 있습니다.

> PTEN loss 또는 ERG/SPOP 아형에 따라 PNI의 수, 신경 크기 및 침범 형태가 다른가?

현재 57개 BCR event로는 다수의 상호작용을 동시에 검정하기 어렵습니다. 따라서 PTEN/ERG를 주 가설로 하고 SPOP/AR는 탐색 분석으로 두는 것이 적절합니다.

## 2-3. 침생검 PNI와 BCR

PCa_Bx_3Dpathology에는 다음이 있습니다.

- 50명
- 120개 biopsy 표본
- 수술 후 BCR 자료
- cancer-enriched coordinates

따라서 PNI를 새로 판독하면 다음은 가능합니다.

> 침생검에서 측정한 PNI 부담·형태·신경 직경이 수술 후 BCR과 관련되는가?

다만 코호트가 50명으로 작고, Excel의 recurrence code 설명이 문구상 다소 모호하므로 endpoint 정의를 원 출처에서 다시 확인해야 합니다. [BCR 메타데이터](/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/data/shared/opendataset/PCa_Bx_3Dpathology/Biopsy-list-with-BCR-outcomes-and-cancer-enriched-coordinates.xlsx)

## 2-4. 생검 PNI와 PTEN/ERG/AR 표현형

NADT-Prostate는 39명의 490개 biopsy block에 대해 H&E와 여러 연속절편이 있습니다.

- PTEN
- ERG
- AR
- Ki67
- PSA
- PIN4
- 일부 RNA/DNA 정보

PNI를 판독하면 다음은 가능합니다.

> PNI가 있는 생검 조직과 없는 조직 사이에 PTEN/ERG/AR 표현형 차이가 있는가?

이 코호트는 분자·IHC 연구에는 유용하지만 BCR이나 장기 예후가 없어 **예후 검증 코호트로는 사용할 수 없습니다.**

---

# 3. 현재 데이터로는 풀 수 없는 문제

## 3-1. Peripheral zone 대 central zone PNI

현재 모든 코호트에서 PNI의 WSI 좌표는 알 수 있지만 다음이 없습니다.

- peripheral/transition/central zone
- 요도 위치
- 피막 위치의 해부학적 확인
- 전립선 전체 윤곽과 orientation

따라서 슬라이드 가장자리의 PNI를 “peripheral-zone PNI”라고 부를 수 없습니다.

가능한 것은:

- 조직 절편 가장자리까지의 거리
- 종양 경계까지의 거리
- 슬라이드 내 중심/외곽 위치

뿐입니다. 이것은 전립선의 해부학적 central/peripheral zone과 다릅니다.

## 3-2. Base–mid–apex PNI

PRECISE, TCGA, PCa_Bx, NADT 모두 로컬 메타데이터에 base/mid/apex가 없습니다.

특히 침생검의 `Bx1A`, `A–F` 같은 표본명은 번호일 뿐, 현재 파일만으로는 다음처럼 해석할 수 없습니다.

- right apex
- left base
- medial/lateral
- anterior/posterior

원기관의 core-number mapping table이 확보되면 가능해질 수 있지만, 현재 상태에서는 불가능합니다.

## 3-3. 12-core 위치별 PNI 발생률

PRECISE에는 37개 core가 있지만 표준 12-core 위치정보가 없습니다. PCa_Bx에는 환자당 A–F 중 일부 biopsy가 있지만 12-core 위치 대응표가 없습니다.

따라서 다음 질문은 현재 답할 수 없습니다.

> Right lateral base의 PNI가 left medial apex보다 흔한가?

이 분석에는 각 코어별 해부학적 채취 위치표가 필요합니다.

## 3-4. 매칭된 침생검–전절제술 비교

현재 자료에는 동일 환자의 다음 쌍이 없습니다.

```text
수술 전 침생검 WSI
        ↕ 같은 환자
전립선전절제술 WSI
```

PCa_Bx에는 생검과 수술 후 BCR은 있지만 수술 검체 WSI가 없습니다. TCGA에는 전절제술 WSI가 있지만 대응 침생검이 없습니다. 공개 코호트 간 환자도 서로 다릅니다.

따라서 생검 PNI 위치와 수술 검체 PNI/EPE 위치의 일치도는 현재 분석할 수 없습니다.

## 3-5. 전립선 전체의 PNI 총량

TCGA는 환자당 대표 절편이 대부분 한 장이고, PRECISE와 NADT는 선택된 생검입니다. 따라서 미관찰 조직에 존재하는 PNI를 알 수 없습니다.

측정 가능한 것은:

> 분석된 슬라이드 또는 코어에서 관찰된 PNI 부담

이지,

> 전립선 전체의 실제 PNI 총량

이 아닙니다.

## 3-6. 신경에서 암으로의 미토콘드리아 전달

H&E, HMWCK/AMACR, 기존 TCGA bulk RNA만으로는 다음을 입증할 수 없습니다.

- 미토콘드리아의 신경세포 기원
- 신경→암 미토콘드리아 전달
- 실제 OXPHOS 활성 증가
- 인과관계

가능한 표현은 “PNI-associated metabolic phenotype”까지이며, 전달 입증에는 mitochondria-specific staining, spatial molecular assay 또는 lineage tracing이 필요합니다.

---

# 가장 현실적인 연구 구성

현재 자료만으로는 두 개의 독립된 축으로 설계하는 것이 가장 좋습니다.

### 현재 코호트로 수행

> **PNI burden + interaction pattern + nerve calibre가 분자 아형 및 BCR과 관련되는가?**

- PRECISE: annotation 방법 개발
- TCGA: 전절제술 기반 임상·분자·BCR 분석
- PCa_Bx: 독립적인 침생검–BCR 탐색 분석
- NADT: 침생검–IHC 분자 표현형 분석

### 별도 코호트가 필요한 연구

> **PNI의 peripheral/central 및 base/mid/apex 분포와 생검–전절제술 공간적 일치성**

필수 추가자료:

- 각 생검 코어의 12-core 위치표
- 전절제술 절편의 base/mid/apex·좌우·zone 정보
- 동일 환자 biopsy–prostatectomy 식별자
- EPE와 절제면 양성의 위치
- 전체 또는 체계적으로 표본화된 전립선 절편

따라서 **정량·정성 PNI 연구는 현재 자료로 진행할 수 있지만, 해부학적 위치 연구와 매칭 연구는 새로운 임상 코호트 또는 누락된 위치 매핑 자료가 있어야 가능합니다.** Song 데이터의 검체 종류와 환자별 위치·수술정보가 별도로 존재한다면, 그 자료가 현재 가장 중요한 잠금 해제 요소입니다.

네. 추가 공개 코호트를 조사한 결과, 한 코호트에서 모든 문제를 해결하기는 어렵지만 다음처럼 역할을 나누면 상당 부분을 풀 수 있습니다.

### 우선순위가 높은 추가 코호트

| 코호트 | 규모·검체 | 제공되는 정보 | 해결 가능한 문제 | 주요 한계 |
|---|---:|---|---|---|
| **PAIP 2021** | 대장·전립선·췌담도 240 WSI. 전립선 학습군 50 WSI | 전문의가 표시한 신경–암 접촉/PNI 경계 | PNI 검출기 학습, touching·encasement·intraneural 후보 추출, 경계 정확도 향상 | 절제 검체, 예후·해부학적 위치 없음. 등록·DUA 필요 |
| **PROSTATE-FUSED-MRI-PATHOLOGY** | MRI 28명, 고해상도 whole-mount 병리 16명·114 TIFF/XML | MRI, 종양 경계, apex에서 base 방향으로 순서가 보존된 절편 | **apex–mid–base, 좌우·전후, peripheral zone–central gland에 따른 PNI 분포** | PNI 라벨은 새로 만들어야 하며 병리 환자 수는 16명 |
| **PAR** | 185명, 유리 슬라이드 339개를 3종 스캐너로 촬영한 1,017 WSI | 좌우 전립선 침생검, 3명 전문의 Gleason/ISUP | 침생검에서 PNI 외부검증, 좌우 차이, 스캐너 일반화 | 한쪽 6개 코어를 함께 올린 경우가 많아 base/mid/apex 복원 불가 |
| **SPROB20** | 460명, 2,611 biopsy scans | 임상정보, 병리정보, 치료결정 | 대규모 침생검 PNI 정량화 및 임상 연관성 검증 | 통제 접근. 코어별 위치정보 포함 여부는 자료 접근 후 확인 필요 |
| **PANDA** | 10,616 biopsy WSI | Gleason/ISUP, 조직 마스크 일부 | 대규모 외부검증 및 AI 후보 선별 | PNI가 독립 클래스로 표시되어 있지 않음 |
| **PROSTATE-MRI** | 26명, MRI–whole-mount 병리 대응 | 수술 검체와 MRI 위치 대응 | 위치 분석의 보조 검증 | 병리가 26개 JPG 수준이라 작은 신경 및 PNI 형태 측정에는 해상도 부족 |
| **AGGC22** | 전립선절제술 144 WSI, 침생검 53 WSI | Gleason pattern 픽셀 라벨 | biopsy–prostatectomy 간 모델 일반화 | 동일 환자 매칭이 아니며 PNI·위치·예후 라벨 없음 |

PAIP 2021은 현재 공개자료 중 PNI 검출기의 출발점으로 가장 직접적입니다. 다만 라벨은 주로 신경–암 접촉 경계이므로, 우리가 원하는 `touching / encasement / intraneural`, 신경 직경, 침범 비율은 추가 판독해야 합니다. [PAIP 2021 공식 사이트](https://paip2021.grand-challenge.org/Home/), [데이터 설명서](https://zenodo.org/records/4575424/files/PAIP2021%20PerineuralInvasioninMultipleOrganCancer%28Colon%2CProstate%2CandPancreatobiliarytract%29_02-10-2021_12-25-47.pdf)

PROSTATE-FUSED가 특히 중요합니다. 첫 절편이 apex에서 약 0.6 mm 떨어진 지점이고, 이후 절편이 base 방향으로 연속되며 좌우·전후 사분면도 보존됩니다. 따라서 현재 제기된 “PNI가 외곽에 많은가?”, “central PNI는 드문가?”, “base와 apex에서 빈도가 다른가?”를 직접 탐색할 수 있는 가장 좋은 공개 자료입니다. [TCIA 컬렉션](https://www.cancerimagingarchive.net/collection/prostate-fused-mri-pathology/), [위치 대응 방법 논문](https://pubmed.ncbi.nlm.nih.gov/24700476/)

PAR는 표준적으로 좌우 각각 6개 코어를 채취하지만, 같은 쪽 코어를 1–2장의 유리 슬라이드에 모아 놓았기 때문에 좌우 분석은 가능해도 개별 base/mid/apex 번호 복원은 어렵습니다. 대신 세 스캐너에서 같은 슬라이드를 촬영하여 모델의 장비 독립성을 검증하기 좋습니다. [PAR 데이터 논문](https://www.nature.com/articles/s41597-026-07798-9)

SPROB20은 규모가 크고 임상·치료결정 정보가 있다는 장점이 있지만 통제 접근 자료입니다. 공개 설명만으로는 12-core의 구체적인 해부학적 번호가 포함됐는지 확정할 수 없습니다. [SPROB20 데이터 페이지](https://datahub.aida.scilifelab.se/10.23698/aida/sprob20)

PANDA-PLUS 문서도 PNI가 별도 주석 클래스로 제공되지 않는다고 명시합니다. 따라서 PANDA는 전문의 라벨이 있는 평가군으로 사용하기보다는 AI가 후보를 뽑은 뒤 일부를 새로 판독하는 용도가 적절합니다. [PANDA-PLUS 설명](https://pmc.ncbi.nlm.nih.gov/articles/PMC12858358/)

### 분자·기전 연구를 보강하는 공개자료

영상 이외에도 다음 자료를 결합할 수 있습니다.

- **GSE7055**: 미치료 전립선절제술 57례로, PNI 50례와 non-PNI 7례의 mRNA/miRNA 자료입니다. 영상에서 얻은 PNI 형태 점수와 직접 매칭되지는 않지만 PNI 관련 분자 signature의 독립 확인에 사용할 수 있습니다. [연구 논문](https://pmc.ncbi.nlm.nih.gov/articles/PMC2597330/), [NCBI 자료](https://www.ncbi.nlm.nih.gov/bioproject/98497)

- **PRJCA013564 / OMIX002477**: PNI 전립선암 3명의 단일세포 RNA-seq 자료입니다. 신경 주변 암세포·면역세포 상태를 탐색할 수 있지만 환자가 3명이고 non-PNI 대조군이 없습니다. [연구 논문](https://pmc.ncbi.nlm.nih.gov/articles/PMC9875799/), [원자료](https://ngdc.cncb.ac.cn/omix/release/OMIX002477)

- **GenomeDK GDK000023**: PNI 전립선절제술 1례의 Visium HD 공간전사체 자료입니다. 기전적 사례 분석에는 유용하지만 통제 접근이고 한 환자뿐입니다. [GenomeDK 자료](https://genome.au.dk/library/GDK000023/)

### 가장 현실적인 다중 코호트 설계

한 코호트에 모든 것을 요구하는 대신 다음과 같이 분리하는 것이 좋습니다.

1. **PNI 검출과 정성 형태학**
   - PAIP 2021로 모델을 학습
   - PRECISE의 Song 전문의 라벨로 보정
   - PAR·PANDA 일부에서 외부검증
   - 산출값: PNI 개수, 총 침범 길이, 신경 직경, 종양 피복률, touching/encasement/intraneural

2. **PNI의 해부학적 위치**
   - PROSTATE-FUSED에서 모든 절편을 apex–mid–base로 배정
   - MRI를 이용해 peripheral zone과 central gland를 구분
   - 환자 내부에서 PNI 밀도를 비교
   - 단, 16명이므로 확증 연구보다는 해부학적 파일럿으로 규정

3. **3차원 형태와 예후**
   - 현재 보유한 PCa_Bx_3Dpathology로 신경을 따라 이어지는 침범 길이와 3D 형태 측정
   - TCGA-PRAD에서 PNI 정량점수와 BCR의 독립·증분적 예후가치 검증
   - GSE7055와 단일세포 자료로 분자적 해석 보강

4. **침생검–전절제술 대응**
   - 현재 확인된 공개자료에는 `치료 전 12-core WSI + 동일 환자의 untreated whole-mount RP WSI + 코어 위치 + 예후`가 모두 갖춰진 코호트가 없습니다.
   - NADT-Prostate가 가장 가깝지만 공개된 영상은 주로 biopsy이고, 수술 전 치료의 영향도 있어 자연경과 연구와는 다릅니다.
   - 이 문제는 NADT 연구진에 추가 자료를 요청하거나 기관 코호트를 확보해야 합니다.

결론적으로 가장 먼저 추가할 자료는 **PAIP 2021과 PROSTATE-FUSED**입니다. 전자는 PNI 검출 정확도와 형태 분류를, 후자는 지금 새롭게 제기된 base–apex 및 외곽–중심 위치 문제를 해결합니다. 여기에 PAR를 외부검증군으로 붙이면, 현재 자료만 사용한 단순 PNI 개수 연구보다 훨씬 강한 다중 코호트 연구가 됩니다.

정확히는 다음과 같습니다.

- **PAIP 2021 전체:** 240장
- **전립선 데이터 전체:** 80장
  - Training: 50장
  - Validation: 10장
  - Test: 20장
- **전문의 XML 정답이 공개되는 전립선 데이터:** **Training 50장**

따라서 우리가 직접 지도학습과 PNI 병변 분석에 사용할 수 있는 규모를 말할 때는 **전립선 50장**이 맞습니다. 나머지 전립선 30장은 WSI는 있지만 정답 annotation이 공개되지 않아 독립 평가용에 가깝습니다.

또한 50장은 작은 biopsy core 50개가 아니라 **전립선절제술 검체의 대표 whole-slide image 50장**, 대략 50증례입니다. 한 장 안에 여러 신경과 여러 PNI 병변이 있을 수 있으므로 병변 단위 표본 수는 50보다 훨씬 많을 가능성이 있지만, 정확한 PNI 병변 수는 XML을 확보한 뒤 계산해야 합니다.
