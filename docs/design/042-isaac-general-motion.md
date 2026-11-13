> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 042 — Isaac 6축 일반 동작과 재사용 코드

2026-10-28. 사용자 「끝나면 시뮬로 전체적인 일반동작을 구현해보고 그걸 토대로 코딩들도 준비해놔」에 따른 후속 범위다. 041 정적 가져오기 종결/실행 예산을 다시 열지 않는다.

## 범위와 권한

기존 다른 노트북 `isaacpc`의 설치 Isaac 6.2 RC에서 041 실제 USD를 **새 042 작업 사본**으로 참조하고, 실제 PhysX articulation drive 목표를 보내며 q/qd/LINK pose를 관측한다. 실물 보정·모터·CAN·플래시·구매·설치·보안/네트워크/서비스 변경은 없다. 질량/COM/관성/한계/effort는 시뮬레이션 가정, 링 검증은 보류다. CAD v3/기존 URDF·041·펌웨어를 수정하지 않는다. 그리퍼·TCP·접촉 작업·정확한 하중/감속기/RL 성능을 주장하지 않는다.

소유: `src/simulation/motion/`, `outputs/isaac-motion-v1/`, 이 문서. `.dev` 셸 쓰기는 현재 Codex 보호 훅이 차단했으므로 보호 파일·규율을 우회/변경하지 않는다. 새 도메인 시험 결과는 위 outputs에 보존한다. 기존 무관한 변경은 보존한다.

## 동작과 단위

정본은 `program.json`: canonical CAD 표시 자세 대비 delta rad, q=0은 굽혀진 CAD 표시 자세다. 실제 모터 영점이 아니다. J1..J6 이름으로 매핑하고 runtime DOF 순서를 가정하지 않는다. 화면용 각도만 degree다.

- 초기 q=0 hold 1s.
- J1..J6 각각 `0→+5°→0→−5°→0`, 이동마다 1.5s + 정착 0.5s.
- 동시 A `[5,-5,5,3,-3,3]°`, B `[-5,5,-5,-3,3,-3]°`: `0→A` 1.5s, `A→B` 3s, `B→0` 1.5s, 각각 정착 0.5s.
- 총 56.5 sim seconds. 각 이동은 quintic `10u³−15u⁴+6u⁵`, 위치와 해석적 속도 목표를 보낸다. 최고 명령 속도 약 0.1091rad/s, 가정 0.5rad/s 이내. 무한 반복 없음.
- 중력0, 모든 실제 CollisionAPI disabled, base 고정. 물리 drive force mode. 초기 가정 gains는 q0 downstream effective inertia Ieff에서 `kp=64 Ieff`, `kd=16 Ieff`(wn8rad/s, ζ1), torque cap `[3,6,5,2,2,1]Nm`. 이는 실제 모터 정격이 아니다. 제한/유효성 검증 후 사용한다.

## 실행과 관측

설치 소스 확인된 experimental Articulation/RigidPrim + explicit PhysX CPU 경로를 쓴다. 초기 timeline play/update로 tensor 초기화 후 pause/update, paused 확인 뒤 `SimulationManager.step(1)` 단일 소유자가 120Hz로 진행한다. 루프 안 app.update 중복 진행은 없다. 강제 tensor backend, fallback 금지. 목표 transform 애니메이션이나 매 frame set_dof_positions로 순간이동하지 않는다.

각 단계 실제 simulation time, physics step count, POST_STEP callback dt/count를 읽고 일치 여부를 검사한다. q/qd와 7 LINK pose는 같은 step에서 읽고 전후 counter 불변을 확인한다. schedule time과 실제 physics time을 별도 보존한다. 실시간 wall-clock 보장이 아니다.

전 프레임 inventory: world/root placement·m/kg/Z; Base+6 LINK; fixed joint 양쪽 local/world frame; 6 revolute 양쪽 anchor/회전/signed axis; COM와 주관성 frame; collider local frame/disabled 상태. q≠0에서는 `Rframe0 Rot(axis,qactual)=Rframe1`를 비교한다. LINK pose와 COM pose를 혼동하지 않는다. runtime COM는 LINK local, quaternion wxyz; full inertia는 COM 기준 LINK축 표현 column-major9다. USD principalAxes로 재구성한 tensor와 대조한다. quaternion 부호 등가를 회전행렬로 처리한다.

FK는 기존 `src/joint_frames/frames.py`와 kinematics 입력을 읽기만 한다. 실제 q를 FK에 넣어 LINK pose와 비교하고, target→actual tracking은 별도 판정한다. 새 실행에 기대 FK pose를 관측값으로 넣지 않는다. 041 source USD SHA256 `117d94292c75e89b201e12606eafbcf24065c537c6f8308647562f9a0679f4db`를 고정한다.

## 사전 고정 수용 기준

모든 recipe checkpoint/실제 sample/step 시간 연속성이 있어야 한다. endpoint 각도 오차 ≤0.5°, 속도 ≤1°/s. FK(actual q) 대 actual LINK 위치 ≤1mm, 회전행렬 성분 ≤1e−3. signed individual positive/negative 반응·runtime DOF 유일한 J1..J6 mapping 확인. base fixed와 양쪽 joint anchor/회전 closure도 같은 동적 허용 내. runtime mass/COM/inertia는 source float32 보존 허용(mass1e−5kg, COM1e−5m, tensor1e−7kg m²), world units/up-axis와 actual collider disabled는 정확 판정한다. clock increment1/120s 오차1e−6s, callback/step delta 각각1. 최종 q0와 저속을 STOP/reset **전에** 실제 step에서 관측한다. 일부 checkpoint나 reset 후 q0로 전체 통과시키지 않는다.

첫 실제 6.2 관측에서 callback dt는 float32(1/120)=0.008333333767950535, engine clock는 double 기준으로 확인됐다. 6780번 누적 차이2.946704626e−6s는 정확한 표현 반올림 합이다(`outputs/isaac-motion-v1/evidence/attempt1-clock-diagnostic.json`). 서로 다른 표현의 누적값에 일괄1e−6을 적용하지 않는다. engine 경과는 index/120에1e−6, callback 누적은 index×float32(1/120)에1e−9로 각각 독립 검사하고, 각 engine 증분1e−6·callback 증분1e−9와 count1을 유지한다. 동작 시간/속도/좌표 수용치를 완화하는 변경이 아니다. 첫 실행은 exit124라 계속 FAILED이며 이 진단으로 수용 승격하지 않는다.

## 코드·출력과 실패 경계

`core.py`(유한 recipe/샘플러/가정 gain), `runtime.py`(원격 supervisor+실제 실행/원자료), `verify.py`(독립 소비 경계), `driver.ps1`(준비/전송/실행/회수), `test_motion.py`, `program.json`, `remote_config.json`, `README.md`와 이 계획으로 M급 단일 파이프라인을 준비한다. 선택적 실제 telemetry replay는 별도 산출물이며 Isaac 렌더로 표시하지 않는다.

각 GUID job에 source/config/input hash·runtime version·실제 PID/exit/time·로그를 보존한다. source/관측 파일 manifest로 결속하고 consumer는 source 변경/누락/실패/불완전 시 FAILED. worker는 dependency import 전 BUILDING 시작, 실패는 app.close 전 FAILED 저장·nonzero exit를 명시한다. fast shutdown 뒤 후속 쓰기에 의존하지 않는다. supervisor는 자기 자식 PID만 timeout 종료하고 실제 exit를 기록한다. exit0만으로 PASS 불가. 기존 Kit 프로세스 있으면 새 실행을 보류한다.

첫 실행은 앱 전체 cleanup(fast_shutdown=False)을 사용해 동작 자료를564초에 수집했으나 stage close 뒤 app.shutdown에서600초 제한을 넘겨 exit124다. 원본 로그/자료/실패를 유지한다. 실행2에서는 설치6.2의 공식 기본 fast_shutdown=True와 명시적 close(exit_code=code)를 사용한다. 완료 소비자는 `DATA_CAPTURED/CLOSING_APP`의 summary 해시·같은 runtime/PID·전체 input/output 해시·실제 exit0를 모두 요구하며, 호출 뒤 도달하지 않는 CLOSED를 사칭하지 않는다. 일반 종료가 반환하면 기존 CLOSED도 처리할 수 있다. 실패는 close **전에** FAILED와code1을 기록한다. pre-close 성공자료만으로 수용하거나 timeout 원본을 소급 통과시키지 않는다.600초 기한·3회 예산·동작/프레임 수용치 유지.

의미 있는 host 회귀: trajectory endpoint/연속성과 속도 cap, 누락 checkpoint/DOF permutation/sign·degree-rad, frozen target echo, stale step/pose, COM 대 LINK, fixed 한쪽 frame, quaternion 부호 등가, missing input/실패 final 경계. 합성 자료 PASS는 runtime 수용으로 승격하지 않는다.

## 검토와 유한 실행 예산

L1 이 계획 → 독립 L2 max2 → 구현/host 검증 → 실제 동적 author run max3(초회+진단된 수정2, 각600s) → 독립 L4 max2. 성공할 때까지 반복/수용치 완화 없음. 독립 검토는 실제 원자료·source/프레임 consumer를 검사하며 필요 시 새 동적 runtime읽기 max1, 사전 예산에 포함한다. 기존041 import/독립SDK 실패 횟수는 그대로 종결이다.

표준 외부 Claude bridge 경로는 현재 hook의 기존 wrapper hard-coded path lint로 차단되어 invoke NOT_RUN이다. 글로벌 wrapper/보호 훅을 변경·우회하지 않는다. 별도 비작성자 협업 검토를 쓰되 외부 계열 검토 부재를 잔여 위험으로 명시한다. 외부 가용 시 전제 검토가 우선이다.

기존 모든 소진/임계를 보존한다. 특히 physical-frame-coverage 040 instance1→041 instance2이며 **다음 추가 독립 실측+작성자 수용 동일 instance1이면 즉시 검증 접근 EXHAUSTED**다. 새042 이름으로 초기화하지 않으며 남은 검토/실행 슬롯으로 같은 접근을 이어가지 않는다. 그 외039 Windows 시간/firmware/PA/terminal/startup/링 보류 상태를 바꾸지 않는다.
