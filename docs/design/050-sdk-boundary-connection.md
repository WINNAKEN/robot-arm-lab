> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 050 — 단일 격리 진입점·SDK 초기화·IsaacLab 실제 연결

2026-10-28 사용자 「SDK 초기화랑 검증 실행 경계를 새로 설계…모듈 검색 경로와 실패 종료코드 문제부터 해결하고 IsaacLab 연결까지 검증」의 새 착수 권한이다. 047/048/049는 무수정 동결한다. provenance accepted5/EXHAUSTED, physical-frame accepted3/EXHAUSTED와 모든 이전 미폐쇄 지적·임계·예산은 그대로다. 049의 남은 native/R2 슬롯을 재사용하지 않는다. 새 경계의 수용은 기존 결과의 소급 PASS가 아니다.

## 범위와 소유

M8: 이 계획 + 신규 `src/simulation/sdk_boundary/{launch.ps1,runtime.py,native.py,audit.py,config.json,test_boundary.py,README.md}`. 증거·새 run·인계는 `outputs/isaac-boundary-v2/`. 기존 SDK·설치 prefix·원본 CAD/URDF·041 extract·043 environment·joint_frames를 읽기 전용 입력으로만 사용한다. 보호 `.dev`는 기존 hook 차단을 우회하지 않으며 이 도메인 인계를 정본으로 남긴다. 변경 전 사용자 범위/현재 기록을 대조한다.

목표는 **SDK/Lab 연결**이다. 원본 로봇 표시0의 정적 프레임·물성 대조 후 중력0·120Hz에서10번의 Lab 명시 step과 실제 engine/callback 시계·관절/LINK 관측을 검증한다. 중력 정착 28지점 재튜닝·computed-torque recipe·DirectRLEnv/Gym 과제 등록·학습은 포함하지 않는다. 질량/COM/관성/한계는 가정, 링은 보류다. 실물 보정·모터/CAN/전원·플래시·구매·전역 설치/드라이버/서비스/보안/네트워크 설정 변경은 없다.

## 1. 로컬과 원격에 동일한 프로세스 경계

049는 원격만 -I였고 실제 local verify CLI는 script directory를 sys.path에 노출했다. 050은 **모든 공개 명령(test/prepare/native/verify)을 PowerShell front door 하나로만 제공**한다. launch.ps1은 자체 `$PSScriptRoot`에서 고정 runtime 바이트/hash를 읽고, 실제 Python을 `-I -B -c <literal bootstrap>`으로 새로 시작한다. bootstrap은 고정한 runtime SHA를 검사한 바이트를 private namespace에 compile하며 마지막 결과를 반드시 SystemExit에 전달한다. Python script-file 실행·`python -m 프로젝트`·프로젝트 sys.path 추가·프로젝트 간 import는 지원하지 않는다. 각 Python 파일은 직접 실행되면 **import 전 첫 문장**에서 nonzero로 거절한다. 문서와 테스트도 이 front door만 사용한다.

runtime은 stdlib만으로 시작해 sys.flags.isolated를 확인하고 프로젝트/작업/입력 폴더가 검색 경로에 없음을 확인한다. 소스와 run 입력의 **source-defined 정확한 전체 파일 집합**, hash, run identity, symlink, source SDK/bootstrap/prefix pin을 확인한 뒤 읽어 둔 바이트만 compile한다. helper는 명시 API capability로 연결한다. host verifier는 stdlib 수학만 쓰며 numpy 등 framework import 자체가 없다. front door의 코드 폴더에 미등록 파일이 추가돼도 실행 전에 거절하거나 검색되지 않아야 한다. OS/PowerShell/선택 Python/기존 SDK 전체 및 전역 site-package의 보안 봉인을 주장하지 않는다.

원격 실행도 raw stock Python -I/-B의 호스트 고정 literal root다. .bat가 암묵적으로 PYTHONPATH를 조정하는 데 의존하지 않는다. 실행·export·로컬 verify까지 같은 권위 경로를 거친다. host가 고정한 source/job hash를 사후 sidecar의 자기 hash로 대체하지 않는다. 누락 필수 항목/추가 코드/수정 root/변조 prefix는 승인 payload가 실행되기 전에 거절한다.

## 2. 공식 SDK 초기화의 명시 실행

현재 읽기 전용 실측: SDK `6.2.0-rc.14+release.52805.02189a84.gl`, Kit0. `setup_python_env.bat`는 SDK site만 PYTHONPATH에 추가하고, site/sitecustomize.py가 SimulationApp/Kit/python_packages 경로와 DLL 디렉터리를 설정한다. -I 이후 단순 sys.path append는 이 초기화를 실행하지 않는다.

050 config는 **실제 바이트**로 회수한 SDK bootstrap pin을 고정한다: sitecustomize SHA `23e66d04b602b9eb316fcf12d2ae4af381ea2c7a2dc12afe018cc41943e2efeb`, setup env SHA `e1e4e6a0600760ee324f7d320d3569f08a7a391ef49667b5dc7c4fdd4a1f96ac`, python.bat SHA `ead7a729c2c9d37a04f11c40e754e1f814127986e14d32953fcefc09d95d9871`. 설치 prefix/job/wheel/39,919-file seal은 048 설치 사실의 source pin을 그대로 사용한다. 가변 성공 marker를 설치 권위로 읽지 않는다.

native는 bootstrap 파일과 SDK VERSION·prefix 전체를 먼저 검증한다. ISAAC_PATH/EXP_PATH/CARB_APP_PATH 및 SDK site PYTHONPATH를 이 프로세스 안에서 정해진 SDK root로 설정하고, 검증한 **공식 sitecustomize 바이트**를 명시 private namespace에서 실행한다. 그 결과의 경로는 SDK root 아래인지 검사하고 초기화 namespace/DLL 수명을 종료까지 유지한다. 이후 승인 prefix를 추가하고 실제 isaacsim provider가 SDK root 아래임을 확인한 뒤 SimulationApp을 생성한다. IsaacLab/Torch/Warp/Gym/RSL의 실제 버전·origin 및 CUDA13 tensor sum6은 같은 native 프로세스에서 관측한다. Lab physics backend는 PhysX/cpu, SDK/Lab 실측 호환을 공식 GA 표로 대신하지 않는다.

## 3. 결과와 종료코드의 단일 소유

SDK worker는 정상/예외/close 실패에서 명시 int code를 돌려준다. 실행 root는 그 code를 **그대로 SystemExit**에 전달하고 front door/SSH/parent supervisor도 원 child code를 보존한다. 예외를 기록한 뒤0을 돌려주거나 반환값을 버리는 호출은 없다. 첫 실패는 primary error로 보존하며 cleanup 오류는 별도다.

SimulationApp fast shutdown이 프로세스를 종료할 수 있으므로, app.close 직전에 원자료 파일 hash와 terminal status/code를 기록하고 **현재 code를 close(exit_code=code)에 전달**한다. close가 반환하면 반환/오류도 기록한다. 최종 소비자는 terminal 완료자료와 실제 parent의 PID/exit 기록이 모두 일치해야 성공이다. app 생성 전 실패, app 생성 후 실패, 수집 후 close 실패, child 강제 nonzero/timeout/불완전 자료는 모두 nonzero/FAILED다. exit0만으로 수용하지 않으며 원자료 FAILED를 덮지 않는다.

standalone stdlib supervisor는 새050 전체 root의 영속 원장과 exclusive lock으로 author native **최대2번/각600초**를 예약 후 실행한다. SDK import 전 실패도 소비한다. 기존 Kit가 있으면 예약된 시도는 실패로 남기고 건드리지 않는다. timeout은 해당 소유 PID tree만 정리한다. 이미 terminal이 있는 run을 재실행하지 않는다. 두번째는 측정된 SDK/API/수집 경계 오류의 최소 수정 확인에만 쓰고 성공 반복·gain 후보 탐색은 없다. wrapper 전송이 끊겨도 재실행하지 않고 기존 run 자료만 회수한다.

## 4. 실제 연결의 관측과 소비

새 run에 041 USD, 원본043의 pre-play complete static.json, CAD kinematics, assumptions, extract/environment/frames helper를 source SHA로 고정한다. consumer가 새 producer snapshot에서 expected를 만들지 않는다. 기존 prefix/SDK/CAD는 수정하지 않는다.

Lab SimulationContext를 실제로 생성하고 원본 USD를 /World/Robot에 reference한다. 원래7개 충돌 proxy와 environment를 관측하며 native PD0/force cap `[3,6,5,2,2,1]Nm`만 설정한다. 관절 목표나 effort 운전 명령을 보내지 않는다. pre-play stage에서 **몸체7개/관절 양쪽 local frame/axis/body relationships/COM/principal/관성/전체 collider owner/local basis/size/enabled/단위/default/root/floor/probe/environment**를 모두 저장하고 고정 원본과 완전 schema·수치 비교한다. source-static의 runtime-only contact_mapping/probe_runtime_mass는 명시 별도 runtime 관측이며 몰래 무시하는 source 필드가 아니다.

sim.reset으로 SDK를 초기화한 뒤 실제 runtime mass/localCOM/full inertia/principal, named DOF순서/PD0/cap, baseline q/qd/LINK poses를 읽는다. 가정의 mass tensor를 실제 값으로 바꾸지 않고 원본 가정과 일치함만 검사한다. 그 후 timeline playing의 Lab sim.step(render=False)만10회 요청한다. 매행 Lab count·engine count/time·float32 PHYSICS_POST_STEP count/time·읽기 전후 step·q/qd·LINK/probe pose를 기록한다. baseline 포함11행,120Hz/각1step/연속시계/독점읽기 및 원본 CAD FK와 양쪽 joint closure·signed axis를 전 행 검사한다. 표시0 오차·속도도 관측하되 중력0/무명령 연결 시험이지 중력 정착 수용이나 장치 영점 보정이 아니다.

static comparison은 전체 원본 frame fields를 검사하고, runtime tensor는 동일 관성을 나타내는 principal-axis 부호 동등성만 허용한다. 원래 SI·frame수치 허용치를 넓히지 않는다. 049의 full field 개념/수학은 내용 자산으로 재사용 가능하지만 **unsafe entry/old verify CLI/native worker는 호출하지 않는다**. physical-frame3/provenance5 소진을 취소하거나 새 source 이름으로 계수를1부터 세지 않는다.

설치 wheel의 PhysxManager는 legacy SimulationManager를 patch/stub할 수 있으므로 그 클래스의 전역 step API를 관측 근거로 쓰지 않는다. **실제 engine step은 PhysX의 `subscribe_physics_on_step_events(fn, False, 0)` post-step 구독에서 센 baseline 이후 event index**이며 전역 절대 count로 표시하지 않는다. engine time은 `omni.physx.get_physx_interface().get_simulation_time()`, 요청 count는 Lab의 get_physics_step_count다. callback count와 engine event index는 같은 물리 구독에서 나온 한 관측이며 독립 센서 둘이라고 세지 않는다. 이 구독은 reset/SDK초기화 이후 걸고, 각 step의 실제 post event1회/float32dt와 엔진 시간1/120·Lab요청1·읽기중불변을 대조한다. [공식 PhysX API](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/107.3/extensions/runtime/source/omni.physx/docs/api/python.html)의 pre_step=False 계약과 실제 설치 wheel 소스를 확인했다. 실제 API 부재/다른값은 실패로 기록하고 검증값을 만들어 넣지 않는다.

## 5. 검증과 검토

실제 front door의 양성 경로와 같은 입력에 붙인 원래 local numpy.py·동명 package·cwd shadow·누락 core/manifest·수정 root·변조 SDK bootstrap/prefix의 반례를 host에서 검사한다. 직접 .py 실행 거절도 첫 import 전에 sentinel이 실행되지 않아야 한다. header text 존재 검사가 아니라 실제 process 결과/marker를 대조한다. old return-discard bug를 정확히 복원한 반대 대조가 종료코드 시험에서 실패해야 한다. app 생성 전/후·close return/raise/강제 exit·partial capture를 실제 wrapper/lifecycle에서 검사하고 mock은 SDK 성공으로 표기하지 않는다. 정상 complete fixture가 소비자 PASS여야 변조 거절에 credit을 준다.

complete positive fixture의 body 삭제/side1=[99,0,0]/COM/principal/collider owner·basis·enabled/마지막 step 변조·PID/exit 불일치를 재봉인해도 실제 소비자가 거절해야 한다. 호스트는 초깃값 및 전체11행 검사를 확인하며 native 성공의 대체가 아니다.

L2/L4 각각최대2, M 검수 단위45분. AGENTS→DEV_PRINCIPLES의 비작성자 검토를 위해 기존 urdf_review/motion_completion_review만 재사용하고 구현 worker를 만들지 않는다. 이전 외부 계열 hook 차단을 우회/재시도하지 않으며 같은 계열 fallback 잔여를 기록한다. L2는 구조가 모든 공개 진입점을 덮는지와 기존 소진 접근의 단순 연장인지 명시 판정한다. L4는5카테고리·원래 반례·실제 결과를 읽고 결함 합집합/계보 연속성/착지를 판정한다. 같은 class 새 반례가 다시 수용되면 기존 충분 임계가 이미 발동했으므로 **추가 라운드로 회복하지 않고 BLOCK/동결**한다. 별도 오류 전파 결함의 첫 수리는 기존 원장과 구분하며 기존 임계를 완화하지 않는다.

native는 host 경계/consumer 대조를 마친 뒤 첫1회만 진행한다. 최종 성공은 full static/runtime/11frame·모듈/GPU/Lab 실제 manager·실제 completion/exit/PID·독립 검토를 모두 만족해야 한다. 부족하면 FAILED/NOT_REACHED/BLOCK을 구분해 남긴다. 결과·해시·제한·이전 실패/소진·최종 process 관측·다음 범위는 도메인 인계에 저장하고 소유 범위만 로컬 commit한다. push/배포는 하지 않는다.
