# Quantitative validation project instructions

Before creating or moving files, read
`../../infrastructure/docs/repository/PROJECT_STRUCTURE_CODEX.md` and
`../../infrastructure/docs/repository/FILE_GOVERNANCE_CODEX.md` and
`../../infrastructure/docs/repository/FILE_NAMING_CODEX.md` from the repository root. Superpowers
designs/plans for this study belong under this project's `docs/designs/` or `docs/plans/`,
not in a new root folder, and require the structure-Codex metadata header.

- 의료 T1–T4 지표와 모델 성능·QC·감사용 analysis measures를 분리한다.
- H1 recoverability, disease association, H2 functional utilization,
  complementarity와 external transport는 별도 estimand와 gate로 관리한다.
- 확증적으로 허용된 표적은 shared 394.24 µm `tumor_fraction`의 내부 descriptive H1뿐이다.
- FM6에서는 별도 잠금 프로토콜에 따른 TCGA-PRAD whole-tissue 내부 개발 pilot을
  허용한다. 이 pilot은 BCR head 유효성, ISUP 복원성, ISUP-correlated subspace
  sensitivity와 power 입력을 산출할 수 있으나, 독립 tumor-region truth가 없으므로
  tumor-specific H1/H2·외부 이식성·신규 residual marker의 근거로 승격하지 않는다.
- 측정 반복성 없는 confirmatory target 지정, 임상/whole-slide 진단, encoder 우월성,
  scanner/stain robustness 및 독립 metric–endpoint·충분한 subjects/events·외부검증 없는
  H2는 금지한다.
- 두 encoder의 membership, physical boundary, crop hash, truth, folds와 row order를
  1:1로 고정한다.
- 각 FM 마일스톤 종료 시 `docs/research_plan/`의 실행계획서에 수행 내용, 결과,
  발견·배운 점, 한계, 산출물과 다음 진입 조건을 즉시 기록한다.
- `00-project-sequence/README.md`의 단계 상태도 같은 마일스톤 종료 시 함께 갱신한다.
