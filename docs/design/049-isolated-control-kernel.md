> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 049 — 격리 실행 커널과 엔진 동역학 기반 정착 수정

2026-10-28, 사용자 「실패 두건과 아이작랩 연결 진행해」의 미완료 목적을 이어간다. 047 두 고정설정 시험0/28, 048의 frame소비/패키지shadow 결함을 보존한다. 현재 physical-frame accepted3/EXHAUSTED, pre-import provenance accepted4/EXHAUSTED다. 047/048을 더 고쳐 같은 단위 R2로 출하하지 않는다. 실물보정·모터/CAN/플래시·구매·링검증·정책학습은 계속 제외한다.

049는 별도 M8파일: 신규 `src/simulation/isolated_control/{kernel.py,control.py,verify.py,native.py,config.json,test_kernel.py,README.md}`+이계획과 `outputs/isaac-control-kernel-v1/`. 기존SDK/코드/CAD/047/048source는읽기전용. 048의 이미시작된 **고정pip installer**가 남긴 prefix를 원자료/전체seal 확인 후 읽기전용 의존성으로만 쓸 수 있다. 048의unsafe module/native entry나CONNECTED소비자를 호출하지 않는다. 기존source/준비물/실패/예산과 두 EXHAUSTED 이력은 새 이름으로 초기화하지 않는다.

## A. 실행 권위·이름공간의 교체

048 child의 `sys.path.insert(run); from setup import ...`는 미등록 setup/__init__.py가선실행되는반례로기각됐다. 049에서는 **프로젝트 폴더를 Python 검색 경로에 넣지 않고 프로젝트 코드 간 from/import를 사용하지 않는다.** stockPython -I의호스트고정literal root가 kernel/job SHA를 확인한뒤 kernel을파일경로로로드한다. 커널은 source-defined 고정입력전체집합·각hash·허용된모든코드디렉터리의정확한파일목록을검사하고, 읽은검증바이트를직접 compile하여별도namespace에실행한다. 나중에같은이름을재검색하지않는다. helper도검증한명시적파일경로/바이트로만로드하며namespace capability(API dict)로전달한다. project input tree는 sys.path/SDK PYTHONPATH로노출하지않는다. prefix는전체seal로검사한설치패키지와기존SDK만검색경로에추가한다.

호스트 실제 -I child에서 승인된payload 양성, 누락core/누락manifest항목/파일변조/추가Python, **setup/frames/core 동명 package __init__.py shadow**, kernel/jobSHA오류가 payload sentinel을 실행하기전에거절되거나검색불가능함을측정한다. 048 public probe의원래shadow witness와동등한실제새entry에서검사하고, 임의소스의자기hash를신뢰root로사용하지않는다. 이검사완료전remote projectpayload실행없음. 새설계의구별은검증가드하나추가가아니라프로젝트공유import namespace 자체를없애는것이며L2에서비작성자가판정한다. 일반OS/표준라이브러리/SDK전체security/TOCTOU보장은주장하지않는다.

## B. 결과 권위의 교체

048의 snapshot self-hash/7colliders 숫자 소비는 기각됐다. 049오프라인검사기는 hash뿐아니라 **고정원본 모델과 전체 frame 내용**을검사한다. 승인043의pre-play static.json을sha고정한source geometry/물성/관절/7collider/floor/probe 기대자료로,원래CADkinematics/recipe를독립입력으로사용한다. 이는새native결과에서생성해재봉인할수있는expected-sidecar가아니다. 가정질량/관성은그대로가정이다.

새native는관측원자료에7LINK pose/localCOM·full inertia/principal frame, fixed/revolute 양쪽 localframe/relationship/axis, collider7개의owner/local matrix/size/enabled, environment floor/probe frame·material·원자료contact mapping/force/normal/point를영속화한다. source-static은위 고정기대자료와모든계약필드를교차검사한다. collider계산결과를producer변수에만남기지않는다. 몸체삭제/추가, joint side1=[99,0,0],COM/principal/bodyframe/collider owner·matrix·enabled/0자세변조를자기hash까지재봉인해도검사기가거절해야한다. 비교키목록은기대자료의전체명시schema와일치해야하며누락은오류다.

동작중에는6781개모든관측의LINK/FK(actualq),양쪽joint closure/signedaxes·시계·접촉을끝까지검사하고tracking실패로frame검사를조기종료하지않는다. 047의 geometry검사 순수숫자정의는참조하되unsafe모듈import/consumer를호출하지않는다. 결과카운트/hash/producer의readybool만으로수용하지않는다. .5°/1°/s/28checkpoint·120Hz/56.5s·frame/contact기존수용기준과effortcap을유지한다.

## C. 제어 방식의 교체

047은model-derived ff+native implicit PD에서 J2/J3 오차와잔류속도가남았다. 기존방식의gain추가재튜닝은하지않는다. 새후보는공식설치SDK에있는 `get_mass_matrices`, `get_dof_gravity_compensation_forces`, `get_dof_coriolis_and_centrifugal_compensation_forces`의 **엔진 현재상태 full M,g,c**를사용하는computed-torque다. 실제반환shape/SI/sign/nativeDOF순서를설치source로확인하고기록한다. native stiffness/damping을0으로설정하고실제tensor에서0을확인한뒤, `tau=clip(g+c+M*(qdd_ref+64*(qref-q)+16*(qdref-qd)),±[3,6,5,2,2,1]Nm)`만직접인가한다. massmatrix의유한성/대칭/양의정정부호와중력/보상벡터단위·6DOF순서를검사한다. 총torque와cmd readback,입력M/g/c/실제이전q/qd를원자료에남겨offline에서식전체를재계산한다. 과거모델ff나남은PDcap을더하지않는다.

qdd_ref는고정원래recipe의qd를고정120Hz중앙차분/끝점단측차분한값이다. 원래기계한계/물성/shape/source USD/ground/probe·중력−9.81/충돌·토크cap은유지한다. q/qd와body pose를바꿔치기하거나kinematic/reset강제로성공시키지않는다. 수집init의timeline 초기화 뒤 baseline을기록하고manual step은각1/120초한번이어야한다. simulation clock과float32callback clock은기존처럼분리검사한다.

실제Lab3.0 wheel의 SimulationContext.step은 paused상태에서wait_for_playing으로대기하므로047의paused-step호출을복사하지않는다. 새프로토콜은headless **LAB_PLAYING_EXPLICIT_STEP**이다: sim.reset()으로SDK초기화한뒤baseline을기록하고, timeline playing 상태에서 sim.step(render=False)만호출하며app.update/다른step을호출하지않는다. 실제timeline상태와Labstepcount/enginecount/doubleengineclock/float32POST_STEP count·clock,각읽기전후step을모두기록한다. 이전행after==다음행before·Lab/engine각1step·동일관측중step불변을매행검사하여pause라는bool대신실제독점stepping효력을검증한다. 이프로토콜을paused라고위조하지않으며기존숫자시간허용치를넓히지않는다. 형상/오차/속도/토크수용치는동일하다.

## 검토·실행·종료

L2/L4각max2,기존비작성자만검토하며구현worker/newagent추가없음. 외부계열bridge의이전hook차단/no-bypass·동일계열fallback잔여유지. source-defined新authority구조가소진접근의단순연장인지L2에서판정하고,모든known반례를새entry/전체frameconsumer에서수리효력으로먼저측정한다. 049새클래스원장을oldEXHAUSTED의취소로해석하지않는다.

Host→module/GPU(프로젝트kernel 새entry,048probe사용금지)→실제Lab/PhysXnative순서다. 독립prefix/module version/origin·CUDA tensor 확인이안되면SDK실행금지. nativeauthormax2/각600s,예약전에영속화하고시작실패도소비한다. 첫실행은위단일computed-torque recipe로고정,둘째는측정된SDK/API/수집오류의최소수정확인만이며성공반복/새gain후보추가불가. 두번후새동작을반복해성공을찾지않는다. 효과가없거나결속/프레임반례가재발하면보수적으로BLOCK/미해결로남긴다. 충분한native/PID/exit0/입력·프레임·제어·全recipe관측과독립검토가모두충족될때만새수용을기록한다. 기존두실패와047/048미폐쇄지적은그대로다.

별도 설치/다운로드는필요없으며외부딥러닝/대규모학습/실물동작도없다. 결과/HANDOFF/검토·예산·확인범위/한계를도메인폴더에저장하고소유범위로컬commit한다. 보호.dev를우회하지않는다.
