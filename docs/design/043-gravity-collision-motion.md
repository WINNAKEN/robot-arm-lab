> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 043 — 중력·충돌 활성 6축 동작 검증

2026-10-28 사용자 후속 요청: 같은6축 동작을 중력·충돌 상태에서도 검증하고 짧은 영상 보존. 042 완료/실패 원본과 예산을 열지 않고 새043 namespace로 수행한다.

## 권한·소유·유한 예산

다른 노트북 isaacpc의 기존6.2 RC/PhysX CPU만 사용한다. 설치·서비스·네트워크·드라이버 변경 없음. 질량/COM/관성/마찰/effort/기계 한계는 가정, 실물 보정·모터·CAN·플래시·구매 없음, 링 검증 보류. 원본CAD·URDF·042/041 코드·결과는 읽기 전용이다. 소유는 `src/simulation/contact_motion/`, `outputs/isaac-contact-v1/`, 이 계획. 이전 보호 훅의 `.dev` 쓰기 거절을 우회하지 않고 새 도메인 결과에 인계한다.

M급 단일043 파이프라인: core.py, environment.py, runtime.py, driver.ps1, verify.py, render.py, test_contact.py, config.json, README.md와 계획(10파일). 042 sampler·frame/clock/completion 검사·render primitive를 hash-bound 의존성으로 재사용한다. L2/L4 각max2, author 실제run max2×600초, 독립 새runtime0(원자료 독립검토), 재시도는 진단된 구현/API/환경 수정1회만. 수용치/토크/경로를 바꾸며 성공까지 반복하지 않는다. 실패도 결과이며 전체 동작을 수용하지 못하면 이유와 실패 영상을 보존한다.

레포 진입점이 요구하는 독립 L2/L4를 기존 비작성자 검토자로 수행한다. 외부 bridge는 이전 session wrapper lint hook에 차단된 경로이므로 이번에 read-only 가용성1회 확인, 불가 시 동일계열 비작성자 잔여 위험을 기록하고 보호 규율/훅을 변경하지 않는다. 새 작업자 병렬 구현은 하지 않는다.

## 같은 동작·중력 보상

042의 원래 program.json/6780steps·6781samples·56.5s·28checkpoint·각축±5°·A/B·최종0을 그대로 사용한다. PD gain/position·velocity 목표와 가정 총 effort cap `[3,6,5,2,2,1]Nm`도 유지한다. 중력은 `[0,0,-9.81]m/s²`.

가정 질량에서 sampled checkpoint 중력 토크 절대최대는 `[0,4.833465792,2.699788190,0.074648670,0.397585932,약0]Nm`. 같은 low-gain PD만 사용하면 중력 정상오차가 생기므로 actual 이전step LINK pose·localCOM·mass와 joint body0/localframe에서 `tau_ff=-Σ axis·((COMworld-anchor)×mass*g)`를 계산해 매step set_dof_efforts로 더한다. 목표/expected FK를 actual 관측으로 쓰지 않는다. ff는 총cap에서 clamp하고 PD drive maxEffort는 `cap-abs(ff)`로 설정해 합의 보수적 상한을 유지한다. 실제 외부 command readback와 drive cap readback을 기록·대조한다. measured actuator torque라고 표현하지 않는다. 총cap/gain을 올려 PASS 만들지 않는다.

## 충돌 설정과 작동 대조

원래7개 assumed AABB box proxy를 켠다. PhysxArticulationAPI selfCollisions=True. 각 revolute joint collisionEnabled=True로 명시하고 직접 연결된6쌍만 FilteredPairsAPI로 제외한다. 이 연결부 형상 중복 제외와 비인접 self-collision 비활성은 다르다. 필터 목록을 정확 검사하고 추가/전역 제외를 거절한다. 사전 q0 및28checkpoint OBB SAT 조사에서 비인접 겹침0, 최소 boxZ=0(Base bottom)이었다. 실제 경로 전체와 접촉력을 별도로 검사한다. AABB proxy의 결과가 실제 속 빈 CAD 표면/링 간섭 인증은 아니다.

고정 바닥 Cube: 중심(0,0,-.05)m, 크기(4,4,.1)m로 topZ=0. 접촉 재료 staticfriction.6/dynamic.5/restitution0은 가정이다. 떨어지는 별도 probe Cube: 중심(-.6,0,.2)m, 한변.05m, 질량.1kg, 초기자세identity. 로봇 밖에서 같은 중력/바닥/충돌의 실제 작동을 확인한다. 로봇7body+probe1의 contact tensor를 ground+7body+probe filters로 읽는다. ContactReportAPI threshold0과 max_contact_data_count 고정. 누락/overflow/미지원 API는 빈 접촉으로 조용히 통과시키지 않는다.

probe는 실제 떨어져야 하고(초기보다 Z최소 .05m 감소), 1초후 중심Z=.025±.002m, 양의 floor normal force>0.1N 관측을 요구한다. 전체 actual robot 비인접/arm-floor contact force는1e−3N 초과가 있으면 contact-free 동작 실패다(Base-floor는 고정 장착면으로 별도 기록). 자기/adjacent filtered pair의 contact도0이어야 한다. 이는 충돌 엔진 켜짐의 양성 작동 확인이며 마찰·접촉하중 성능/충돌회피 시험은 아니다.

## 실제 관측·모든 frame·판정

042의 paused manual step 단일 소유자·tensor fallback 금지·각 step counter/time/POST_STEP·동일step actual q/qd/7 LINK를 유지한다. engine double=index/120±1e−6, callback float32=index×float32(1/120)±1e−9 및 각 증분/count1. 종료는 bound pre-close summary + actual exit0, 오류는 close전 FAILED/code1. old sources/새script/config/input/원자료/source job/PID를 결속한다.

기존 모든 frame inventory(world/root/7LINK/fixed양끝/6revolute양끝·signed axes/7localCOM·principal tensor/7collider local basis)는 그대로 검사한다. 여기에 floor local/world placement·scale/material, probe body/local collider·COM·inertia·principal frame/actual world pose, 6filter body 경로와 contact sensor/filter 인덱스 매핑/힘의world축을 추가한다. probe도미지원/누락을 skip하지 않는다. 전체 실제actor8·collider9만 허용한다. 예상frame을 관측에 덮어쓰지 않는다.

원래 지점 각도≤0.5°·속도≤1°/s, FK(actualq) 대 LINK/anchor≤1mm·행렬/축≤1e−3, 최종0은 STOP/reset 전. 기준을 완화하지 않는다. 충돌·토크·probe 확인과 042 motion/frame/clock 검사를 구분한다. 원자료 완주/실제 exit가 있어도 이 중 실패하면 `DYNAMICS_FAILED`로 정직하게 보고한다. 불완전자료나 hash/protocol 오류는 `INVALID_EVIDENCE`로 구분한다.

host 의미검증: 중력 토크 부호/virtual work·회전COM·zero-g·cap총합, nonadjacent OBB/SAT/가짜frame, gravity/collider/selfCollision/filter/material/probe/frame/force행렬 tamper, contact0·누락probe·badindex/overflow, clock/source/completion 회귀. 합성 PASS는 runtime PASS가 아니다. 코드 작성자와 최종 검토자를 분리한다.

기존 physical-frame-coverage accepted instance2→다음 독립실측+작성자수용 동일누락1이면 즉시 verification approach EXHAUSTED 임계 유지. 새043으로 초기화하지 않는다. 기존039/firmware/startup/SB/PA/terminal/링 이력도 유지한다.

## 전달

실제 관측 LINK로12초 MP4(56.5s 시간압축)를 만들고 중력/충돌 상태·접촉작동 확인·검증PASS/FAIL·가정 물성·실물 미승인 표시. Isaac viewport 직접 녹화와 구분한다. 실패 완주라면 실패 라벨로 영상 보존, 불완전이면 관측 구간만 표시하며 전체 완료 사칭 금지. metadata/frame QA·원자료·해시·독립최종결과·실행 안내·로컬 commit/push없음.
