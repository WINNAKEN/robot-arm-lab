> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 048 — 원격 IsaacLab 설치와 프로젝트 모델 연결

2026-10-28 사용자 「실패 두건과 아이작랩 연결 진행해」에 따른047과분리된M단위다. 소유 `src/simulation/lab_connection/{setup.py,native_probe.py,config.json,test_connection.py,README.md}`+이계획(6파일), `outputs/isaac-lab-recovery-v1/`. 047의수치실험과별도로 기존원격6.2RC를보존하면서프로젝트전용Lab환경을설치/검증한다. CAD/041~044/047원본/펌웨어·MP8모델링 무수정. 설치된Sim·드라이버·보안·서비스·전역환경·기존패키지를교체/제거하지않는다. 실물보정/모터/CAN/플래시/구매/링검증은제외하고PPO최적화/정책학습도이번범위에없다.

## 조사와 선택

현재isaacpc/robot-user기존Python3.12.14/Isaac6.2RC14,조회torch/warp/Lab부재·numpy는Kitprebundle,git는PATH미발견,C여유약341GB. 공식release/3.0.0현commit270a8c1d4a26181adf2c5bd2fc9a3c649f17a294소스를다운로드해읽었고32,583,358bytes/SHA991904eb05a7f6aef885cf4546153e1d26f305080802dc96661f1733b0f4a143로보존했다. source현재coremetadata28.0.1과aggregatePyPI3.0.0은다르므로동일commit바이트라고단정하지않는다. 실제설치는공식PyPIaggregate wheel3.0.0의URL/SHA를고정해사용하고연구source/설치wheel을구분한다.

공식3.0은Sim6.2/Python3.12·Torch2.11/Warp1.17·CUDA13을사용한다. 기존bundlePython사용은유지하고별도venv/conda로Sim을섞지않는다. fullinstaller는prebundle/전역uninstall까지수행하므로사용하지않고 새GUID아래 `C:/isaacsim_remote/robot-arm-lab/048/<guid>/packages`에 `pip --target`으로 **최소PhysX연결용runtime**만설치한다. 이는fullLab/모든backend/모든extra환경충족주장이아니다. 실행할child만prefix를우선검색하게하고그process이외환경은바꾸지않는다. upstreamLab자신의prebundle우선순위조정은그process안의공식코드동작으로기록한다.

고정criticaldeps: torch2.11.0+cu130/torchvision0.26.0+cu130(공식download.pytorch.org),warp-lang1.17.0,isaaclab3.0.0. Gymnasium>=1.2,<2/RSL5.5.1 및실제공식Lab import에필요한선정runtime deps를같은prefix에설치한다. 다른pxr provider/usd-exchange·두번째IsaacSim/OV/Newton/teleop등은연결시험용으로추가하지않는다. 의존패키지가모자라면해당import traceback에필요한것만명시기록후보완(최대1회)한다. 결과는pipreport·wheelSHA·실제moduleversion/origin/CUDA확인으로남긴다. CPU버전Torch로조용히대체하지않는다.

Aggregate wheel의 설치 명령은 반드시 `pip install --no-deps --target <새prefix> <SHA검증wheel>`이다. 공식 metadata 전체를 resolver에 넘기지 않고, 앞서 선정한 runtime deps만 별도 설치한다. 047의 PASS가 확인되지 않은 FAIL/PENDING/UNKNOWN 모두 동작 금지 분기로 간다. 이 분기에서는 gravity0의 정적 stage 연결만 확인하고 reset/step/목표 전송을 실행하지 않으며, 중력·충돌 물리 연결 성공으로 표시하지 않는다.

## 단계·예산·수용

### 047 소진 이후의 새 시작 경계 (L2 R2 재상정)

047 L4 R1에서 manifest가 core항목을누락해도worker가미등록core를실행하는반례를수용했다. 기존 실행의존/provenance accepted2+이번1=3으로 **그 per-item manifest 검증 접근은 EXHAUSTED**다. 047을추가수리/재실행/출하하지않으며이사실을048성공으로지우지않는다. 물리frame계열accepted2는별개로유지한다.

048은이worker를복사하거나import하지않는standalone시작구조로재설계한다. host가고정한bootstrapSHA와jobSHA를원격 **격리Python(-I)**의짧은표준라이브러리검증구문에서먼저확인하고그뒤에만bootstrap을실행한다. bootstrap의고정입력목록(실행파일·config·모델/kinematic/extractor/frame자료)은manifest **정확한전체집합**과대조하고모든hash를검사한뒤payload를실행한다. 누락/추가/중복/잘못된경로/새미등록Python파일은실행전에거절한다. 기대집합을user-job의선택목록에서추론하지않는다. setup/probe두단계모두동일한닫힌시작경계를쓴다.

설치는빈projectprefix만대상으로한다. pipreport/고정aggregatewheelSHA외에설치완료prefix의모든파일을열거·hash한seal을남긴다. 후속module/native시작전에prefix의정확한집합·파일hash를다시확인하며seal자체SHA는host가회수한기록에결속해remote실행인자로전달한다. 기존Kit/표준라이브러리/운영체제까지무결성을보증하는계약은아니다. 실제모듈경로/버전과단계별PID/nativeexit도별도기록한다.

검증의핵심반례는047에서측정된같은누락core/executable sentinel이다. 올바른manifest는실행되고, manifest항목만삭제한경우/파일변조/추가미등록Python/서로다른jobSHA/seal항목삭제·재봉인/설치파일추가·수정은모두payload sentinel이실행되기전에거절되어야한다. 이새입구가검증되기전에는원격설치/프로젝트payload를실행하지않는다. 이는소진된접근에가드를더얹어출하하는047수리가아니라048의아직미구현된bootstrap/payload분리설계이며,旧family3/EXHAUSTED이력은그대로남긴다. L2잔여1회(R2)에서이전제와재발class판정을독립검토한다.

1. setup은새GUID/write-once/BUILDING부터시작, config/모든실행파일hash·wheelidentity·원격설치기록/PID/실제exit를결속한다. 설치phase max1800s,1회+명확한누락의존복구1회. 실패경로는FAILED로끝내고과거성공을current로대체하지않는다. supervisor는자기자식만정리하고기존Kit세션을종료하지않는다. 설치중에는nativephysics를실행하지않는다.
2. 기존bundlePython+projectprefix로Lab/Torch/Warp/Gym/RSL을실제import,version/origin·TorchCUDA13/GPUtensor연산을확인한다. 이것은LabPhysX연결완료가아니다.
3. nativeprobe예약최대2회/각600s(시작/API실패포함). 기존Kit이종료된뒤진행한다. 공식LabSimulationCfg/SimulationContext의PhysX backend를실제생성하고이프로젝트041/USD혹은검증된047scene(고정SHA)을불러7links/6canonicalDOFs·m/kg/Z·CAD表示0·동일runtimeclock을확인한다. 현재SDK/실제API를읽은뒤그버전맞춤호출을쓴다. RC-version검사를우회/라이브러리소스를수정하지않고실패는RC호환미검증으로남긴다.
4. 모델연결은LabSimulationContext소유물리단계와기존CoreexperimentalArticulation관측/제어의실제교량을검증한다. 완성된IsaacLabDirectRLEnv등록이나044Gymnativebackend연결로표현하지않는다. 047PASS일때만같은가정/gain/solver/cap·중력/충돌의짧은목표경로와실제q/qd/clock을기록한다. 047FAIL이면모델가져오기/정적연결만하며동작/학습수용을막는다. 상태41/action6계약의연결점은문서화하되실제MDP통합·장기정책평가는후속이다.
5. moduleimport+GPU검사와nativeLabPhysX+모델상태단계는별도status. 실제native/PID/exit/모델/설치path·hash·시간/관측이결속되고범위검사가통과할때만해당단계PASS다. 표준출력성공문구/CLIexit0만으로native성공으로바꾸지않는다. 실물authority는항상false·weightsnull.

호스트검사: URL/SHA/path/scope/config엄격검사,없는입력/설치실패/잘못된moduleorigin·CPUCUDA대체/native미실행상태를연결PASS로소비하지않음,실제childexit/모델fingerprint·시간진행/6DOF/physicalfalse변조. 설치의동등한실행재현스크립트를저장하고실제모듈체크와native원자료도독립검토한다. 재사용047/041/044 helper실행이필요하면전이의존까지승인hash를import전에검사한다.

L2/L4각max2, AGENTS→DEV_PRINCIPLES의무에따른기존비작성자검토만사용하고구현workingagent는추가하지않는다. physical-frame accepted2/다음동종독립실측+작성자수용1임계와 provenance accepted3/이미EXHAUSTED와모든이전예산/SDK실패/039실시간·링보류를보존한다. 외부계열bridge는이전043hookblock이후이번재시도/우회없음,같은계열비작성자fallback잔여명시. 도메인delivery/HANDOFF와로컬commit으로끝내며보호.dev쓰기를우회하지않는다.

공식근거(2026-10-28): https://docs.nvidia.com/isaaclab/isaac-lab/installation · https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/compatibility.html · https://github.com/isaac-sim/IsaacLab/tree/270a8c1d4a26181adf2c5bd2fc9a3c649f17a294 · https://pypi.org/pypi/isaaclab/3.0.0/json . 公式対応表は설치RC実動作검증대체가아니다.
