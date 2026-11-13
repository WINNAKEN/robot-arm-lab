> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 038 — 관측 완료 게시·공통 대조 술어 / Windows 환경 분리

2026-10-26 사용자 명시 처분: 시험 관측부·대조시험 새 설계, Windows 시간 위반 별도 구분, 실물 보정·모터 운전 제외. 037 BLOCK/VERIFICATION APPROACH EXHAUSTED·원자료·예산을 보존한다. 새 범위는 관측 완료와 oracle 수정뿐이며 기존 서비스전제 복구/타이머튜닝/제품수정이 아니다. 기존 PA/terminal/startup/firstfault 원장/충분다음 임계 유지. L2 최대2/L4 최대2, 비작성자 검토·외부계열 기존 차단/NOT_RUN 잔여 유지.

## 소유·구조

새 `src/firmware/tests/walltime_observer/`의 fixture/browser/oracle 및 `.dev/observer-controls-evidence/`와 문서만 수정한다. 기존037/035/제품 소스·native actor/타이머/guard/approval 불변. 037 native strict builder를 실행하여 그 native actor를 그대로 사용하며 새target빌드/장치/플래시/WiFi접속 없음. profile은 기존 host FakeCAN이며 실제 보정·운전 승인이 아니다. FD/F3enable0·calibrationfalse 불변.

## 완료 경계

fixture는 result를 로컬 변수로 받아 native audit/T와 actual post-status까지 모은 뒤 불변 `completed={result,audit,post}` 한 값을 원자적으로 공개한다. consumer는 completed만 대기·소비한다. result/audit 부분게시 금지; HTTP body와 product 상태는 원래 실제값 유지. missing-forward fixture는 성공형 result를 만들되 actual pre/post 상태는 실제 native에서 읽고 동일 completed형식으로 게시한다. 정상 응답/대조 응답의 소비자는 같은 코드다.

공통 순수 causal predicate는 pre-click과 native pre-admission clean phase0/stop0/fault0, authenticated result errors0, 양수 accepted_at==actual post.stop_at, 일치 namespace/axis를 검사한다. 데이터만 입력하며 control 이름/forwarded 플래그를 받지 않는다. 누락전달 fake result의 accepted_at은 실제 현재시각 양수로 만들어 0 sentinel만으로 검출하지 않는다. asset identity도 현재 실제수신바이트로 검사한다. missing-forward 성공 credit은 원본 공통술어가 data-dependent하게 false여야만 가능하다.

## Windows 시간 위반 분리 (성공으로 전환 금지)

각 결과에 verification PASS/FAIL/NOT_REACHED와 environment max_gap/서비스위반 사실을 분리한다. native real clock gap>=10과 core Time fault8/사전자동stop을 실제 자료로 확인한 경우에만 ENV_SERVICE_VIOLATION으로 실행 방해를 분류한다. 원래 invariant/data mismatch/asset failure를 단지 max_gap이 크다는 이유로 환경으로 덮지 않는다. 원인불명은 FAIL. 자동정지 뒤 명시Stop 성공 credit 금지. 환경으로 미도달한 양성/대조는 NOT_REACHED·credit0이며 전체실시간수용은 OPEN이다. 단순 타임아웃·JSON오류·누락파일도 환경으로 치환하지 않는다. 환경위반 자체의 측정은 제품/관측기 결함 판정과 분리하되 원래037 실패를 PASS로 바꾸지 않는다.

## 고정 검증 목록·한도

1. 새 fixture 완료게시를 별도 Node시험에서 native RPC를 명시적 deferred promise로 막아 result만 끝난 중간상태에서 completed가 없는지 확인하고 T/post 완료후 한 번 공개·불변임을 확인한다. 실제 fixture 코드와 독립 데이터 oracle을 쓴다. 순수 oracle에는 정상양성·누락poststop0·wrongnamespace·priorfault·missingmetadata·시간환경분류 우선순위를 넣는다. 가상 단위시험의 Promise 제어는 실제wallclock 브라우저 증명과 구분한다.
2. 실제 무수정DOM/타이머, 실제native cold Boot: readonly3초, baseline축1/2, held-status1200ms+held-StopACK1200ms, inboundStop100ms, badpair 각1회. actual completion 후 ACK전에 Stop 인과, 실제 Terminal/history·manualcut보고, 실제delay측정. 정상운전Stop/인계/실물수용 아님.
3. 별도 고정 원본-before→valid-commentasset변경→missingforward→원본-after 각1회. 환경실패면 반복하지 않고 credit0; 음성은 공통data oracle 실패와 실제 자료 확인. 원본전후 PASS가 아니면 bracket 수용 안 함.

작성자 전체목록1회·대조1회, 독립 L4도 같은 고정목록각1회. 원자료/환경실패/미도달 보존. 타이머/priority/phase/sleep 조정으로 성공일정 탐색 없음. 관측부 defect 발견 시 L4예산 내 수정은 가능하지만 실행 한도 확장은 사전에 남은 범위를 명시해야 하며 무한 반복 금지. 이전037 코드/실패를 수정하지 않는다. 전체 실시간 검증 완료는 모든필수양성·유효대조가 있어야만 가능하며, 환경 미도달이면 관측부 단위수용/부분실측까지만 분리해서 보고한다.

최종 수용: 생산/기존037 해시불변, 완료게시 단위검증·공통 oracle/효과있는누락대조·환경분류검증, 실제브라우저 도달범위/미도달 명시, 비작성자 L4. scalar latency는 각시계내차분, 샘플을 실제폰/WiFi·물리정지 상한으로 표현하지 않는다. 도달coldStop verifiedfalse/manualcuttrue는 그대로 표시한다. 인계/HANDOFF·BACKLOG·LESSONS와 로컬커밋 보존, push없음.
