# P0 Evidence & Governance Portal

이 포털은 P0-M8 근거 검토, P0-G8 역할별 전자 판정, G8 최종 확정,
P0-M9 clean rerun과 P0-G9 결과 확인을 한 화면에 묶는다. 인터넷이나
외부 CDN을 사용하지 않으며 서버의 loopback 주소에만 바인딩한다.

## 1. 서버에서 시작

저장소 루트에서 다음 명령을 실행한다.

```bash
.venv/bin/python projects/quantitative_foundation_model_validation/governance_portal/portal_server.py --host 127.0.0.1 --port 8011
```

장시간 유지하려면 기존 서버 운영 방식에 맞춰 `tmux` 또는 `systemd --user`를
사용한다. 방화벽 포트를 열거나 `0.0.0.0`으로 바인딩하지 않는다.

현재 서버에서는 `qfmv-governance` tmux 세션이 `run_portal_forever.sh`를 실행한다.
Python 포털 프로세스가 예기치 않게 종료되면 3초 후 자동 재시작하며 로그는
`preexperiment/governance_records/portal_server.log`에 기록된다.

## 2. 로컬 PC에서 SSH tunnel 연결

로컬 PC 터미널에서 아래 명령을 실행한 채 브라우저로
`http://127.0.0.1:8011`에 접속한다.

```bash
ssh -N -L 8011:127.0.0.1:8011 <사용자>@<원격서버>
```

로컬 8011 포트가 사용 중이면 왼쪽 포트만 바꿀 수 있다. 예를 들어
`-L 18011:127.0.0.1:8011`이면 브라우저 주소는
`http://127.0.0.1:18011`이다.

## 검토·승인 절차

1. 판정 범위, P0-Q1~Q6 답, 미해결 위험과 evidence 파일을 검토한다.
2. 이 독립 연구에서는 연구책임자가 최종 판정한다. 병리·통계·ML/데이터 검토는
   필요 시 기록하는 선택 자문이며 G8을 차단하지 않는다.
3. 연구책임자의 최신 판정이 동일 snapshot에 대한 `Conditional Go`이면
   `FINALIZE G8`을 입력해 G8을 확정한다.
4. `RUN FULL CLEAN RERUN`을 입력해 P0-M9을 시작한다. 이 단계는 GPU를
   사용하며 별도 attempt 디렉터리에서 실행된다.
5. 포털의 G9 결과가 `PASS`인지 확인한다. 불일치 시 자동 인계하지 않고
   `revise` 또는 `failed` 상태와 로그를 보존한다.

승인 source ledger와 파생 manifest는
`preexperiment/governance_records/`에 기록된다. 기존 P0-M8 결과와 immutable
clinician source는 수정하지 않는다. 승인 기록은 덮어쓰지 않고 JSONL에
append되며, 동일 역할의 재검토는 새 record로 추가된다.

현재 전자서명은 SSH로 접근 통제된 서버에서 실명과 역할을 확인하는 내부
attestation이다. 인증서 기반 규제 전자서명은 아니므로, 해당 수준이 필요하면 기관
SSO/PKI와 별도 승인 정책을 연결해야 한다.

## 해석 제한

G8/G9가 통과해도 다음은 해제되지 않는다.

- 측정 반복성 없이 confirmatory target 지정
- 임상 또는 whole-slide PNI 진단 주장
- encoder 우월성, scanner/stain 견고성 주장
- 독립 metric–endpoint pair, 적절한 사건 수와 외부 검증 없는 H2 본 분석

즉, 포털은 승인과 재현성 문제를 해결하지만 부족한 과학적 근거를 서명으로
대체하지 않는다.
