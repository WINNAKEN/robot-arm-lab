> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 112 후보 — 정적 workspace 전건 검산을 첫 원격 전에 실행하고 입력 해시로 재사용

2026-11-04 KST. **제안만: 사용자 새 예산 미승인, source0/HOST0/L2·L4·SSH0/native45 미착수.** 111의 두 코드 결함과 실제 import·정지 통과를 보존하면서, motion 준비가1680초 headroom을 소모한 관측을 입력으로 한다. 111 L4 통합2/2의 R3나 원 single-attempt 재시도가 아니다.

## 입력과 선택

111 closed ZIP SHA7dc14ccbce2cb3ae64d51c52f0521c528089bd733328534dfd3c96b34919ade1, offline-observation.json, performance-diagnosis.json, 최종 코드 L4 df4fa7d7...를 그대로 읽는다. 정지 native 종료 후 motion launch 전 여유는193.171초였다. 로컬 full workspace3회만80.591초였고 C는 prepare/snapshot/consume/proof에서 반복한다. 원격 함수별 비용은 아직 미계측이다.

후보는 **원 순수 workspace 검산을 원래 알고리즘·8192 samples/6241 path 전건으로 첫 원격 이전에 한 번 수행한 영수증**이다. 원 source·model16·workspace/program·oracle·규칙 등 모든 결정 입력의 실제 같은 바이트 SHA/길이, 실행 알고리즘 SHA, 전체 결과와 metrics를 영수증에 결속한다. 원격에서는 매 사용 시 현재 sealed input 바이트를 다시 검증한 뒤 일치하는 순수 결과만 재사용한다. 실제 SDK import·provider·COM/속도·고정 기저·정착·중력·프레임·종료 검사는 캐시하지 않는다. 물리/시간 기준·원 프로그램/게인64/16·cap·native600/motion900/cleanup150·headroom1380/1680·총2700초는 그대로다.

그냥 PASS 파일을 믿는 경로는 허용하지 않는다. 영수증은 exact freeze dependency와 최종 비작성자 L4·typed native 승인에 포함되고, 누락/추가키/다른unit/알고리즘·모델·program·oracle·result 변조는 첫 SSH 전에 거절한다. 원격 전달 뒤에도 실제 source20/model/ref 바이트와 같은 영수증인지 확인한다. 검산과 key 생성이 다른 파일 사본을 읽어 생기는 TOCTOU·경로 alias 문제를 피하도록 **동일 읽기 바이트 bundle 기반의 명시 API**를 L2에서 확정한다. 전제 결속을 입증할 수 없으면 BLOCK이며 조용한 fallback/기준 생략·source 확대는 없다.

## 제안 소유와 새 예산

새 mutable8/M8, 세 그룹이다. 111·108 원 파일을 수정하지 않고 `src/simulation/static_workspace_preflight_112/`와 `outputs/static-workspace-preflight-112/`에 새 사본을 둔다.

| 그룹 | 파일/책임 | 제안 구현·HOST 누적 상한 |
|---|---|---|
| B2/S2 | bootstrap.py, test_bootstrap.py: unit112·정확 입력/영수증·census/권한/command 계약 | 첫 source write부터1500초 |
| C4/S4 | driver.py, config.json, test_driver.py, OUT execute.py: 새 validator·receipt 명시 배선, 시간계측, 기존 실패/종료/수명 보존 | 첫 source write부터1500초 |
| D2/S2 | validate.py, test_validate.py: 원 static verifier를 기준으로 같은 바이트 전건 검산/영수증 소비 API와 차등 시험 | 첫 source write부터1500초 |

각 L2/L4 최대2회, 비작성자 각2700초이며 BLOCK 수리는 작성자만 한다. 주/보조 검토가 B/C/D/통합을 각각 판정한다. 기존 명시 same-family 비작성자 폴백만 유지하고 편향을 기록한다. bridge 수리/설치·새 모델 비용 권한은 포함하지 않는다. 소진/다음 재발 임계는 세션 명칭과 무관하게 연속 승계한다. 111 두 class union1/open0/다음 distinct2 충분 임계 및 옛 B/FS/raw/restoration/109 소진을 초기화하지 않는다.

runtime은 원 immutable108 중 validate를 제외한15 + 새 bootstrap/driver/config/validate4 + exact A helper1로20을 유지하는 후보다. immutable dependencies는15 source/11 refs/16 model/3 USD/1 helper/1 preflight receipt=47, mutable8+metadata5+manifest1로 capsule61 후보다. 이는 source0의 명시 계약이며 실제 L1 census와 L2에서 전건 닫기 전 코딩하지 않는다. 원 sampler/물리 source는 읽기 전용이다.

## 추가 필수 수용 조건

1. 원 full verifier 실제 양성 결과와 새 preflight/재사용 결과가 같은 입력에서 일치. 모든 기존 물리 체크는 원 실패 fixture에서 계속 실패한다.
2. 모델16·source20·workspace·program·oracle·검산 규칙/영수증 결과 각각 변조·다른 unit·삭제·중복·path alias·결과 반환 후 수정은 원격/SDK 전에 차단. 캐시 hit가 파일/owner/권한 검증을 우회하지 않는다.
3. 새 API 실제 C caller → D consumer를 관측하고 영수증 없는/과거111 경로는 거절. 입력 binding 판정과 실제 사용이 같은 bytes다.
4. HOT path의 전체 sample 검산 호출 수와 반복 proof 비용을 HOST에서 계측한다. 단순 주장 대신 실제 원 소비자와 재사용 대조를 보존한다. 로컬 시간만으로 원격 headroom 성공을 보장하지 않는다.
5. 실제 runtime source20/제출 모델·원 helper/정리·raw/실제 child exit/UNKNOWN 의미·command8000·float interval 전건 유지. source와 기준을 바꿔 시간만 맞추지 않는다.
6. 원111 native 결과/attempt/기한·모든 실패·검토·47 HOST/정지21frame과 CAD22를 보존한다.

로컬 구현·검토가 전부 통과한 뒤에만 **새 첫 원격2700초 단일 예산**을 시작한다는 조건부 새 권한을 제안한다. import1 → 정지1 통과 → motion1(42초), 배치/회수 포함, 자동 retry0이다. 새 영수증·source이므로111의 import/정지 성공을 새 native 실행 승인이나 새 source의 수용으로 승격하지 않는다. 실제 시간 여유가 부족하면 동일 gate로 차단하며 예산을 늘리지 않는다.

새 원격 승인 전112 native-approval/attempt/활성화 파일0을 유지한다. 실물 CAN·급전·flash·모터·설치·UAC·OS 시각/시간서비스·네트워크 설정 변경은 범위 밖이다. 승인 이후에도 전 단계 실패 시 큰 동작0이다.
