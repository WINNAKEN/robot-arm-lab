> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 055 — 검사 전 provider 관측과 새 프로세스의 명시적 초기화

2026-10-28 사용자는 실제 Torch 로드 경로/CUDA 상태를 검사 전에 기록하고 원인에 맞게 초기화 순서를 수정해 IsaacLab 연결까지 검증하라고 명시했다. 재부팅·실물 보정·모터/CAN·플래시·설치·드라이버/전역설정·학습·구매·CAD·링 검증은 제외한다. 질량/관성 가정,047 정착 실패와053/054 source·실제 카운터·검토 이력을 보존한다.

## 소유·예산과 새로운 권위

M8/45분: 이 계획과 `src/simulation/provider_session/{session.py,providers.py,worker.py,settings.json,launch.ps1,test_session.py,README.md}`. 근거 `outputs/isaac-provider-v1/`. L2/L4각max2, 기존 비작성자 읽기 검토만 사용하고 구현은 작성자가 한다. 이전 외부계열 hook 차단은 재시도하지 않으며 동일계열 fallback 한계를 기록한다. .dev/BOM/다른 코드 무접촉, 소유 파일 로컬 commit만 한다.

원054는 감사1/앱1과2L4가 이미 종료됐다. 새 사용자 권한에 따라055의 세 목적은 설치 재감사1(900s), 앱 내 provider 진단1(300s), 그 진단으로 결정한 새 프로세스 연결1(600s)이다. 기존054 원장 SHA62748c815ce30ad4d692c702801746a87f4a847ce9bf8ba768e42666b7f87677 및 nested053 기록을 필수 legacy 입력으로 유지한다. 이전 성공을 새 source의 실행 허가로 재사용하지 않는다. 기존 슬롯을 비우거나 같은 프로세스에서 Torch DLL/module을 unload/reload하지 않는다.

새 권위는 **측정(report)과 접속허가의 분리 및 고정된 provider 의도표**다. diagnosis의 정상 종료는 관측이 완료됐다는 뜻이며 CUDA13/로봇 연결 통과가 아니다. 실제 module 객체의 origin/version/CUDA 값으로 root가 두 고정 profile 중 하나를 선택하며 사용자 입력 success flag나 producer의 선택을 믿지 않는다. 054 감독·종료/감사 코드는 내용 자산으로 재사용하되 새 session이 세 목적의 순서·단발 원장·nested proof·profile 선택과 최종 수용을 소유한다. old public/entry/supervise/consume는 호출하지 않는다. 053 canonical 수학/SDK numeric/robot collector와054 streaming audit만 hash 고정 내용으로 재사용한다. 이 구조가 단순 stage명 변경인지 L2가 독립 판정한다.

## 관측과 초기화

공개 PS→Python -I -B -c hash loader, 단일-read job/source의 immutable bytes, 정확 payload집합·source package SHA, cached bytes compile, 실제 exit/PID/shell/SSH 분리는054의 최종 계약을 유지한다. 감사는 SDK import0·39,919개 전체 seal·4thread/1MiB streaming이다. SDK와048 prefix는 세션 동안 readonly인 신뢰된 설치이며 동시 OS 변조 전체를 봉인했다고 주장하지 않는다.

진단은 원래의 SDK bootstrap→SDK NumPy2.3.1/SciPy1.17 수치 확인→SimulationApp→prefix-last 순서를 관측한다. **CUDA 판정 전에** Torch.__file__/__version__, distribution version/root, torch.version.cuda, torch.version/torch._C origin, availability의 미실행/결과/오류, device count/name/capability와 가능한 GPU ones(2×3).sum 결과, 주요 module origins, sys.path를 저장한다. import/availability/GPU probe 전후에도 원자료를 저장해 부분 실패를 없애지 않는다. Nvidia-smi는 driver/name 조회만 최대10초로 수행하고 실패를 별도 기록한다. GPU/driver 설정은 바꾸지 않는다. numeric-before/after 및 각 module의 실제 관측도 남긴다. driver CSV·설치 metadata·Warp GPU 인식을 Torch의 실제 성공으로 대체하지 않는다.

진단은 Torch 식별과 availability(또는 명시적 probe 오류)·numeric SDK 대조를 완성해야 `PROVIDER_DIAGNOSIS_COMPLETE`로 종료할 수 있다. Torch 자체 import 실패/필수 Torch 관측 부재는 진단 실패이며 연결을 막는다. 그 외 주요 module은 각각 관측 또는 import 오류를 빠짐없이 기록해야 하며, 이 오류는 BASELINE을 허가하지 않고 PREAPP 후보의 원인 자료가 된다. root는 hash/PID/actual exit0·정상진단 원자료를 다시 대조한다. root의 수학 판정은 immutable cache에 고정한053 pure validator만 사용하며 파일을 다시 읽어 실행하지 않는다.

현재 Torch가 canonical048 prefix/2.11.0+cu130/CUDA13·actual CUDA tensor sum6이고 주요 framework도 의도한 provider와 일치하면 profile `BASELINE_CONFIRMED`, 그 밖의 완전한 관측이면 `PREFIX_TORCH_PREAPP`다. Lab3.0 wheel의 torchvision==0.26.0 요구도 고려해 Torchvision은 기존048 prefix/0.26.0+cu130을 의도표에 포함한다. 연결 job의 profile은 root가 원본 진단에서 재유도해 일치해야 한다. 임의 profile/success 필드로 허가하지 않는다.

연결은 새 프로세스다. BASELINE은 원래 순서를 유지한다. PREAPP은 SDK bootstrap→SDK NumPy/SciPy 전체 수치·origin 확인→SDK Warp1.17을 그 고정 root에서 import→prefix를 우선 노출해 Torch2.11cu130·Torchvision0.26cu130을 import·원자료 저장·canonical origin/CUDA13/GPU sum6 확인→SimulationApp 순서다. numpy/scipy/warp/torch/torchvision 객체 identity와 origin을 앱 전후에 다시 확인한다. sys.modules 제거·DLL 교체·설치 변경은 없다. 기존 collector의 frameworks 함수를 cached 새 provider 수집기로 연결하여 **로그 뒤에만** 수용 판정을 수행한다. 모든 numeric/framework identity, CUDA13/actual GPU6, CAD static/bodies/trace/contact4facet·중력0/PD0/10step11행 수학 검증은 그대로 필수다. 조건을 삭제해 통과시키지 않는다.

## 허가 수명과 종료

lock 아래 durable reservation 후 Popen, 실패/timeout도 각 목적1회 소비. 진단은 감사 완료 후300초 안에 허가되어야 한다. 연결은 진단 완료 후300초 안에 허가되어야 하며 원 감사의 적시성은 **진단 허가 시각**으로 대조한다. 연결/최종 조회 때 과거 감사를 현재시각으로 다시 만료시키지 않는다. 모든 proof는 같은 input signature·원본 job/receipt/hash/PID/actual exit/remote-shell과 원장의 original run에 묶고 nested audit proof도 필수다. public host gate는 원본 transport0도 확인한다. 읽기 조회가 허가를 갱신하지 않는다.

정책은 actual0..255 유지/그 밖 실제정수는 보존하되 정책1, timeout124·cleanup/reap/poll 오류·실제 UNKNOWN/생존상태는 분리한다. fast shutdown 전 raw/hash와 실패/정상 terminal을 쓰고 실제 parent exit로 다시 대조한다. transport 실패는 회수만 하며 재실행하지 않는다. Windows 보조 프로세스는 숨김 실행한다.

## 검증·정지

호스트는 이전 정상 로봇 fixture와 source/exit/감사 시험을 보존하고, wrong-provider/CPU/CUDA버전/probe오류가 판정 전 저장되는지, report로 root profile이 결정되는지, profile 위조/진단실패/다른 signature/PID/hash/오래됨/중복/nested proof누락을 거절하는지 검증한다. 진단 완료≠연결 성공, 조회≠재허가를 대조한다. SDK 없이 init 순서와 수집기 연결을 기록하는 호스트 대조를 하고 AST·범위 whitespace·L4 뒤에만 실제 감사→조건부 진단→조건부 연결 각1회를 실행한다. source 변경은 성공 proof 재사용 권한이 아니다.

실제 단계 실패 후 같은 목적 추가실행·source 수리출하는 하지 않고 원자료·도달지점·소유프로세스 정리를 남긴다. provenance7/physical-frame6 EXHAUSTED·eligibility2/다음 독립실측·작성자수용1 충분 임계와 다른 과거 원장은 불변이다. L2/L4는 class/착지/예산 종결 및 정적/실행 한계를 구분하고 신규 같은 class 재발은 비작성자가 판정한다. 외부계열·실물·링·학습 한계도 소급 PASS로 바꾸지 않는다.

## 사용자 명시 연장 — R3 한정

2026-10-28T12:45:47Z 사용자 응답 `추가 검토 후 계속 진행 (추천)`에 따라 새45분 예산을 시작한다. 보완 패치(availability=True일 때 장치 수/이름/capability 또는 명시적 device_details_error 필수)의 비작성자 독립 정적 검토를 **1회만 추가**, L4 총최대3회로 한다. 기존 R1/R2 BLOCK·보존 source·호스트 결과·소비 이력은 그대로 둔다. R3 PASS일 때 아직 미실행인 installation_audit/provider_diagnosis/provider_connection을 정해진 순서와 조건으로 각각1회 실행한다. R3 실패 시 네 번째 검토나 추가 수리출하는 없다. 설치·재부팅·실물 보정·모터 운전 제외는 유지한다. 실제 단계 사용0/0/0에서 시작하며 이전053/054 원장은 변경하지 않는다. 원문 승인 기록은 outputs/isaac-provider-v1/evidence/user-authority-r3.json에 둔다.
