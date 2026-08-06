# VLM 환각 벤치마크 — 새 세션 실행용 프롬프트

> **✅ 완료 (2026-07-29).** 아래 프롬프트대로 4개 모델(GPT-5.5로 전환, Claude,
> Quilt-LLaVA, LLaVA-Med) x 4개 과제 벤치마크를 SICAPv2 Test-split 75패치로 실행
> 완료했다. 결과·표는 `docs/01_motivation.md`와 `report.tex` §9.6("정식 VLM 환각
> 벤치마크") 참고, 재현 스크립트는 `models/pilot_vlm_benchmark_{gpt5,claude,quilt,
> llavamed}.py`, 프로젝트 메모리 `project-vlm-pathology-status`에도 전체 요약 기록.
> 이 파일 자체는 원본 실행 계획으로 그대로 보존.

이 파일 전체(또는 아래 "프롬프트 본문" 섹션)를 새 Claude Code 세션의 첫 메시지로
붙여넣어 실행하세요. 이 프로젝트(vlm-pathology)의 자동 메모리(`project-vlm-pathology-status`,
`feedback-vlm-excluded`)가 자동으로 로드되므로 프로젝트 배경은 어느 정도 이미 갖춰져
있지만, 이 벤치마크의 구체적 설계는 메모리에 없으므로 아래 내용이 필요합니다.

---

## 프롬프트 본문 (여기부터 복사)

전립선암 병리 논문(vlm-pathology 프로젝트)의 서론 motivation을 위한 **VLM 환각 벤치마크**를
실행해줘. 먼저 메모리(`project-vlm-pathology-status`, `feedback-vlm-excluded`)를 읽어서
전체 맥락(마커 풀 접근법, 왜 VLM 직접 판단을 배제했는지)을 파악해줘.

### 배경

이 프로젝트는 "VLM이 병리 이미지를 직접 보고 판단하면 환각한다"는 것을 논문 motivation의
핵심 축으로 쓰려고 하는데, 지금까지 근거가 **Quilt-LLaVA 하나로 시도한 내부 파일럿
6개**(비공식, 정량화 안 됨)뿐이었다. 이걸 여러 모델·정량 지표로 정식화하는 게 이 작업의
목표다.

이미 확인된 지원 문헌(인용 예정, 그대로 믿지 말고 필요시 재확인):
- GPT-4V의 병리(pathology) 영역 환각률이 **46.8%**로 보고됨 (arXiv 2406.10185,
  "Detecting and Evaluating Medical Hallucinations in Large Vision Language Models")
- 그런데 **in-context learning(프롬프트에 예시 몇 개 포함)을 쓰면 GPT-4V가 병리 조직
  분류에서 전용 컴퓨터 비전 모델과 비슷한 수준까지 개선**된다는 반례도 있음(PMC11582649,
  "In-context learning enables multimodal LLMs to classify cancer pathology images")

→ 그래서 "VLM은 원천적으로 안 된다"가 아니라 **"단순 프롬프팅(zero-shot)으로는
실패하고, in-context 예시를 줘도 실패하는지/개선되는지"까지 정직하게 확인**하는 게
이번 벤치마크의 핵심이다.

### 테스트할 모델 (4개, "중간 범위"로 이미 합의됨)

1. **GPT-4V/GPT-4o** (OpenAI API) — 상용
2. **Claude(비전)** (Anthropic API) — 상용
3. **Quilt-LLaVA** — 이미 완전히 세팅됨: `models/.venv-quilt`, `models/Quilt-Llava-v1.5-7b`,
   기존 파일럿 스크립트 `models/pilot_quilt_llava_*.py` (재사용/참고)
4. **LLaVA-Med** (Microsoft, 오픈소스 의료 특화 VLM) — 아직 미설치, GitHub
   `microsoft/LLaVA-Med` 또는 HuggingFace에서 받아서 설치 필요 (Quilt-LLaVA 설치
   방식 `models/download_quilt_llava.sh` 참고해서 유사하게 진행)

**API 키**: `~/.bashrc`에 `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`로 이미 설정돼 있음
(2026-07-28에 작동 확인됨 — 단, 그 세션에서 실수로 값이 대화 로그에 노출돼서
사용자에게 재발급을 권했었음. **먼저 두 키가 여전히 유효한지 최소 호출로 조용히
확인**하고, 안 되면 사용자에게 새 키를 물어봐).

**GPU**: `nvidia-smi`로 확인 후 비어있는 인덱스(1~5가 보통 비어있음)를
`CUDA_VISIBLE_DEVICES`로 지정해서 LLaVA-Med/Quilt-LLaVA 로컬 추론에 사용.

### 테스트셋 구성

`opendataset/SICAPv2` 재사용 (이미 있는 데이터, 새 다운로드 불필요):
- 실제 pixel-level Gleason grade 라벨 + patch 단위 cribriform 플래그가 이미 있음
- **반드시 SICAPv2가 이미 제공하는 slide-disjoint Test 분할에서만** 패치를 뽑을 것
  (Train 쪽은 절대 안 됨 — 이 프로젝트의 다른 실험들이 Train으로 CONCH probe를
  학습시켰을 수 있으므로, 완전히 독립된 held-out으로 유지해야 벤치마크의 의미가 있음)
- 정상/G3/G4(cribriform 포함)/G5 등급에 걸쳐 층화 표집으로 **50~100장** 구성

### 과제 배터리 (기존 6개 파일럿 방식을 재사용/확장 + 신규 1개)

1. **절대 척도 채점**: 1~10점으로 심각도 채점 요청 → 점수의 분산 확인(모든 이미지에
   같은 점수 주는 "붕괴" 현상이 있는지, 기존 Quilt-LLaVA 파일럿에서 나온 패턴)
2. **개방형 소견 질의**: "무엇이 보이는지, 진단은?" 개방형 질문 → 응답에 이미지로
   검증 불가능한 구체적 진단/소견(예: 물어보지 않은 신경내분비종양, synaptophysin
   등)이 포함되는지 확인 → **환각률(%)**로 정량화(간단한 rubric: 이미지 종류/라벨과
   무관한 특이적 임상 용어 언급 여부, 필요하면 다른 Claude 세션이나 규칙 기반으로
   판정)
3. **강제 이분 비교**: 실제 등급이 다른 두 이미지를 제시하고 "어느 쪽이 더 의심스러운가"
   질문, 좌우 순서를 바꿔가며 반복 → **위치 편향률(%)**(내용과 무관하게 한쪽만
   고르는 비율) + 실제 등급 기준 정확도
4. **(신규) in-context 조건**: 위 1번과 3번 과제를 프롬프트 맨 앞에 실제 라벨이
   달린 예시 2~3장을 포함시켜 반복 → baseline(예시 없음) 대비 개선되는지 비교

### 산출물

- 4개 모델 × 4개 과제의 결과를 **정량 표**로 정리(모델별 환각률, 위치편향률, 점수
  분산/정확도, in-context 개선 여부) — 서술식이 아니라 숫자로.
- 원본 응답 로그도 저장(감사 가능하도록), `models/pilot_vlm_benchmark_*.py` 형태의
  재현 가능한 스크립트로 작성.
- 결과를 `song-datasets/_previews/latex/report.tex`의 VLM 관련 절(§5.2 또는 적절한
  위치)에 반영 — 기존의 서술식 "6개 파일럿" 설명을 이 정식 벤치마크로 보강.
- `docs/01_motivation.md`에 위 인용 문헌 + 새 벤치마크 결과 반영.
- `docs/04_publication_strategy.md` 항목 1("VLM 환각 동기 citable화")을 완료로 표시.
- 프로젝트 메모리(`project-vlm-pathology-status`)에 결과 기록.

### 주의사항 (이 프로젝트의 기존 작업 방식)

- 실제 실험 없이 가정만으로 판단하지 말 것 — 항상 실측 후 결론.
- 결과가 나올 때마다 report.tex와 메모리에 정직하게 기록(성공/실패 둘 다, 특히
  in-context가 실패해도 성공해도 있는 그대로).
- API 비용이 발생하니 큰 배치로 한 번에 다 돌리기 전에, 먼저 5~10장으로 파일럿
  실행해서 프롬프트/파이프라인이 제대로 작동하는지 확인한 뒤 전체(50~100장)로
  확장할 것.
- 통계는 이 프로젝트의 다른 실험들(마커 풀)만큼 큰 표본은 아니므로, 신뢰구간이
  넓다는 걸 정직하게 인지하고 과대 해석하지 말 것.

---

## 이 프롬프트를 만든 배경 (참고용, 새 세션에 복사할 필요 없음)

2026-07-28 대화에서: (1) 논문 포지셔닝을 "VLM 환각 우회 + 검증된 마커 풀"로 정하고,
(2) 이 motivation의 citable한 근거가 부족하다는 걸 확인했고, (3) 문헌 검색으로 위
두 논문(GPT-4V 병리 환각률 46.8%, in-context learning으로 개선되는 반례)을 찾았고,
(4) API 키(OpenAI/Anthropic)가 `~/.bashrc`에 이미 있고 작동한다는 걸 확인했고,
(5) "중간 범위"(상용 2개 + 오픈소스 2개) 벤치마크로 진행하기로 합의했다. 이 세션
자체에서 실행하지 않고 프롬프트로 남겨서 별도 세션에서 실행하기로 함.
