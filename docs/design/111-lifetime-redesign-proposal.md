> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 111 제안 — 이미 알려진 수명을 모든 진입점에 전달

2026-11-04 KST. 사용자에게 재상정 여부를 제시하기 위한 구체 후보다. **L2/구현/새 검토/원격 실행 권한이 아니며 소스는 만들지 않았다.** 110 C 최종 R2 BLOCK4/1·FS owner 배치/검증 source 한정 소진 판정과 prefix 반례를 입력으로 작성했다. [정본](../../outputs/single-host-controller-110/review/AC-L4-r2.json)의 원 class·회차 처분을 보존한다. 110 계획·동결·원 실패·검토 횟수는 수정하지 않는다.

## 남은 두 경계에 대한 답

110 B는 후속 원격 요청의 최초 claim read 전에 원래 global end를 모르는 문제가 남았다. C 수리는 회수600/복사300/업로드·압축해제120의 본문에는 Fence를 세웠지만, 그 Fence의 끝을 구하려는 `_operation_end`가 budget/activation 파일을 읽는다. 읽기가 막히면 아직 watcher가 없다는 실제 반례가 나왔다. 본문에 Fence를 하나 더 넣는 방식으로 이어가지 않고, **기한을 소유한 부모가 이미 검증한 원끝을 호출 인자로 전달**하는 구조를 제안한다.

1. 최초 remote bootstrap의 고정 helper bytes는 inline decode/SHA 검증만으로 메모리에 준비한다. 기존 READY→실제 LIVE와 고정20초 차감을 유지한다. 초기 Fence20이 armed되기 전에는 managed 파일·stdout 응답·자식·archive를 다루지 않는다.
2. 최초 교환에서 정한 시작과 끝, attempt/nonce/claim SHA를 불변 lease 값으로 만든다. 후속 remote caller는 그 고정 scalar를 전달하며 remote는 **최초 managed read 전에** `min(now+20, original_end)`를 armed한다. 이미 지난 끝·누락·비유한·다른 unit/nonce는 읽기0으로 거절한다. 그 안에서 claim SHA와 동일 원끝을 검증하고 같은 끝의 full Fence를 armed한 뒤 초기 Fence를 닫는다.
3. controller/SDK entry와 C의 public/clock/local-process/launch/recover/verify/publish 경계는 같은 lease를 명시 인자로 받는다. 새 helper를 파일에서 읽어 Fence를 준비하지 않는다. 이미 검증해 메모리에 가진 helper를 쓰며, phase 끝 계산은 typed scalar와 순수 monotonic 산술만 사용한다. runtime-budget/config/snapshot을 다시 읽어 검증할 때는 이미 Fence 안이어야 한다. 재검증 파일이 lease를 대체하거나 끝을 늘리지 못한다.
4. 각 phase 진입 직전 monotonic을 고정하고 즉시 `Fence(min(lease.global_end, phase_start+limit))`를 armed한다. 그 다음에 budget/config/원자료 읽기·링크검사·해시·출력·진단을 한다. 회수 전체600, export/각copy300, upload/extract각120, OS clock20 및 기존 native 목적별 한도는 그대로다. 자식 생성·입력·종결·fsync·오류 기록도 원끝에 포함한다. 예외 때문에 새로운2700/phase 기한을 만들지 않는다.
5. 공개 CLI가 임의 lease로 native 권한을 만들지 못하게 한다. 최초 승인/claim/최종 plan·source·L4 지문 검증과 실행1회 소비는 bootstrap 책임이며, standalone run/controller는 기본 거절한다. 전파된 lease는 기존 승인을 대신하는 인증서가 아니다. 최초 client 요청부터 회수까지2700초이며 기존 조건부45분은 실제 첫 요청 전까지 시작하지 않는다.

원래109 두 의무도 남긴다. 새 실행 폐쇄에 OS 시각 setter/UAC가 없어 실제 시각 보정0이어야 하고, 정상 사용자 자식은 생성 순간부터 고정 Job에 속하며 반환 전을 terminal로 오판하면 안 된다. 110 A의 실제 관측과 동일 바이트를 승계하되 새 caller 연결은 다시 검증한다. 과거109 결함을 소급 PASS로 바꾸지 않는다.

이는 제안된 소유 관계다. 실제 구현 및 독립 반례 검증 전에는 충족된 것으로 세지 않는다. OS 스케줄 정지 중 즉시 종료하는 실시간 보장도 하지 않는다.

## 보존할 자산과 새 작업 경계

110 A의 정확한 `winjob.py` SHA `2ca8c90616026a103eb41da18c33f34b012bcd56439cb39af967ea9bf2f683b0`와 독립 PASS 관측은 읽기 전용 내용 자산으로 승계한다. 110 C의 UNKNOWN/명시 NOT_CREATED 구분과 known clock process envelope도 최종 비작성자 판정과 함께 입력으로 보존한다. 기존의 절차 PASS·활성화·승인·native 시도는 승계하지 않는다. 원10816개 immutable runtime dependency 및 모델/ref/USD gate는 기존 census와 정확 바이트 대조 후 승계한다.

새 mutable 후보는 `src/simulation/known_lifetime_controller_111/`의 `bootstrap.py`, `test_bootstrap.py`, `driver.py`, `config.json`, `test_driver.py`와 `outputs/known-lifetime-controller-111/execute.py`의 **6개**다. A helper는 수정하지 않는 dependency다. 기존110 파일을 이름만 바꿔 수리 재개하지 않고, lease 전달·첫 읽기 전 소유 구조를 L1/L2에서 확정한다. 원 class 원장은111에도 연속으로 가져가며 새 unit 이름으로 충분 임계·미해결·소진을 초기화하지 않는다. 원109와110의 회차/소스는 닫힌 채 보존한다.

승인받을 새 예산 후보는 B2/C4 구현 각각25분, 검토 각45분, B/C/통합 각각 L2 최대2·L4 최대2다. source/helper/중계·진입점의 실제 연결 계약과 namespace/census를 먼저 확정하고 비작성자 L2 PASS 후 작성한다. 첫 원격은 모든 단위와 통합 코드검토 PASS 및 typed native 권한 이후만 가능하다. B·통합만 추가 검토하려던 이전 질문은 이 C 잔여 경계를 해결하지 못하므로, 이 제안으로 진행한다면 그 질문을 대체하는 명시 결정으로 기록한다.

## 반드시 관측할 대조

- 원110 actual recovery-prefix read를 막는 반례와 정상읽기/본문차단 대조를 동결 사본에서 재현하고, 새 actual caller에서 같은 파일잠금·동일 원끝을 써 producer가 더는 기한 밖에 남지 않는지 고정 handle로 확인한다.
- 원600/2700 수치를 유지한 global 잔여1.2초의 budget/config/claim 읽기 차단, phase만 더 짧은 대조, 진단/출력 차단을 구분한다. 짧은 HOST 관측을 실제600초 경과로 쓰지 않는다.
- remote entry가 원끝 뒤 도착하면 managed read/write/child0, 끝 직전이면 정확 원끝까지, claim 불일치면 권한 실패여야 한다. 실제 caller scalar 배선과 정확 원 버그 복원 mutation을 함께 검증한다.
- 알려진 PID/FILETIME/actual exit 보존, post-delegation UNKNOWN, admission 다섯째 인자, helper Job/handle 수명, USD gate·physics/시간 원기준을 회귀한다. SDK 전에 무승인 진입의 거절을 관측한다.

게인64/16·cap·097 후보·모델·물리/시간 기준을 완화하지 않는다. 실물 CAN·급전·flash·모터·설치·시각 변경·UAC는 계속0이다. 정지 수용을 통과한 뒤만 큰 동작으로 간다. 이 문서를 저장한 현재도 새111 소스/예산·원격 실행은0이다.
