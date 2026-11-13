> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 026 / JC-20261024 — CAD/코어 각도와 실제 제어 경로 연결

2026-10-24 사용자 후속 지시. 링 형상 미해결 보류, 장치 없는 구현/시험만 수행한다.

## 요구/현재 경계

025의 고정 v2/CLI에서 CAD표시deg와 core delta rad는 +1관측 일치다.021 pose_deg는 [15,-50,70,15,25,-10], q_geometric=q_delta+pose_rad. native/motor 부호를 혼용하지 않는다. 기존 ControlGate/BenchRun은 고정100pulse·speed5·acc2만 수용한다. 실제 모터 sign/감속비/원점/encoder는 미측정이고 기본 app/물리 승인false다.

새 실제 C++ 제어 진입점 BenchRun::request_joint_step은 각도 상대변위→보정된100pulse의방향→기존 BenchRun::request→ControlGate→실제 MKS codec→CanPort로 연결한다. 독립 helper만 만드는 것이 아니다. 기존 direction HTTP/웹 schema와 입력경로는 변경하지 않는다. 숫자각도 웹 endpoint/연속궤적/절대목표 위치제어는 이번 범위가 아니며 임의 현재 위치를 요청에서 받아 절대목표로 보내지 않는다.

## 소유 범위/보존

기존 bench_run.hpp에 새 진입점·불변 보정 저장·생성자 overload·영구철회 API만 추가, 같은 include경로의 joint_angles.hpp에 header-only 순수 변환과 typed calibration/relative-step을 추가한다. 기존 bench_run.cpp/control_gate/core/boot/phone/app/CMake는 무수정. src/firmware/tests/joint/의 새 실제통합시험+빌드/변형runner와 .dev/joint-control-evidence/, 본계획/최소인계만 소유한다. CAD/021/025/SB 생성결과와 기존기준파일은 보존한다. 새 API는 host와 SDK의 기존 header 경로를 공유하고 추가 linker 의존성을 만들지 않는다.

## typed 변환/승인 계약

- 절대좌표 Coordinate는 CadDegrees/CoreDeltaRadians/CoreGeometricRadians enum으로 구분, joint1..6에 대해 세 좌표를 함께 반환한다. 상대 Step은 CadDegrees/CoreRadians만 가능하며 offset을 더하지 않는다. 잘못된enum/joint/NaN/Inf/overflow는 명시 오류와 기본0출력. finite 표현가능값의 변환과 물리 한계를 구분, 임의 대칭 각도 범위를 도메인으로 만들지 않는다.
- 코드의 pose/모델revision/hash 상수는025/021의 고정 입력에서 명시 생성/대조한다. 새 시험에서 승인021 Python실제함수를 사용한 oracle벡터와 C++변환을 대조하고, pose에 임의값을 손으로 추정하지 않는다. 기준source/receipt hash를 고정하고 변경시 새 evidence 필요.
- Calibration은 기본 measured=false. 요청 인자로 받지 않고 BenchRun의 새3인자 생성자에서 축별2개를 actor private const 배열에 복사한다. 기존2인자 생성자는 미승인 보정만 갖는다. boot/profile/axis/joint에 결속하고 motor fullsteps(200또는400)·microstep16·reduction>0·dir0_joint_sign±1을 명시한다. 새로운 물리승인을 자동 설정하지 않는다. 이 struct는 신뢰된 설정측 입력이며 웹/요청 JSON에서 채우지 않는다. normal_approved=false이면 새 이동을 거절한다. CAD+1은 CAN direction0/1을 결정하지 않으며 motor 보정sign을 별도 적용한다. 기존 profile.dir0_sign은 encoder count방향이므로 joint sign과 혼용하지 않는다.
- 해당보정이 유효하고 요청axis가구성축/보정축과 같고 boot/profile/joint가일치할 때만 상대각도를 `abs(delta_rad)*fullsteps*16*reduction/(2*pi)`로 계산한다. 유한한100pulse와 오차1e-9pulse 이내일 때만 수용. 반올림/잘라내기/분할/임의 pulse확장은 하지 않는다. 미승인·불일치·0·비유한·overflow·다른pulse크기는 gate intent/CAN 이동 생성 전에 거부한다.
- 정상 변환은 direction을 내부 계산해 복사 Request에 넣고 기존 request를 호출한다. 인증된caller의boot/session/seq/request/lease/ticket/axis는 그대로 전달하며 deadline/stop/normal승인/부팅토크/완료판정은 기존 소비경로를 통과한다. 새 API로 Stop을 호출하면 변환/보정조건과 관계없이 기존Stop경로를 우선 호출한다. 다른op는BadRequest. 새로운변환실패가 기존first fault/time을 덮거나Stop을 막지 않는다.

## 시험/완료

기존 실제tests/run/test_run.cpp의 Fake/Fixture를 재사용(테스트 TU에서 main명만분리)해 실제 BenchRun과codec를 통합한다. 두축별±CADdeg/±coreRad,서로반대 motor sign/reduction을 fixture로 설정해 정확한FD100pulse바이트/축/direction·관측완료와StopF7를 확인. 보정미승인/잘못된axis/joint/profile/boot/단위/NaN/Inf/0/비100pulse·세션/티켓/lease불량과Stop후요청 거부에서 추가 FD가0임을 확인한다. 실제HW보정으로fixture를표시하지 않는다.

절대좌표영점/양음/왕복·rad/deg·offset은 승인021에서 생성한 oracle로 검증. positive suite 성공 후 compiled 행동변형 3개(단위변환삭제/offset삭제/보정gate삭제)를 실제회귀가 AssertionError/FAIL로 잡아야 한다. compile 실패는 변형검출로 세지 않는다. 새 API 때문에 영향받는 기존 run/boot/runtime/phone host 회귀를 실행한다. hardware/flash/network/SDK실물은 NOT_RUN. SDK target build는 현재 단계에서 별도 실행하지 않고 모든 기존 translation-unit의 hoststrict컴파일과 header 의존성을 확인한다.

## 검토 예산/원장

L1→독립L2→L3→독립L4. L2최대2/L4최대2를 첫검토 전에 선언한다. 기존020/023 startup/result-finalization 역사EXHAUSTED·다음추가동일class독립측정작성자수용1→EXHAUSTED 임계유지(이번신규artifactgenerator는만들지않음). ring indexedgeometry 미해결보류.021math/023dependency와025serialization CLOSED이력유지. firmware first-normal-fault reason/time N+1임계불변. 검토자는class착지와재발/소진판정을명시하고동일class재발이면예산잔여와무관중단한다. 외부계열 기존중앙bridge차단NOT_RUN/우회없음,동일계열비작성자독립검토잔여위험기록. L4수용후 HANDOFF/SESSION/LESSONS/구조지도 갱신,소유범위로컬commit/push없음.

## L2 R1 처분 — 보정과 permit 수명 결속

JC-L2-R1-1을 수용한다. 요청별로 바뀌는 Calibration은 제거했다. actor 생성자에서 복사한 const 배열 외에 새 값 입력/갱신 API를 두지 않는다. 따라서 Arm/Ticket 이후 외부 원본 보정 객체의 sign/ratio/measured 변경은 실행 의미를 바꾸지 않는다. 활성화 여부는 별도 영구 철회 latch로만 false가 될 수 있고 같은 actor에서 복구할 수 없다.

`revoke_joint_mapping()`은 latch를 세운 후 begun/active actor이면 기존 `enter_stop(Fault::Profile)`을 호출한다. 기존 정지 경로가 gate snapshot revision/stop을 갱신해 reserved/pending intent를 폐기하고 버스를 격리한다. request accepted와 poll의 take_intent 사이 철회 시험에서 FD0/F7정지를 확인한다. 이미 제출/배달된 CAN을 소급 취소한다고 하지 않는다. 기존 첫 fault/time은 enter_stop의 보존 경로를 따른다. begin 전 철회는 장치 호출 없이 latch만 세우고 이후 angular진입은 계속 거부한다.

보정 변경은 기존 actor를 정지 종결하고 CanPort의 단일 owner를 해제한 뒤, 신뢰된 설정측이 새 고유 boot/profile identity와 보정으로 새 actor를 구성하고 기존 boot/maintain/torque/lease 절차를 다시 밟는 별도 수명이다. 현재 프로젝트의 신뢰된 boot identity 유일성 전제를 유지하며 전역 actor registry나 hot swap을 만들지 않는다. 같은 boot/profile을 다른 보정으로 재사용하는 것은 이 계약의 설정측 위반이며 지원 API가 아니다. 현재 actor에는 보정 교체 기능 자체가 없다. boot evidence의 Profile 구조는 바꾸지 않고 별도로 저장된 보정이 생성자 boot/profile과 같아야 새 angular명령을 허용한다.

시험에는 Arm/Ticket 후 원본보정변경 무영향, 예약 Move 후 철회 FD0, 철회 후 재요청/재begin 불허, 기존 firstfault/time 보존, 새boot actor의 구permit 거부를 추가한다. 기준fixture는 기존 실제Fake/Fixture를 상속/재사용하되 새 생성자용 Fixture를 구성해 실제 경로를 통과시킨다. const배열 초기화를 위해 기존2arg 생성자에 위임하는 새3arg 생성자를 header에 정의할 수 없으면 작성자가 원래 생성자 초기화와 같은 overload를 header에 정의(동일port/profile/gate/stop초기화)하여 기존cpp는 무수정으로 유지한다. L2 R2가 마지막2/2다.
