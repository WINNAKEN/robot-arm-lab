> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 137 — 실측 jaw 기반 피니언 reference 수리·오프라인 실행 경로 검증

## 권한과 책임

2026-11-10 사용자 「계속 작업 이어가.」에 따라 완료136이 권고한 시뮬 제어 수리를 진행한다. 단위137의 범위는 로컬 구현·HOST·비작성자 검토·오프라인 runtime kit 준비다. 실제 SDK/SSH/원격 실행·영상/Drive 추가·실물 CAN/RS485·포트·급전·flash·설치·네트워크/시계·Git 작업은0이다. 원 CAD/URDF/STL·원장·출력 작업·133/130/134/135/136 코드와 기록·게인·cap·속도 한도·기존 정지/파지/동작 수용 기준은 보존한다. 현재 출력 작업의 v4 동일성은 미확인이다.

신규 소유는 `src/simulation/mp18_pinion_feedback_137/{feedback.py,prepare.py,test_feedback.py,test_prepare.py}`4개와 이 계획1개, `outputs/mp18-pinion-feedback-137/` 새 전용 산출이다. kit에 생성되는 파생 native wrapper와 effective native body까지 구현 표면으로 세도7개/M이며, 변경 없는 원133/130 코드·모델 복사본은 readonly dependency다. 그룹은 실측 reference 정책, 실제 native 경로 배선/준비의2개다. 기존 source를 수정하지 않고 새 파생물만 만든다. Root만 HANDOFF/SESSION을 보존 덧붙인다.

L1 Root→비작성자 L2→별도작성자 L3/HOST→비작성자 L4→Root 정확 핀 확인·최종 오프라인 CLI1회. 각 role 내부 cap2700초, main은 L2+L4 공유 누적2700초(첫읽기/준비/실행/수리/출판 포함, 명시 동결 대기만 제외), closing300초 확보. 사용자 명시 새45분 승인이라고 쓰지 않는다. 작성자 readonly 준비≤120초에서 동결·FINAL L2 PASS 전 code0. L2/L4 각각max2/합max4/no5, 분기 예산 전환0. 기존 사용자 승인 동일계열 비작성자 폴백을 유지하고 공통 편향을 잔여로 기록한다.

이것은136 분석의 재실행이나 기존 소진 예산의 이름 변경이 아닌 새 reference 제어 구현 책임이다. 원136 신규class0, 원135 CONSUMED_SOURCE_PROVENANCE_WINDOW1 CLOSED, 원134 두class CLOSED 및 모든 예산/라운드/원시자료를 보존한다. 유사한 실제 새 인스턴스는 비작성자가 기존 계보에 연결해 판정한다.

## 고정 근거와 관측

- 136 `Root-final-result.json` SHA `c5610c15a6a4bc0a192c99190479c5a41610473da318480d3ad5701dc0ad9aa3`, source-freeze `07ae1e1bb61b2ea6c62caf9f48e9b29e4972c7d42d21951d74b2650c17513162`, finalL4 `6fbb60c700a17d4ccf8685e421396654fe3f0a3fe8a2458730c57356d19094bf`/publication `f0db30e8665c9b7df637ddd7a55181da8baf0602fca39b0c1918ff611923cc7e`를 실제 읽고 검산한다. 136은 actual 위치 결합 peak2.332424°/등가rack0.549564mm와57초 gear 교차를 확인했으나 제어 수리의 새 plant response는 검증하지 않았다.
- 133 F6 `outputs/mp18-manipulation-133/author/source-freeze.json` SHA `3cf40c09cc20bac27195fc1963e997734f3dbc3e8e03b25bf737e0ecf97ace3f`; actual05 native-result SHA `c4345f4461601566d9398a7ab6101217f2bfa0e1f851b8bfb33352687a92b4e2`, run `850124eb93cc4cc4945ee02c3aa1ed0d`, job `816522a14e506263a7a7517ce76ad7deb23402ffc6bddd6c23513f306725a6ae`. 현재 L1이 원378핀 일치를 확인했다. raw `attempts/05/retrieved/motion.ndjson`는 native-result와136 manifest를 통해 SHA/bytes 및11161행·step0..11160/time=step/120/실제 시계를 결속한다.
- 원 source `mp18_isaac_130/native.py` SHA `e78af630c5dfda106dca14d3059065c0e060c63671e2ba8b3d0756cd86b1dcd8`, contract.py SHA `9052f08394a2af45f7c73b259a9bece983393bcc0d102a82a6fb21010d5574cf`와133 native/contract/config/planner/scenario/model을 F6에서 캡처한다. 모든 소비 원파일은 소비 전후 SHA/bytes와 실제 실행 바이트를 결속한다.
- 원130 `_native`의 실제 step loop는 logical target 생성→mimic logical검사→같은 current clock에서 gravity/FF/cap검사→실제 setter/readback→sim.step→actual state→journal/phase_check 순서다. current는 command step n 직전 n-1의 관측이다. 원133은 원130을 exact anchors로 파생한다. **133의 최종 `_text` exec 직전**에137 파생을 적용하면 원130 SHA와 원133 anchor들을 보존할 수 있다. 원130 먼저 바꾸고133을 적용하지 않는다.
- current qA 범위[-.0100165866315,.0100007941946]m, abs(qdA)max .00960943754762m/s가 원11161행에서 관측됐다. ratio -74.07407407407408이면 pinion reference범위[-.740799569973,.741969380114]rad/속도 max.711810188713rad/s로 기존 한도 안이다. 이 관측을 미래 plant의 한도 보증으로 확대하지 않는다.

## 실측 reference 정책

원 logical target(dict), reference_velocity, velocity_targets는 절대 mutate하지 않는다. 원 궤적과 verify_coupled_targets/phase_check/Task acceptance/fault logicaltarget을 그대로 유지한다. 별도 applied reference 객체를 만든다.

1. 모델의 movable9·정확 DOF 이름, pinion revolute/slide_A prismatic, XML-derived mimic의 leader=KG1_slide_A·multiplier·offset 및 기존 limit/velocity가 고정 원모델과 일치하는지 확인한다. ratio는 runtime source model에서 읽고 r13.5mm/기존 XML 비율과 검산한다. B를 임의 평균·선택해 오차를 숨기지 않는다.
2. 현재 관측 q/qd의 유한 scalar·9DOF census·same clock_before/clock_after/clock·expected current step n-1·engine time을 검산한다. duplicate/missing/잘못된 step·stale clock·비유한/boolean·벡터·잘못된 모델/이름/기어비는 실패한다. 이 시계 검산은 실제 source에서 current가 읽힌 경로와 연결돼야 하며 같은 필드가 존재한다는 helper 검사만으로 실측 출처를 주장하지 않는다.
3. pinion position reference = multiplier × current.q[leader] + offset; pinion velocity reference = multiplier × current.qd[leader]. 같은 causal snapshot에서 계산한다. 나머지8DOF의 실제 전송 position/velocity는 기존 float32 변환 의미를 포함해 그대로 보존한다. gain/effort/FF/max velocity/물성/기준 변경0이다.
4. finite·기존 위치/속도 한도와 binary32 전송/오차를 확인한다. 잘못된 입력이나 한도 초과를 clamp/filter/default/목표값 fallback으로 숨기지 않고 **어떤 setter보다 먼저** 실패시킨다. 수치 반올림 오차는 보고하되 물리 한도를 늘리지 않는다. 실제 pinion이 새 reference를 추종하는지·고주파/지연·안정성·실제 치합은 이번 HOST로 검증되지 않는다.
5. receipt에는 원 logical reference, applied position/velocity, 입력 실제 q/qd, source clock/step, command step, leader/multiplier/offset, float32 전송값/관측 readback을 구분해 기록한다. target/state snapshot을 수정하지 않는다. initial row는 실제 setter가 없으므로 NOT_APPLIED로 표시한다.

## 실제 native 배선과 kit

원133/130을 immutable bytes에서 조합해 새 native wrapper/effective body를 생성한다. 실제 setter/readback 바로 전에 정책을 호출하고 applied position/velocity로만 pinion 목표를 전달한다. 원 logical target의 verify·journal targets·phase_check·Task acceptance는 유지한다. 추가 journal 필드는 applied receipt와 source clock이므로 post-step 실제 q/qd와 혼동하지 않는다. source clock이 바뀌거나 readback이 다르면 기존 실패/종료 경로로 빠지며 이후 sim.step/정상 완료를 내지 않는다. 기존 FF/cap 초과·속도/정착·watchdog·회수 경로는 변경하지 않는다.

파생은 정확히1개씩의 source anchor/AST 구조와 필요한 setter/readback/receipt 소비 위치를 검산한다. 키워드가 있다는 것만으로 성공하지 않는다. 파생 effective `_native` 코드와 HOST에서 실행한 AST가 실제 생성 모듈의 코드에 결속되는 근거를 남긴다. helper 단독 테스트를 실제 배선 검증으로 세지 않는다.

kit는 새 outputs137 leaf 안에 native/feedback/필요한 readonly contract·planner·scenario·config·model/refs를 명시 allowlist로 묶는다. 실제로 쓰는 파일과 SHA/bytes를 manifest에 전수 적고, 파생 변경부/그대로 복사한 파일을 구분한다. 승인 파일(approval.json/current-user-approval 등), job/lease/run admission, 실행 가능한 runner/driver/proxy/SSH bootstrap은 **포함하거나 재활성화하지 않는다**. 133 attempt6/옛45분·SDK grant를 열지 않는다. 원 config의 역사적 경로 문구는 실행 권한이 아니다. 표지는 PREPARED_NOT_RUN/hardware_approved=false/new_runtime_approved=false이며, 새 원격 owner 통합/SDK 실행은 별도 구체 단계로 남는다. 이번 CLI에는 실제 SDK나 transport를 호출할 선택지가 없다.

kit를 읽어 실행할 때도 manifest로 확인한 캡처 바이트를 compile/exec한다. 생성 후 파일을 바꾼 뒤 그것을 실행 근거로 늦게 hash하는135 문제를 재도입하지 않는다. feedback module은 같은 해시 검산 bytes로 실행하고, 원133 base source guards를 유지한다. 향후 owner 역시 kit와 새 sourceF/권한을 검산해야 한다는 계약을 남긴다.

## HOST·재생·판별력

실제 생산 CLI→키트 생성→생성 native 코드의 실제 actuation step loop/setter/readback/journal을 fakeSDK·named robot callback으로 통과한다. SDK 초기화/scene/동역학은 HOST 범위 밖이다. AST를 추출할 경우 생성 effective source와 실제 함수 코드/모듈 결속을 검산하고 실제 분기를 고쳐 테스트만 통과시키지 않는다. 원형상/FF/Task 전체를 HOST가 새로 검증했다고 쓰지 않는다.

원11161행의 command n=1..11160에 대해 **pre-state row n-1**과 logical target row n을 사용한다. original130/133과 동일한 step/시계·이름 재배열·진짜 setter/readback 경로를 재생한다. fake sim은 시간만 진행하고 actual state는 원133 기록 그대로 공급한다. 따라서 새 plant response가 아니며 새 sim/그립 성공·실제 교차0을 주장하지 않는다. 원 실제 결합 오차/원135 겹침/원133 수용 결과는 그대로 남긴다.

전 command에서 다른8DOF 전송값 불변, A 기준 applied coupling 오차가 수치 반올림 범위임, B 기준에는 실측 비대칭만 남음, ref 위치/속도 기존한도 내 여부를 전수 기록한다. 현재137 command가 미래 actual pinion 상태인 것처럼 끼워 넣은 geometry 보고는 금지한다. 원단일 정책 이전 상태/target은 전후 동일해야 한다.

양성/음성: canonical source model·입력 정상, DOF permutation, q/qd/clock step·bool/nonfinite/누락·과도속도/위치·모델 ratio변경, snapshot mutate, readback 오염, stale state와 state를logicaltarget으로바꾼 배선, wrong sign/1000배단위·B잘못선택·velocity를command에서읽는변이, source초기/late변경·의존성바꿈·실native output reparse/alias/escape·출판실패를 다룬다. 오류는 setter0/step0 등 실제 금지 지점에 도달했는지 검증한다. **같은 입력과 실제 원 setter 분기로 이전 목표값 연동 버그를 정확 복원**해 명령 결합 오차가 재현되고 수리본은 검증을 통과함을 수치로 보여준다. NameError나 helper mock의 예외만으로 역효능이라고 쓰지 않는다.

기존 raw/success를 덮지 않는다. CLI 고정137 lexical root+제한된 fresh slug, 모든 existing ancestor native reparse/symlink 처음·출판 직전 거부, 독점 새leaf·완료JSON마지막·실소비 source/input/kit 전후핀·실제 실행 immutable bundle을 지킨다. 테스트 변이는 author/review 소유 authentic clone에서만 수행한다.

## 산출과 수용

산출은 한국어 준비/수리 보고서, replay summary/command receipts·peak, 파생 diff/anchor inventory, runtime kit/manifest·NO-SDK 표지, input/source manifest·재현 명령이다. 원부품/다른실물·전체수리안전으로 범위를 확대하지 않는다. 최종 Root CLI는 FINAL L4 PASS·정확 source/evidence핀 확인 뒤 새leaf에1회만 한다.

AC8: (1)권한/고정원자료·옛grants불재활성 (2)모델 ratio/한도/실측 q·qd·시계 provenance (3)실제 setter/readback/기록 배선·논리target/다른8DOF 불변 (4)전11160 command와원실측기록 보존/새동역학 주장이없음 (5)fail-before-setter/stop·readback오염·정확oldbug복원·단위/부호 음성 (6)실kit생성/immutable실행과다른기전 command 관측 (7)source/input/kit·namespace/완료최후출판 실효 (8)source/검토/예산/라운드/class/최종publication 일치. 비작성자 L4는 source model과 rawrow 산술을 독립 계산하고 setter callback/실제 배열·code 결속으로 반증하며, 기존 class 계보/EXH는 검수자 전속으로 판정한다. 성공은 오프라인 제어 준비물/배선 검증에 한정되며 실제 pinion tracking 개선은 NOT_RUN이다.
