# Quantitative Foundation-Model Validation

## 핵심 목표

동일 환자·동일 조직에서 독립적으로 측정한 **복수의 임상·병리 정량지표**가
CONCH와 Virchow의 frozen representation과 locked 질병예측 판단을 얼마나 완전하게
설명하는지 규명한다. 이어서 알려진 지표와 기술적 교란을 제거한 뒤에도 두
모델과 독립 외부 코호트에서 반복되는 residual morphology를 병리의가 감사할 수
있는 명시적 정량지표로 전환하고, 독립 assay·omics·임상 outcome으로 신규 마커
후보의 타당성을 검증한다.

이를 다음 증거 사슬로 구분한다.

1. **H1—복원성:** 사람의 정량지표가 각 frozen embedding에서 복원되는가?
2. **포함관계·완전성:** 복수 지표의 조합이 AI 표현과 판단을 얼마나 설명하는가?
3. **H2—기능적 활용:** 지표 관련 표현을 선택적으로 제거하면 locked disease head가
   matched control보다 더 저하되는가?
4. **Residual 발견:** 설명되지 않은 신호 중 모델·기관을 넘어 반복되는 병리 형태가 있는가?
5. **마커 전환:** 반복 형태를 측정 가능한 지표로 정의하고 외부·생물학적으로 검증할 수 있는가?

CONCH와 Virchow는 우열을 가리기 위한 대상이 아니라, 사전학습 방식이 다른 두 독립
측정기로 사용한다. 공통 신호와 모델 특이·기술적 신호를 분리하는 것이 목적이다.

## 현재 운영 범위

P0와 FM1–FM5는 완료되었다. 현재 허용된 결론은 25명·1,218 paired tile에서
shared 394.24 µm `tumor_fraction`이 두 frozen representation에서 복원된다는 내부
descriptive H1 근거뿐이다. FM6 H2는 독립 metric–endpoint 쌍, 충분한 환자·사건,
치료 공변량과 외부 코호트가 확보될 때까지 잠금 상태다. 위 핵심 목표의 등록은
이 잠금을 해제하거나 임상·외부·신규 biomarker 주장을 승인하지 않는다.

P0부터 FM/H2까지의 진행 순서는 [`00-project-sequence/`](00-project-sequence/)에서
번호순으로 확인한다.

- 현재 상태: [실행 추적표](docs/research_plan/01-01-01-foundation-model-validation-execution-tracker-ko.md)
- 연구계획: [canonical plan](docs/research_plan/01-quantitative-ai-validation-disease-diagnosis-plan-ko.md)
- 마일스톤: [canonical milestones](docs/research_plan/01-01-foundation-model-validation-milestones-ko.md)
- 관련연구: [survey index](docs/surveys/README.md)
- 결과: [report index](reports/README.md)
- 논문: [paper entry point](paper/README.md)
