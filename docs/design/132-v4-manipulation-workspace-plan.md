> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 132 — v4 다관절 큰 동작·안전 홈·집기/놓기 경로의 정적 준비

사용자 새 지시: “자그럼 이제 관절을 다양하게쓰는 큰동작도 테스트하고 안전자세를 하나 세팅해서 작은 물체하나 집고 다른장소에 놓는 시뮬하나 짜보지?” 기존131 영상 전달은 완료·그예산과6SDK 기록은 무수정 동결이다. 이번 새 목표는 simulation-only이며 CAN·RS485·포트·전원·flash·설치·네트워크/시계·Git 변경0. 현재 지시는 새 시뮬 준비와 실행을 허용하지만 이132 단위 자체는 local planning/HOST만 수행한다. 과거45분 grant를 재무장하지 않는다.

소유: src/simulation/mp18_manipulation_plan_132/{planner.py,test_planner.py,scenario.json}, outputs/mp18-manipulation-plan-132/, 본계획과Root자기인계. source3+plan1/1group=S, author implement113_c 총1500s(firstread포함)/마감검산예비300, 필수main review113_lens 총1500s/예비300/각max2/noR3. S 경량 L2 생략 L1→L3→L4, 기존 동일계열 비작성자 폴백 승인과 공통편향 기록 유지. 131author1309.265/main1153.7236574 및130/128129 예산·원장·EXH는 그대로 동결한다. 새로운 책임은 정적 작업 공간/그리퍼 물체 접촉 예정 경로이며 구수리 예산을 리셋하지 않는다.

입력은 원 models/robot-arm-urdf-v4/robot_arm.urdf SHA d55f0cbdffb8f82094b8797b187f02a3a5fd77a4a4f4272c975f21945b53135f, 원mesh/asset ledger, 원130contract9052f083… 및 실제130 runtime-inertias/기존support를 읽기만 한다. 모델·URDF·mesh·가정물성 수정0. base FK/관절·mimic은 실제URDF에서 추출, gripper의 실제 pad 내면 위치·닫힘방향·슬라이더/피니언 커플링과 swept jaw gap을 mesh로 측정한다. source limits arm velocity0.5rad/s·jaw0.02m/s·pinion2rad/s, gain64/16·현재simcap J2=12/J3=7/그외URDF cap 유지. 새로운 물체 질량은 정한 가정임을 표시한다.

목표 산출: (1) 여섯 관절 각각 여러 방향으로 충분히 움직이는 무부하 큰 동작(개별축 range 정량, 한계끝 margin, 분석적 quintic peak 이하), (2) 작업공간에서 그리퍼/로봇이 바닥·작업물과 떨어진 safe_home 자세 후보(실물 안전 인증 아님), (3) 물체에 접근→그리퍼 닫힘→20mm 이상 들기→XY150mm 이상 다른 위치로 운반→내리기→그리퍼 열기→home의 열린-loop 경로·phase/waypoint. 전체physics duration 목표90초 안팎으로 제한해 첫 원격45분 window 안에서 진단 가능하게 한다. 런타임 단계는 별도133에서 구현·검수한다.

시나리오 기준은 기존 arm 정착0.5deg/1deg_s와 sourcevelocity+.0001 guard 유지. 새다양한경로와물체 task에 맞춰 phase이름·duration·정착check time을 별도로 명시하며 과거131large34/42PASS를 새로운경로PASS로 전용하지 않는다. stage별 plannedFK+표면/자가거리/바닥여유·추가물체 중력 포함 cap check·jaw물체 충돌기하를 전수샘플링한다. Static은runtime 물리grasp 성공이 아니다. runtime acceptance는133이 실제objectpose/양jaw-contact/들림/놓은 뒤정착으로 검증하며 object teleport/weld/fixed-joint 부착으로 fake성공을 만들지 않는다.

물체/위치는 사용자가 특정하지 않았으므로 실제finger gap과 workspace에 맞는 작은 경량 box를 정한다(초기 후보 20×20×40mm/20g, 자재가정). 소형 받침은 필요할 때만 추가하고 기준바닥을 낮추지 않는다. safe_home은TCP높이와모든움직이는부품 여유를 실제 계산한후 명명한다. 이동 중 알려진 접속부를 제외한 self-collision 여유가 불충분하면검토로남기고범위를수정한다. IK없이기하적으로정당한자세를먼저찾아도되며 찾을수없다고원점/visual mesh만옮기지않는다.

조사 가설(확정값아님): J4/J6의원래고정Rx를상쇄하는관절값은각각−15deg/+10deg. forearm pitch를+5deg에유지하는q3=−15−q2, q5≈60deg는gripper tool z를수직아래로맞출후보(실URDF/FK 검산필수). q2≈−7deg에서lower/−40deg에서lift, J1−25→+25deg로source/target를만들면XY분리될수있다. 수직pick의높이한계가낮을가능성때문에ground위높이40mm경량box나실측후다른크기를선정한다. safe_home예비[0,−25,−25,−15,45,10]deg와변형큰동작은실측가설일뿐FK/지면/cap/selfgeometry필터로결정한다. 계산값을손으로확정하지않는다.

기계가독 scenario.json은SI q_rad(원joint명), opening_m/slider_q_m/pinion_q_rad, durations120Hz정수step, 정착checkpoints, 6joint expectedranges, safe_home/source/target/lift TCP poses, object dimensions/mass/friction assumptions, acceptance thresholds와geometry provenance를 포함한다. planner는같은scenario검증 API를 제공해133이사용한다. 추가의존성설치없이현재printforgevenv numpy/scipy/trimesh 활용가능; runtimeSDK imports/SSH0. 최소8AC+5attack범주의HOST로 실제132planner/JSON배선 검증, typo/기하gap폭/닫힘부호/mimic/경로속도/한계/바닥/caps/false static grasp승격/Sourcepins를 공격한다. 관측 실패를PASS로표시하지않는다. class원장·다음DISTINCT2의책임scope와충분SOURCE_EXH threshold를검토자가선언하며old원장reset0.

Root는계산결과와 SourceF/L4를확인후133runtime engine을이정의에연결해 실제시뮬을실행한다. 생산132파일만새로만들고 원파일·사용자모델링/공유문서타인절은보존한다. F/HOST/측정한geometry/미확정사항과총누적rawclock로고정한다.
