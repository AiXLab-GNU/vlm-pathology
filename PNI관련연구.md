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
- HMWCK–AMACR 영상은 [data.zip](/home/jinhyun/prj_ws/prj_jin/vlm-pathology/opendataset/PRECISE/data.zip) 안에 있으며 아직 대부분 미추출 상태
- 현재 PNI 후보 120개: [전문의 검토 HTML](/home/jinhyun/prj_ws/prj_jin/vlm-pathology/opendataset/PRECISE/pni_review_120.html)
- TCGA-PRAD: 다운로드된 H&E WSI 300개, 273명
- 이 중 검증된 BCR 자료와 연결되는 환자는 270명, BCR 사건은 57건입니다. [BCR provenance](/home/jinhyun/prj_ws/prj_jin/vlm-pathology/opendataset/TCGA-PRAD-BCR/bcr_label_provenance.csv)

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