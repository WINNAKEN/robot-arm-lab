> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 096 — 기존52초 독립감사·정착 분석·회수 경로 수리

2026-11-01 KST. 사용자는 095 후속 추천(기존 로그 정착 분석/독립감사,120초 회수 경로 수리,그 뒤 별도 수정안·재시험)에 「좋아 진행해」로 동의했다. 이번 096은 앞의 두 작업을 계획→검토→구현→검토로 수행한다. 새 SimulationApp/native/SSH/네트워크/실물CAN/serial/flash/급전/모터/보정/설치/재부팅/전원정책/구매/학습/외부업로드는0. 새45분 시계도 만들지 않는다. 게인64/16·cap·물성·원52초 경로·COM/정착/한계 기준은 불변이다. 095의 old45/native 각1회/원FAILED·recovered-validation/L4소진/정착15·velocity-onlyEXHAUSTED·모든과거임계는 보존한다. 동일계열 비작성자 폴백의 기존 사용자 승인과 공통편향을 이어간다.

## 소유와 절차

src/simulation/recovery_ready_run/는095 source17을 복제하고 recovery.py를 더한 새 source18 비활성 사본이다. driver의export/caller·config metadata·HOST·README만 바꾸고 제어/씬/수용 코드·프로그램을 바꾸지 않는다. public prepare/run 및 remote supervise/native는096 전용명시거절로 차단하고 config.deadline_unix=0을 유지한다. source18은 향후 검토 단위의 재사용 후보이며 이번에 native-ready/물리수용을 선언하지 않는다.

분석/원본감사/실행하네스·새증거·검토는 outputs/isaac-offline-096/, 문서는 본 계획/096-results.md, 최소 HANDOFF prepend/SESSION_HANDOFF append만 소유한다. 원095 source/output(ignored ZIP 포함),095계획/결과와 기존 보호2740경로를 전후 SHA256 보호하고 R1을 수정하면 그 source/harness/결과를 별도 보존한다. CAD/URDF/BOM/펌웨어는 무변경이다.

새 L2 최대2/L4 최대2, 비작성자 한 명을 재사용한다. L2 논리 검토 후 구현, HOST/기계검사 후 L4에서 원095 자료 독립감사와 새코드 풀스코프 검토를 함께 수행한다. SDK/네트워크 검토는0이다. 지적 합집합/class·착지·소진/다음임계·과거실패보존을 매 라운드 기록한다. 예산 소진 뒤 자동R3·수리·새native는 없다. 비작성자 외부계열 가능 시 전제 재검증을 우선한다.

## 원본 감사와 정착 분석

고정된095 job/source/원terminal·parent·remote-shell/원봉인 파일의 전체 해시·원transport와 최초FAILED·별도복구receipt/status를 대조한다. 원 source의 offline consumer도 실행할 수 있지만 native를 재실행하지 않는다. 52초6240step6241obs521frame, 연속 journal↔report, PNG CRC/sidecar q/qd/clock,7endpoint·rawM9/C9/G9·COM·원metrics를 재검증한다. 전체physics는 정착미달 BLOCK 그대로이며 원sdk_connectedfalse 예외를 SDK미실행으로 해석하지 않는다. 096 독립 감사는095의 소진된R3가 아니라 새로 승인된 오프라인 증거 감사다.

분석은 기록된 정지구간만으로 한다. 34초 endpoint 전후 목표/실제q·qd·명령FF·남은cap여유를 표/그림으로 비교하고, 그 hold 안에서 기준 최초진입/이후 연속 통과 구간을 계산한다. hold 뒤 목표가 바뀐 자료를 동일목표 정착으로 세지 않는다. endpoint 한행 판정과 사후 계산한 연속구간은 분리한다. J3/J5의 위치오차 감소/최소/기준교차·속도·다른hold와 비교하여 후보를 좁히되, 기록만으로 유일 원인/정적평형/실제PD토크·포화를 확정하지 않는다. 실제PD/포화 UNKNOWN, moving-root 독립교정 NOT_DONE을 유지한다. 허용오차·hold시간·경로·게인·cap 튜닝은 하지 않는다. 결론/숫자는 소유 재현 스크립트가 생성하고 문서는 그 결과와 대조한다.

## 회수 수리 — 실제 새 caller/dispatcher 경로

관측된 결함은 정상native778.359초 뒤 export SSH가 default120초를 넘은 것이다. 원driver.entry는 export도 snapshot()의smoke 물리검증을 먼저 거치며 launch의export/SCP는120초 대기를 쓴다. 이것은 코드상 관측이며 지배비용의 유일 원인으로 단정하지 않는다.

새 recovery.py는 stdlib-only로 closed native terminal 또는 실패 parent snapshot의 identity/PID/REAPED/원 해시/안전한경로/입력 바이트를 검증하고, 물리·기하학 의미검증이나 SDK 모듈 import를 하지 않고 기존출력만 별도아카이브로 복사한다. native terminal 부재 시 실패 parent manifest의정확 inventory/hash와 native_acceptance=false/native_reexecuted=false를 요구하며 성공 seal을 제조하지 않는다. 열린/불일치/변조/중복·경로탈출·링크는 거절한다. archive와receipt는 exclusive 새 파일이며 실패/부분파일/과거validation을 덮지 않는다. receipt는 archive hash·기존파일 해시·job/native 프로세스결과·복사유형을 결속하고 native acceptance를 부여하지 않는다. 수용 의미검사는 회수후 기존consumer의 별도 결과로만 기록한다.

새 driver.entry의 export 분기는 일반 snapshot() 앞에서 검증된 recovery.py를 로드해 이 경로로 진입한다. 나머지 native역할은096 명시차단이다. launch의실제export/SCP caller는 정확 int export_timeout_s=300, recovery_total_s=600을 읽고 native절대deadline과 min인 단일 회수deadline 안에서 남은시간으로 각 호출을 제한한다. 기본120의 우발 재사용·불리언/NaN·목적혼용·기한 경계를 거부하고 새시계/자동재시도/native 재실행은 없다. 회수실패를 nativeSDK미실행으로 바꾸지 않도록 native transport 결과와 recovery 상태를 별도 기록한다. 원 native 실패는 성공으로 바꾸지 않는다. 원095는 무수정이며 수정은이새비활성caller/dispatcher에서만 한다.

HOST는 실제 새entry export와 launch 호출부를 통과시킨다. synthetic transport/가상clock으로120초초과 지연양성·300/600/절대deadline 제한·archive/SCP실패·호출순서·실패보존을 검사한다. 일반snapshot이export에서 호출되면 실패하도록 차단하고, 원 snapshot-first/default120 복원변형이 대응검사에서 FAIL인지 확인한다. 실제095 로컬closed 자료도 새 exporter로 새 소유폴더에 복사해 전체 원본 해시/receipt를 검증한다. 원 archive/validation을 덮지 않는다. 이것은 로컬복사 검증이며 SSH성능/native/실물검증이 아니다. 사진/그림은 원수치기반이며 외부 업로드는 없다.

## 9개 이진 수용 기준

AC1 권한/비활성/native·네트워크0/실물false. AC2 원095·과거실패·보호 목록 SHA불변. AC3 원본 identity/seal/consumer/복구실패보존과 독립감사. AC4 52초·저널/프레임/endpoint/COM 판정 정확. AC5 동일목표hold 분석·불완전관측/UNKNOWN·원기준 유지. AC6 closed-only exporter의 경로/입력/출력/실패snapshot·exclusive/receipt 결속. AC7 실제caller/dispatcher fast경로와300/600/절대deadline·별도회수상태. AC8 양음성·옛버그복원변형·로컬실제자료·코드기계검사 재현. AC9 한계/소진/공통편향/결과·바이트보존인계·정확소유 로컬commit.

096 완료는 오프라인분석·독립감사·회수수리의 HOST/로컬 증거 범위다. 실제 새원격 export/수리 native/전체물리 PASS는 NOT_RUN이다. 후속변경 후보와 필요한새검증을 구체화하되 승인·새검토·새예산 없이 재실행하지 않는다.
