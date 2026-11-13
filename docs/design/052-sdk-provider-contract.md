> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 052 — SDK NumPy 단일 제공자·필수 관측 계약·단계당 단발 실행

2026-10-28 사용자 최신 명시 결정: 재부팅하지 않고 SDK NumPy로 통일, 접촉 매핑 검증과 단계별1회 제한 구현, IsaacLab 연결 확인. 실물 보정·모터/CAN/전원·플래시·구매·학습·링 검증·SDK/전역 패키지/드라이버 재설치·서비스/보안/네트워크 변경은 없다. 물성은 가정이다. 047~050 동결/실패/남은 슬롯은 불변이며 새052는 이를 재시도하지 않는다. physical-frame accepted4 EXHAUSTED, provenance accepted5 EXHAUSTED, conditional-second eligibility accepted2(다음추가독립실측·작성자수용1이면 EXHAUSTED 충분)를 연속 유지한다.

## 분할과 소유

전체 L 작업을 두 M 단위로 나눈다. 구현자는 root이며 검토자는 기존 비작성자만 사용한다.

- **052A 실행/제공자**: 신규 `src/simulation/contract_v3/{launch.ps1,runner.py,providers.py,test_runner.py,README.md}`와 이 계획(M6). SDK NumPy/SciPy 우선 부팅·PS literal-I-c 경계·실제 exit 전달·두 고정 단계별 단발 원장을 소유한다.
- **052B 관측/소비**: 신규 `src/simulation/contract_v3/{obligations.json,model.py,verify.py,test_model.py,config.json}`와 이 계획(M6). 완전 source-static·가정 물성·실제 접촉 인덱스/샘플·11행 관측을 하나의 source 계약으로 생산/검증한다.
- 증거·원자료·현재 상태·인계는 `outputs/isaac-contract-v3/`. MP9 계획051/CAD/그리퍼, .dev, 기존 펌웨어/모든 이전 simulation source는 읽기 전용이다. 보호 .dev hook을 재시도/우회하지 않고 도메인 인계에 종료 상태를 남긴다. 각 M 기계검사 후 별도 L4, L2는 통합 계획에 대해 최대2회, L4는 A/B 각각최대2회·45분이다. 구현 worker는 만들지 않는다.

## 실측 원인과 대안 소스

050 stderr에서 prefix NumPy2.5.4 `__init__.py`가 SDK NumPy2.3.1 `fft/_pocketfft_umath`를 읽어 DLL load failure가 난 경로를 확인했다. 실제 SDK METADATA: NumPy2.3.1/SciPy1.17.0; prefix는 NumPy2.5.4/SciPy1.18.1. 현재 Kit0이며 재부팅은 수행하지 않는다. 이는 혼용의 직접 증거이지 모든 DLL 문제 원인 식별이나 재부팅 무효의 일반 증명이 아니다. [NumPy 공식 진단](https://numpy.org/doc/stable/user/troubleshooting-importerror.html)은 Python/NumPy 버전과 PATH/PYTHONPATH 확인을 요구한다.

새 방침은 **SDK 제공 NumPy/SciPy를 먼저 실제 import/FFT/Rotation 검사하고, SDK 앱 생성이 끝난 뒤에만 학습 prefix를 검색 경로 맨 뒤에 추가**하는 것이다. prefix를 NumPy 앞에 넣거나 SDK 앱 전 Gym/Torch/Lab로 prefix NumPy를 먼저 import하지 않는다. 기존 설치 파일은 바꾸지 않고 재설치/복제 overlay도 없다. SDK bootstrap3파일·VERSION/원048 prefix 전체 seal은 이전 source pin을 유지한다. 실제 numpy, numpy.fft, `_pocketfft_umath`, scipy.spatial.transform과 그때까지 로드된 모든 numpy/scipy 모듈의 파일 origin을 SDK의 각 고정 subtree에 한정한다. 버전도 SDK2.3.1/1.17.0과 일치해야 한다. source metadata만으로 DLL 성공을 표시하지 않는다.

SDK 초기화는050에서 실측된 공식 sitecustomize 바이트 private 실행 방식을 내용 자산으로 재사용한다. 모든 공개 test/prepare/run/verify와 원격 worker/export는 PS front door→raw Python **-I -B -c**의 literal hash root로만 실행한다. 직접 .py는 첫 import 전 nonzero 거절, 프로젝트 코드 검색/import 없음, 정확한 source/payload 집합·hash·link·config/source-reference 검사를 완료한 cached bytes만 private namespace에서 compile한다. 로컬 consumer와 원장 검사는 stdlib만 사용한다. 모든 worker 결과는 literal root SystemExit→실제 parent exit→SSH/PS까지 보존하며 FAILED가 exit0으로 승격되지 않아야 한다. SDK/OS 전체의 보안 봉인을 주장하지 않는다.

## 두 단계, 각 정확히 최대1회 — 재시도 분기를 제거

고정 프로토콜은 `sdk_preflight`와 `robot_connection` 둘뿐이다. 전자는 SDK 공식 bootstrap/NumPy FFT·SciPy Rotation을 검사하는 **앱 없는 DLL 진단 프로세스**이고, 후자는 실제 SimulationApp/Lab/우리 로봇/접촉 뷰/10step을 생성하는 별도 목적이다. 성공한 로봇 실행을 반복하거나 실패한 단계에 새GUID를 붙여 다시 실행하는 기능이 없다.

052 원격 root에 단일 영속 ledger와 exclusive lock을 둔다. **stage별 최대 예약1건**, source/config 버전이 바뀌어도 이052 원장 안에서 회수를 초기화하지 않는다. 예약은 Popen 전 저장하고 시작 실패·timeout도 소비한다. `sdk_preflight`는 ledger에 그 단계가 없을 때만 가능하다. `robot_connection`은 자신의 예약이 없고, prior SDK 단계의 실제 terminal/exit/provider 원자료가 정상이며 run/job/source-input signature/SDK provider 계약이 현재 동일 입력과 결속될 때만 가능하다. SDK 실패/미완료/누락/exit비정상/다른 input이면 로봇 단계는 거절한다. 이 prereq 소비는 단순 success bool이나 외부 marker가 아니라 저장된 원본 job/hash/PID/exit/provider 값의 교차 대조다.

단계별600초 supervisor, wrapper는 더 긴 유한시간이다. 기존 Kit가 있으면 건드리지 않고 예약된 실패로 남긴다. timeout은 자기 PID tree만 정리한다. 한 stage가 실패하면 그 stage 수리 재실행은 없다. 자동/조건부 second retry가 없으므로050의 '이전 성공이어도 새 run 허용' 분기 자체를 제거한다. 두 모드 외 이름·중복 reservation·잘못된 ledger는 실행 전에 거절한다. SDK-only 성공 뒤 robot 실행은 사전 선언된 다른 목표/관측 계약의 정상 진행이며 성공 반복으로 세지 않는다. 전송 오류면 기존 실행 자료만 회수하고 자동 재실행하지 않는다.

## 052A SDK 단일 제공자와 실제 종료

SDK preflight는 prefix를 노출하지 않은 새 -I 프로세스에서 고정 SDK paths로 공식 초기화를 수행한다. NumPy2.3.1 실제 rfft([0,1,2,3])의 `[6,-2+2j,-2]`, SciPy1.17 Rotation identity와 모든 해당 origin을 저장한다. FFT 확장 DLL까지 실제 import되지 않으면 실패다. SDK 배포 경로 검사와 숫자 대조를 stdlib consumer도 수행한다.

Robot worker도 동일 SDK 숫자 검사를 먼저 하고 SimulationApp을 만든다. **그 후** 봉인 대조한048 prefix를 sys.path 끝에 추가한다. prefix의 IsaacLab3.0/Torch2.11cu130/Warp1.17/Gym1.4/RSL5.5.1 version/origin을 실제로 확인하고 CUDA13 tensor sum6을 수행한다. 이미 다른 framework provider가 있으면 숨기거나 sys.modules를 지워 성공시키지 않고 실패로 기록한다. Lab를 읽고 난 뒤 모든 numpy/scipy loaded origins와 FFT를 다시 대조해 혼용 재발을 검출한다. 원 prefix NumPy/SciPy는 읽기 전용으로 남지만 이 프로세스의 provider로 수용하지 않는다.

설치 소스 추가 대조에 따른 제공자 명확화: SDK 자체가 `C:/isaacsim/extscache/omni.warp.core-1.17.0+wx64/warp`를 공개 모듈로 로드하며 extension.toml과 이전 실제 로그 모두1.17.0이다. **Warp는 이 정확한 SDK subtree/실제 module.__version__1.17.0을 canonical로 사용**하고 prefix의 동명 Warp로 덮어쓰지 않는다. 위 prefix framework 목록 중 Warp만 이 명시 SDK 제공자로 대체한다. 다른 framework는 그대로 prefix/version을 검사한다. SDK tensor view와 Lab가 이미 쓰는 동일 Warp 객체를 유지하는 결정이며 임의 SDK 경로/다른 버전을 허용하는 완화가 아니다. 원자료 `evidence/sdk-framework-source.json`을 보존하고 L2 R2에서 이 제공자 계약을 최종 확인한다.

worker는 app 전/후 예외와 close 오류를 구분해 첫 실패·code를 기록한다. app.close fast exit 전 terminal과 원자료 inventory/hash를 쓰고 현재 code를 close(exit_code=code)에 전달한다. close 반환/오류도 기록하며 parent의 실제 종료와 함께 소비한다. 원자료 FAILED/nonzero/partial은 성공이 아니다. source 실패 exit, host wrapper failure와 실제 SDK API 미도달은 별개로 보존한다.

## 052B 필수 관측 의무를 단일 source 계약으로 실행

050처럼 producer/consumer가 각각 필드를 골라 누락하는 방식을 버린다. source `obligations.json`은 **정확한 네 facet `static`, `bodies`, `trace`, `contact`의 순서·필수 schema**를 선언한다. runtime의 고정 필수 집합과 일치하지 않는 계약/빈 목록/unknown/optional 의무는 실행 전에 거절한다. model의 COLLECTORS와 verify의 VALIDATORS는 이 집합과 정확히 일치해야 하며 두 쪽 모두 계약의 모든 항목을 순회한다. producer는 각 collector의 실제 값을 담은 뒤 전체 facet 완료를 확인해야 terminal 완료에 도달한다. consumer도 누락/추가 facet와 schema를 먼저 거절하고 네 validator를 전부 호출한다. coverage count/hash만으로 개별 값의 의미 검사를 대신하지 않는다.

- **static**: 041USD와 원043 pre-play golden/CAD/assumptions를 source SHA 고정. 원본 7LINK/고정+6revolute 양쪽 frame/relationships/axis, local COM/principal/관성, 7collider owner/localposition/basis/size/enabled, units/default/root, floor/probe/material/필터/전체 source environment를 저장·대조한다. golden의 runtime-only contact_mapping/probe_runtime_mass는 이 facet의 static field가 아니며 각각 아래 contact/bodies에서 **반드시** 검사한다.
- **bodies**: 실제 named DOFs, native PD0/force caps `[3,6,5,2,2,1]Nm`, 로봇7+probe1의 runtime mass/localCOM/full inertia/principal, 실제 gravity0/cpu/120Hz/PhysxManager를 관측하고 source 가정과 비교한다. 임의 q/qd reset·목표/effort 명령은 없다.
- **trace**: sim.reset 초기화 뒤 Lab playing-explicit-step 10회, baseline 포함11행. 실제 PhysX post-step callback index/dt, PhysX engine time, Lab 요청 count, 읽기 전후 count와 전행 연속성을 대조한다. legacy SimulationManager global count stub를 쓰지 않는다. callback index/count는 한 관측이다. 모든 행의7LINK/CAD FK(actual q)/양쪽 joint closure/signed axis와 표시0·probe pose를 검사한다. 원래 dt/frame 허용치는 넓히지 않는다. 중력0 연결 시험이며 중력 정착28/실물보정 성공으로 표현하지 않는다.
- **contact**: reset 후 **실제** `environment.ContactReader(sim.physics_manager.get_physics_sim_view())`를 생성하고 실제 sensor/filter paths·counts/capacity를 보존한다. source golden의 canonical8 actors/9 filters·WORLD/N/capacity512와 완전 schema/중복/집합/행별 인덱스를 검증한다. 마지막 engine event10에서 실제 `.read(1/120)` sample을 저장하고8×9×3 finite normal force,8×9 counts, active contact의 canonical 인덱스/단위/범위/개수 합을 대조한다. 사전경로 목록이나 가짜 mapping을 실제 SDK view 관측으로 채우지 않는다.

각 facet은 생성 중 실제 state를 공유하지만 결과 envelope는 하나이며 source-input signature/SDK version/job/run/worker+parent PID와 결속된다. 성공 원자료 inventory는 observations/scene/providers/SDK initialization 등의 고정 파일이다. SDK stage 성공은 DLL 진단만, 최종 `ISAACLAB_ROBOT_CONNECTION_VERIFIED`는 네 facet·실제 exit·prereq·독립검토가 모두 통과할 때만 가능하다. producer의 ready flag나 호스트 synthetic positive가 native 물리 증거를 대신하지 않는다.

## 대조시험과 검토

052A: 실제 공개 PS 명령 양성/원래 source numpy.py·동명 package/cwd shadow/직접py import guard/누락root·필수manifest/변조SDK·prefix. old return-discard 정확복원 반대대조, 진짜 worker7→parent7, app 전/후/close failure를 actual wrapper/lifecycle로 확인한다. SDK모드 기존 성공/실패/미완료 뒤 **동일 SDK 재예약 거절**, 로봇 기존 성공/실패 뒤 **동일 로봇 재예약 거절**, SDK 실패/다른 입력/잘못된 PID·exit 뒤 robot 거절, 진짜 SDK 성공에만 robot 양성을 hostfake Popen 호출수와 원장으로 검사한다. 원래050 성공뒤second 허용 반례는 새 정책에서 실행0/거절이어야 한다.

052B: 네 facet 완전한 synthetic positive가 실제 공개 consumer에서 PASS인 것을 먼저 확인한다. 계약/collector/validator 의무 누락, contact facet 누락/잘못된actor·collider·LOCAL·kg·capacity0/중복sensor·각filter행변조/force/count/active 범위·마지막event불일치와 source body/joint side1/COM/principal/collider matrix/owner/enabled·마지막trace frame·PID/exit를 하나씩 바꾸고 원자료hash까지 재봉인해도 거절해야 한다. 매 변이마다 같은 정상 입력이 통과하는 독립 양성 대조를 사용한다. 실제SDK 관측 이전에 이 누락 반례를 새 entry에서 막았는지 비작성자가 확인한다.

L2는 이 source 계약 실행과 단발 단계 프로토콜이 소진한050의 단순 가드 수리인지 구조적 교체인지 명시 판정한다. L4 A/B는 실제 소스/원래 지적/모든 결과를 읽어5카테고리와9binary rubric·결함 합집합·계보 연속성·착지를 기록한다. 모든 기존 sufficient threshold는 유지하며 동종 새 반례가 독립실측·작성자수용되면 새 파일명으로 회피하지 않고 해당 접근 BLOCK/동결한다. 외부 계열 bridge의 이전 hook차단/no-bypass/no-retry와 같은 계열 fallback 잔여도 유지한다.

SDK/로봇 stage는 그 단계 host 대조/기계검사 후 각1회만 실행한다. 최종 결과는 부분 도달/원자료 검증/독립수용을 구분하며 실패도 보존한다. 끝에 owned process/Kit 및 원장 상태, source/raw/evidence hash·assumptions·NOT_RUN·구체 다음 범위를 인계하고 소유 범위만 로컬 commit한다. push/배포는 하지 않는다.
