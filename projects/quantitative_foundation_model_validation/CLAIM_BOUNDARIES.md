# Claim boundaries

장기 핵심 목표는 복수의 독립 정량지표가 CONCH와 Virchow의 표현·locked
질병예측 판단을 얼마나 설명하는지 규명하고, 알려진 지표와 기술적 교란을
제거한 뒤 두 모델·외부 코호트에서 반복되는 residual morphology를 검증 가능한
신규 정량 마커 후보로 전환하는 것이다.

확증 범위의 기존 결과는 단일 T2 tumor-fraction 표적의 내부 descriptive recoverability
근거다. 여기에 TCGA-PRAD 392명/80 BCR events의 whole-tissue 내부 개발 pilot이
추가됐다. 이 pilot에서는 CONCH와 Virchow 모두에서 ISUP OOF recoverability, 유효한
내부 BCR head와 제거분산-matched control 대비 ISUP-correlated fixed-head sensitivity가
관찰됐다. 그러나 독립 tumor-region truth가 없으므로 이는
`internal whole-tissue R/A/U exploratory evidence`이며 tumor-specific H1/H2가 아니다.
정량지표를 복원할 수 있다는 사실은 모델이 그 지표를 질병예측에 사용한다는 뜻이
아니다. H2, 임상적 유용성, 외부 일반화와 encoder 우월성은 각 추가 gate 전까지
주장하지 않는다. Residual은 병리의 블라인드 검토, shortcut 감사, 반복성, 독립
assay·outcome·외부 코호트 검증 전에는 신규 마커로 주장하지 않는다.

이번 pilot에서 ISUP 단독 BCR C-index는 0.696이었고 제한적인 ISUP+AI 대 ISUP-only
비교의 paired interval은 두 encoder 모두 0을 포함했다. 이는 이 내부 분석에서 증분이
확립되지 않았다는 뜻일 뿐, 임상 증분이 없음을 충분히 평가한 설계가 아니다. 따라서
내부 기능 민감도는 AI의 임상적 증분가치 또는 신뢰성 향상과 동의어가 아니다.
AI risk와 tissue fraction의 상관도 0.324–0.341이므로 독립 tumor-region·기술 교란 감사
전에는 설명되지 않은 risk를 신규 생물학으로 해석하지 않는다. 2026-08-20 site-heldout
T는 Virchow만 통과했고, 508명/87 events LEOPARD locked reanalysis에서는 두 encoder 모두
외부 gate를 통과하지 못했다. CHIMERA 95명/27 events에서는 두 encoder의 ISUP 방향이
복원되고 targeted erasure가 양성이었지만, prespecified head·control·multiplicity gate를
모두 통과한 것은 Virchow뿐이었다. 따라서 External T는
`ENCODER_SPECIFIC_WHOLE_TISSUE_TRANSPORT`이며, 전체 encoder family의 universal transport와
strong H2는 `PROHIBITED`다.

2026-08-16 독립 detector gate에서는 TCGA outcome·ISUP·CONCH·Virchow를 사용하지 않은
ImageNet ResNet18을 SICAPv2 pixel mask로 개발했다. 공식 test AUROC 0.920과 sensitivity
0.928에도 specificity 0.751로 선고정 0.80 기준을 통과하지 못했다. PANDA provider
scanner-proxy 감사도 Karolinska는 통과했으나 Radboud sensitivity 0.299로 실패했다.
따라서 threshold를 사후 변경하지 않았고 TCGA tumor filtering을 실행하지 않았다. 이
실패는 whole-tissue pilot의 기존 내부 결과를 무효화하지 않지만 tumor-specific 또는
detector-restricted claim으로의 승격을 명시적으로 차단한다.

같은 날 시행한 train-only 3-fold remediation에서는 HED stain perturbation과 scale
augmentation 후보가 선택됐고 OOF AUROC/sensitivity/specificity는 0.949/0.887/0.887이었다.
이미 열었던 SICAP test의 비선택적 재평가에서는 specificity가 0.810으로 개선되어 수치상
내부 기준을 충족했지만 이는 새 독립 test가 아니다. 사전에 잠근 별도 PANDA 100-slide
holdout에서는 Karolinska/Radboud sensitivity가 0.563/0.679로 0.75 기준에 미달했다.
따라서 재튜닝이 SICAP specificity 문제를 완화했다는 개발 결론만 허용하며, cross-domain
detector gate와 TCGA 적용은 계속 실패/미실행으로 둔다.

PBV의 해시-잠금 근거를 승계한 alignment 원고에서는 기존 cohort에서 지표의
복원 정확성·외부 재현성이 사람과 AI 사이의 공통 해석 좌표 가능성을 제시한다고
요약할 수 있다. 여기에 FM6 whole-tissue ISUP fixed-head erasure를 두 encoder에서 반복한
결과와 site-heldout encoder-specific evidence를 포함하고, LEOPARD external transport
실패/불확정 및 Virchow-only CHIMERA 통과 결과를 함께 보고한다. SICAP specificity
0.810은 secondary internal evidence로 수용하지만 PANDA 두 provider의 sensitivity 실패를
독립 domain limitation으로 병기한다. 이 derivative manuscript는 Virchow--CHIMERA에 한해
qualified external whole-tissue functional transport를 주장하지만 strong H2 ceiling은 높이지
않는다. Indispensable use, encoder superiority, universal transport, tumor-specific mechanism 또는
clinical increment를 주장하지 않는다. Residual/unknown AI feature의 신규
정량 marker화는 현재 원고에서 제외하고 별도 후속 논문으로 다룬다.
