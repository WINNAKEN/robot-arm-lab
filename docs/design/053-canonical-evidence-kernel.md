> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 053 — 불변 실행 snapshot과 단일 canonical evidence kernel

사용자의 현재 권한은 그대로다: 재부팅하지 않고 SDK NumPy로 통일·접촉 매핑·단계별1회 구현·IsaacLab 연결까지 검증한다. 052는 SDK0/robot0에서 source를 동결했다. 새052 수리/R2/실행은 하지 않는다. 새로운053은 **모든 검증 권위를 SDK 수집 코드 밖의 하나의 stdlib kernel로 옮긴다**. source cache reread/lexical-origin/자기 static에서 inertia 재유도/접촉 aggregate 의미 누락을 전부 재상정한다. provenance7 EXHAUSTED, physical6 EXHAUSTED, eligibility2/다음1 충분 및 이전 모든 이력은 불변이다.

## 소유와 구조

새 `src/simulation/canonical_v4/{launch.ps1,kernel.py,providers.py,robot.py,contract.json,config.json,test_kernel.py,README.md}`와 이 계획(M9, 실행권위·수치증거 두 그룹), 증거 `outputs/isaac-canonical-v4/`. 원052/050 등의 entry/검증 실행 경로는 호출하지 않는다. SDK실제 collector의 무해한 내용과 원본041extract/043environment/joint_frames·041USD/043golden/CAD·가정은 source hash 고정의 읽기 전용 입력으로만 사용한다. MP9·.dev·CAD·펌웨어는 무접촉. 실물 보정·모터/CAN/전원·플래시·학습·구매·링검증·재설치·재부팅·시스템 설정 변경은 없다.

052의 registry는 단순 필드 누락을 막았지만 의미 판정이 여러 helper와 관측 metadata로 분산됐다. 053의 pure kernel은 **코드 실행 권위, 경로 identity, source oracle, 접촉 cross-signal reconstruction, 단발 stage 상태**를 직접 소유하며 SDK 모듈은 원자료 수집만 한다. producer가 제시한 expected/provider verdict를 소비하지 않는다. 이 권위 이동이 소진한 source의 단순 patch인지 L2 비작성자가 명시 판정한다.

## 1. 실행 snapshot과 권위 경계

모든 공개 PS test/prepare/run/verify·원격 root는 Python -I -B -c literal loader를 쓴다. 직접 .py는 import 전에 거절하고 프로젝트 sys.path/import는 없다. source/payload의 전체 고정 집합·job/source SHA를 검사한 **같은 바이트**를 보관하는 불변 snapshot을 만든다. `Snapshot`은 run/job hash/code pins/source signature/config/bytes를 포함한다. nested job/config/bytes는 읽기 전용이며 SDK 코드에 expected golden oracle은 전달하지 않는다.

supervisor는 이 snapshot에서 stdlib kernel의 prereq/provider 수치 검사를 직접 호출한다. **supervisor에는 project code 파일을 다시 읽거나 동적 compile하는 코드 경로가 없다.** SDK ops는 native 역할에서만 snapshot의 검증된 cached bytes로 private namespace에 compile한다. child는 자신의 새 snapshot을 다시 검증하므로 parent 검증 뒤 input 파일이 교체돼도 다른 코드가 실행되지 않아야 한다. SDK sitecustomize도 read_bytes1회→그 bytes SHA 검증→동일 bytes compile이며 SHA용 read와 실행용 reread를 분리하지 않는다.

설치 prefix/기존SDK는 protocol동안 readonly인 신뢰된 제3자 runtime으로 취급하며 전체seal/고정 bootstrap을 실행 전에 관측한다. 임의 OS 공격자가 import 직전에 설치SDK/prefix 전체를 동시변조하는 경우까지 봉인했다고 주장하지 않는다. 이 제한은 project 코드 snapshot과 explicit SDK bootstrap bytes의 위 의무를 면제하지 않는다. 코드 hash 오류·누락·추가 package는 source 실행 전에 거절한다.

## 2. canonical 제공자 identity

kernel의 단일 `owned_origin(path, root)`만 모든 NumPy/SciPy/FFT/Warp/Torch/Lab/Gym/RSL 제공자 판정에 사용한다. 절대 경로만 허용하고 원문 component에 `..`/`.`가 있으면 거절한다. Windows Path.resolve로 canonicalize한 path/root를 비교한다. raw lexical is_relative_to는 사용하지 않는다. 실제 collector의 resolved origin이라고 해도 consumer가 같은 판정을 다시 수행한다. resolved roots도 source config에 고정한다. 원 A NumPy와 B Torch traversal witness를 동일 한 원인으로 모두 검사한다.

SDK NumPy2.3.1/SciPy1.17의 고정 root parents를 먼저 노출해 FFT([0,1,2,3])=[6,-2+2j,-2]·Rotation identity와 해당 모든 loaded module origins를 실제 관측한다. 앱 이전에는048 학습prefix를 노출하지 않는다. SimulationApp 생성 뒤 prefix를 맨 뒤에 추가한다. Warp1.17은 실제 SDK 공개 subtree/module.__version__를 유지하고 나머지 Torch2.11cu130/Lab3.0/Gym1.4/RSL5.5.1은 prefix identity/version을 검사한다. 숫자와 경로 판정은 kernel에만 있고 providers.py에는 독립적인 loose checker가 없다. kernel callback이 없는 API로 SDK collector를 실행할 수 없다.

## 3. source oracle과 cross-signal 의미

kernel은 SHA 고정 원043golden을 자기 snapshot에서 decode한 **canonical source oracle**로만 사용한다. 원자료 static/body에서 expected tensor를 재유도하지 않는다. SDK producer에는 이 oracle 객체를 전달하지 않고 measured facets만 받는다.

`contract.json`은 source 필수4facet static/bodies/trace/contact와 필수 field를 고정한다. producer COLLECTORS와 kernel VALIDATORS는 그 집합과 정확히 일치하고 모두 실행한다. 누락·추가·optional 의무는 거절한다. 원 source-static7LINK/양쪽 joint frames/relationships·axis·localCOM/principal/inertia·collider owner/basis/enabled·units/default/root/floor/probe/environment를 전부 대조한다. 수치 tolerance는 단일 unit 정책이다: 기존 frame1e-6 source비교, runtime position/rotation1e-3, mass/COM1e-6, **source inertia_diag 및 runtime full inertia는1e-7**. 관측된 static이 그 근처라 해도 runtime expectation은 항상 golden principal+diagonal의 source tensor다. 5e-7 source/runtime 동반 drift는 거절해야 한다. principal frame의 동등한 부호는 full tensor를 diagonalize하는지로만 허용한다.

runtime mass/DOF/PD0/caps `[3,6,5,2,2,1]Nm`·gravity0/cpu/120Hz/Lab manager와11행·10step·PhysX 실제 post event/dt/time/Lab count/read 소유권·모든 LINK/FK/양쪽closure/signedaxis를 원래 계약대로 검사한다. 근거는 source oracle과 actual q이며 producer의 ready/expected sidecar가 아니다.

실제 ContactReader의8sensor/9filter/index permutation/WORLD/N/512·event10 sample을 필수 관측한다. mapping의 actor/filter 집합·중복·행별 index를 canonical source와 대조한다. **8×9 normal-force vector는 각 pair의 active scalar force×world normal vector 합으로 kernel이 재구성하여 원 matrix와 대조한다**(절대1e-6 N). counts는 같은 pair의 active 개수와 같고 총합<512여야 한다. counts0/active[]에 matrix99N, 또는 정상 99N·[0,0,1] active를 두고 matrix만[99,0,0]으로 바꾼 원 반례 모두 거절한다. 정상 일관된 비영점 host sample도 양성으로 통과해야 한다. 자기합계 검사를 실제 SDK contact API 검증으로 혼동하지 않는다.

## 4. 단발 stage 상태와 실제 종료

서로 다른 고정 단계 `sdk_preflight`(앱 없는 NumPy FFT/SciPy DLL 진단)와 `robot_connection`(앱/Lab/원본 로봇/contact/10step) 각각 최대1회·600초다. 새053 root ledger와 lock에 예약을 Popen 전에 저장하고 성공/실패/timeout 모두 소비한다. **원052 stage-ledger가 존재하면 같은 stage의 기존 reservation도 함께 세어 누적 한도를 적용**한다. 052예산 미소비라는 현재 사실을 source 이름 변경으로 초기화하지 않는다. 동일 stage 재실행은 항상 거절하고, SDK 실패/미완료·다른 input signature/PID/exit/raw hash/provider 값이면 로봇 단계는 시작하지 않는다. SDK 정상 자료에만 다른 목적 robot 단계1회를 허용한다. 기존 run의 terminal/exit는 덮지 않는다.

worker→root SystemExit→parent actual exit→SSH/PS가 실제 code를 유지한다. app.close fast exit 전에 measured artifacts/hash와 현재 code terminal을 쓰고 close에 그 code를 전달한다. close 반환/오류와 primary fault를 구분한다. 전체 facet/actual exit/PID/SDK prerequisite가 모두 충족돼야 최종 연결 수용이다. 접속 전송 실패는 회수만 하며 재실행하지 않는다. 이전 정착28지점과 학습은 미해결/NOT_RUN이다.

## 검증·검토·종료

L2/L4 각최대2/M45분, 기존 비작성자 재사용·구현worker없음. 외부계열 기존hook차단 no-bypass/no-retry·동일계열fallback한계 유지. A/B052 receipt와 원래4반례를 직접 읽고 동일 계보/중복 union/착지를 판정한다. 새 같은 class 독립실측·작성자수용이면 기존 sufficient threshold를 유지하며 보수 동결한다.

실제 source literal child에서 검증후 providers 파일만 교체하는 원052 schedule을 복원해 unapproved sentinel이 실행되지 않음을 확인한다. 새 supervisor가 runtime validator를 별도 읽어 compile하지 않음을 실제 호출 경로에서 검사한다. 모든 numeric/framework origin traversal을 source-root 밖으로 해석하는 반례는 public verify에서 거절한다. 표준 source/kernel 정상 양성 뒤 검사마다 source 누락/변조/registry 누락, mapping 누락·오류, contact matrix/count/normal cross변조, golden-v-runtime inertia 동반변조, 마지막frame/clock/PID/exit·stage repeat 및 legacy052 reservation을 대조한다. old return-discard의 정확복원 반대대조와 genuine worker7→최종7을 유지한다. 호스트 synthetic을 native 성공으로 표시하지 않는다.

Source+host+독립 코드 검토가 모두 통과한 뒤에만 SDK단계를1회, 동일 source input signature의 full robot단계를1회 실행한다. source를 바꾸면 기존 SDK 성공을 새 코드의 prereq로 쓰지 않는다. 결과의 현재성/부분범위·원자료/PID/프로세스 정리·hash·소진이력은 도메인 인계로 보존하고 소유 파일만 로컬 commit한다. 보호.dev/다른모델링은 변경하지 않고 push/배포하지 않는다.
