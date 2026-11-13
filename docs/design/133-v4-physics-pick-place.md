> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 133 — v4 다관절 큰 동작·안전 홈·실제 물리 집기/놓기 시뮬레이션

새 사용자 지시: “자그럼 이제 관절을 다양하게쓰는 큰동작도 테스트하고 안전자세를 하나 세팅해서 작은 물체하나 집고 다른장소에 놓는 시뮬하나 짜보지?” 이 요청에 따라 Root가 구현·검토·실제 시뮬레이션을 수행한다. 원131 목표는 완료이며 그 원격기간·모든 old grants/markers/SDK6·예산·raw/EXH는 동결한다. 이133은 새로운 물체 조작 책임이며 과거 수리 예산을 리셋하는 이름 변경이 아니다. 실물 CAN·RS485/포트/전원/flash/설치/네트워크·시계/Git 변경0, hardware_approved=false.

## 소유·시간·검토
source8: src/simulation/mp18_manipulation_133/{contract.py,native.py,driver.py,runner.py,media.py,config.json,test_contract.py,test_runner.py}; 본계획1과 outputs/mp18-manipulation-133/. 2그룹(물리 task engine / 전송·소비·영상 lifecycle), 8+plan1=M. 신규 author 총2700s(firstread와 준비 포함)/검산예비300, 신규 main 비작성자 L2+L4 합2700s/예비300, 각max2/noR3. 새 author 준비는180초 안팎으로 동결 후 L2 대기 분리; L2 PASS 전 source 작성0. 기존 승인 same-family 비작성자 폴백 사용, 공통편향 잔여 명시. Root L1→main L2→author L3/HOST→main L4→Root current-byte freeze검산→생산prepare/원격→실제영상. 이전132 author/reviewer예산과 독립이나132산출은 읽기 의존으로만 사용한다. 새 sourceF에 planner132, scenario132, typed132 L4와 model/source dependencies 핀을 포함한다. 132 L4 PASS 전 생산 prepare/GO0.

Root 내부 새 작업 상한(사용자가 분 단위를 직접 승인했다고 쓰지 않음): 이 실제 새 simulation 요청에 근거해 SDK 최대2회, 각 최초 원격 실행부터 고정2700초, 회당GO1/retry0, 합5400초 이하. 첫 실행 성공하면 두번째 실행0. 실패 원자료를 회수하고 필요한 source수리는 남은 author/main hardcap 내, 재검토/새F 후에만 별도 두번째 fresh run/nonce/job/oneshot으로 실행. 오래된 period 재무장·실패 삭제·자동 연장·세번째SDK0. 이 내부 allocation과 실제 user quote를 구별해서 task-scope.json에 기록한다. 실패/소진이면 실제결과와 남은 제약을 정직하게 종결한다.

## 입력과 실제 물리 계약
원 URDFv4 d55f0cbdffb8f82094b8797b187f02a3a5fd77a4a4f4272c975f21945b53135f 및 모든 mesh/model74 핀 읽기 전용. 원130 native e78af630c5dfda106dca14d3059065c0e060c63671e2ba8b3d0756cd86b1dcd8, contract9052f08394a2af45f7c73b259a9bece983393bcc0d102a82a6fb21010d5574cf, driver 그리고 실제108SDK lifecycle/WinJob/raw123 transport를 읽기 재사용한다. 기존 source130/131를 덮어쓰지 않는다. 원 fresh_stage anonymous root/session lifetime/zero clocks/no inherited roots, importer numeric/COM/inertia/current binding 증거를 보존한다. 설치된6.2.0-rc.14의 actual SDK source/API 핀으로 구현하고 latest문서만으로 지원을 단정하지 않는다.

132 planner.sample(scenario,t_s)→{targets:9 named SI,reference_velocity:9 named SI/s,phase,gripper_mode,opening_m,phase_index}를 직접 사용한다. 혼합 단위는 joint_units rad/m로 구분한다. 다른 궤적 구현을 복사하지 않는다. 132 actual geometry는 작은20×10×8mm/2g 물체, KG1z104mm grasp frame, source/target actualFK yaw/위치/좁은pedestal, 85초 내외를 제공할 예정이다. 최종 schema/hash/geometry는132F에 따른다. static132의 floor/caps/limits/velocity 검사는 실제 물리 성공 증거가 아니다. 자기충돌 broadphase의 장착부 UNKNOWN 등 잔여를 성공으로 승격하지 않으며 safe_home은 이 시뮬레이션의 복귀 자세이지 실물 안전 인증이 아니다.

ARM gain64/16, sim torque caps J2=12/J3=7Nm·그외URDF 원cap, 원 source speed arm0.5rad/s+jaw0.02m/s+pinion2rad/s와 +0.0001 guard, dt1/120, 원바닥/중력 유지. PhysxCfg.solve_articulation_contact_last=True와 reset전후 readback 유지. 현재9 acceleration drives 중 새 jaw두개만 name으로 지정해 force drive kp1000N/m kd20Ns/m(초기 가정), cap10N 이하로 접촉 제어한다. pinion cap0.2Nm/기존 acceleration 유지, mimic targets qB=qA, pinion=-74.074074074*qA. 소프트웨어 target coupling이며 실제 gear 접촉/mimicconstraint 검증으로 주장하지 않는다. 이 새 gripper force 모델을 arm gain 변경과 혼동하지 않는다. 실제 USD driveType/reset 후 gains/caps/velocity readback과 결과를 보존한다. SDK/API 미지원이면 failclosed, 가짜 pose로 폴백하지 않는다.

신규 물체는 dynamic rigidbox, mass0.002kg·실제 dimension/inertia/collider/friction읽기 검산, kinematic=false/gravity enabled. 새로운 object material은132scenario와같은 static0.8/dynamic0.6/restitution0의 가정값. source/target narrow pedestal은 static rigid geometry이며 ground는 원0 유지. 최초 timeline 전 object pose 초기화만 허용. 시작 후 object setpose/kinematic/parenting/fixed joint/weld/teleport/attach성공 금지. 손가락 접촉과 마찰로 실제 운반한다. object.sleepThreshold를0으로 지정해야할 경우 새scene가정으로 핀/읽기 증거를 남긴다. 물체 support그림/색만으로 실제 집기를 주장하지 않는다.

## task와 판정
실제9named joint q/qd, arm gravity/COM/cap/floor, object tensor worldpose·linear/angular velocities, source/target support contacts와 양jaw-object contact를 매120Hz current step에서 읽는다. SDK RigidPrim get_world_poses(wxyz), get_velocities()->(linear,angular) API를 actual 설치와 대조한다. contact bodypaths는 owned object/robot bodies, sameLab/Kit/cache/context/stage/clock proof를 guard전에 남기며 CPU implicit attach0 정책은 원129 현증명 결합으로만 허용한다. stale callback/borrowed vector/overflow/foreign stage를 성공 증거로 사용하지 않는다. 최대256contactpoints/8192primitive 상한과 immutable copies, 원primary error 보존. 감시용 추가physics step0. contact missing은 UNKNOWN이지 자동 contactfalse 성공아님.

단계: import/reset/readback→safe_home 정착/그리퍼 open→여섯축 다양한 큰 동작→safe_home→source approach→close→lift/hold→XY운반→lower→open→object settle→retract→safe_home. 실제 phase는132schema의 named boundaries로 매핑. arm 정착 판정0.5deg/1deg_s는 유지하되 새로운 phase/checkpoint와 시간임을 명시; old34/42수용과 혼용0. open jaws는 실제 tracking 기준(슬라이더1mm/피니언0.02rad)을 유지. object가 막는 close/contact_hold는 목표오차로 fake fail/pass를 만들지 않고 actualjaw gap/양쪽접촉/물체pose로 별도 새task판정.

성공 최소: 모든arm 원한도·floor/cap guards, 지정정착 checkpoints PASS; 관절별 실제 max/min/range를 보고132예상범위와 대조; object 양jaw접촉 증거, source보다20mm 이상 실제lift 후0.5초 이상 유지·support접촉 없음·graspframe 상대미끄럼3mm 이하; actualXY150mm 이상 운반; release 후 targetregion XY±3mm/Z±2mm, object speed≤0.01m/s/angular≤0.1rad/s를1초 유지, 양jaw 분리와 gripper open, safe_home 정착. 조기 fault는 current actual state와 primary exception을 먼저 저장하고 후속 diag 실패가 덮어쓰지 않는다. 접촉·질량·관측이 UNKNOWN이면 PASS0.

새RGB640×480/10fps actualRTX, 팔과작은물체가 보이는 camera는132sweptbounds로 결정. 원본RGB/metadata/phase/frame개수/수치와 영상 provenance를 결합한다. 화면녹화나CAD/이전영상 재사용0. 예산은 native≤1800s, legacy adapter hold6/small31/large48=85sim_s 및 phase별예산 hold200/small600/large1000s는 global1800안에 제한, recovery≤600s, 초기 GO20s; 원격period2700 고정. 상대deadline 계산/handshake 뒤 연장0.

## 전송·소비·영상
jobhash는 input read 이전 외부 expectedjob 인수로 검증, payload member SHA·path/duplicates/symlink/exclusivity 검산. 새fresh root/runid/nonce/parentPID+creationtime/run binding·WinJob kill-on-close·active0/reap/timeouts를 보존. 소스F+typedL4/actualrequest/oneshot/capturedcode가 매 생산동작 권위다. mutable root source를 recovery perfile마다 전체재해시해 이전35분병목을 반복하지 않는다: byte-captured frozen 실행코드와 payload가 실제 실행권위이며 transaction 시작/끝/최종publish 경계에서 검산, 각file의 canonical path/role/exclusive write/hash/zip CRC/currentresultseal은 생략하지 않는다. metadata-only/복사된허위current epoch/서로다른run/file substitution은 차단한다.

정상 원SDK lifecycle은 COMPLETE_PRE_CLOSE/CLOSING_APP/code0 또는 APP_CLOSED이며, 앞표현은 owned parent의 실제 SDK REAPED exit0/active0/rawcomplete/timedoutfalse+actual/policy0/정확PIDcreation/run/job+terminal/status원문동일+nativeSeal=RecoveryMinus5+원SDK.verify_records(postnumeric/binding/current)와 결합한 경우만 수용. APP_CLOSED/close반환/remoteparent별도OSwait를 관측없이 주장하지 않는다. 131원처리기는captured130전용이므로 수정/재사용하여새run성공을 만들지 않는다. 불변 raw/sourceF/current report/hash를 새133소비기가 일반검증한다.

최소8AC+5attackclasses HOST: 실제planner/schema·양jaw현재증거/가짜attach/정착/미끄럼·lift/transfer/release/poseunits/rotations·armcriteria·버전/초기화·lifecyclefalsecode/reap/stale/jobsubstitution·capture/ZIPpathrole/duplicate/symlink·one-shot/budget/sourcepin·mediaresultseal. 독립main은 실제테스트와SourceF 전핀검산/union rootcause ledger·nextDISTINCT2 sufficientSOURCE_EXH를 책임scope별로 판정한다. oldthreshold/currentfalse 원장은 보존한다. 실측physics 실패도 원자료를남기고 정적PASS와구분한다.

실제전체 task와 source/L4/lifecycle/영상전체decode/처음중간끝frames 검증 후 MP4 한개를 기존 승인DrivefolderPRIVATE_CLOUD_RESOURCE_REMOVED에 추가(기존 영상/공유권한변경0), provider metadata/actualbytes SHA/size 검산. 내부JSON/설정/권위/토큰 업로드0. 실패를성공영상으로표시하지 않는다.

## L2 명료화·실제 collider 관측

initial safe_home6초 끝에서 다양동작 전에 실제 ARM0.5deg/1deg_s 정착과 실제 open을 확인한다. legacy3phase와132의18subphase/phase_index/boundaries/checkpoints를 명시 매핑한다. contact bodypaths는 Floor/source/target pedestal/object/robot owned paths를 포함한다. No-header UNKNOWN은유지하며 실제 collision extent/contact+restoffset/오차를반영한보수적분리계산은별도의absence proof로허용한다.

Root는 실제130 import-static.json에서 gripper 포함11collider가 whole-link convexHull임을 확인했다. 132의 per-source-component 정적분리와 같다고 가정하지 않는다. source_lower/place_settle에서KG1_A/B의whole-link OBB overlap후보가 관측됐으나 완전SAT/침투는아직미확정이다. cavity를보존하기위해133은 로봇원staticgeometry검증후/reset전 gripper KG1/KG1_A/KG1_B의 UsdPhysics.MeshCollisionAPI approximation을 convexDecomposition으로지정하고 실제USD readback·cooking정책·최종scene을남긴다. 기존URDF/mesh triangles/bodymass/관절frames는그대로, simulation-only 충돌근사변경과원geometry검증을구분한다. 이것만으로cookedgeometry나graspPASS를주장하지않으며 실제양jaw접촉/현재objectpose/이동/놓기판정이필수다. support/object/grippercontactoffset과restoffset은actualreadback하고필요시 objectscale에맞는명시적새scene값(예:contact0.5mm/rest0)으로핀·검산한다. arm solver/gain/cap/판정은유지. 공식API근거 https://docs.omniverse.nvidia.com/kit/docs/omni_physics/latest/dev_guide/rigid_bodies_articulations/collision.html 및 https://docs.isaacsim.omniverse.nvidia.com/latest/physics/simulation_fundamentals.html .

## Root 운영 보정 — 실제 최초전달의 NOT_CREATED 결함 수리

실제 attempt01은 2026-11-08T02:57:05.202635Z에 로컬 WinJob 출력폴더 transport 누락으로 CreateProcess 이전 NOT_CREATED에서 끝났다(child_pid null/GO없음/SSH0/SDK0). 원 attempt/run-result/transport 기록과 period474238.968→476938.968/2700은 동결하고 재무장하지 않는다. 후속02만 기존 max2안에서 사용한다.

새로 실측된 전달 준비/미생성 인계의 제품 결함을 사용자의 현재 집기시뮬 구현·실행 및 자율계속 지시 범위에서 수리한다. Root는 자기 등록한 max2/noR3 계획을 이 구체 결함 수리에 한하여 R3 한 회 추가로 보정한다. 사용자에게 R3나 추가시간을 명시 승인받았다고 기록하지 않는다. 판정만 더 얻는 추가 발사나 기존 두 class/소진 원장 초기화가 아니다: outputdir생성 및 실제NOT_CREATED→안전후속허용이라는 새코드와 실경로 양성/음성 증거를 반드시 먼저 만든다. 원 R1/R2 지적은 유지하며 새 결함의 착지·원장 판단은 비작성자가 내린다.

author carry1850.346841/2700(잔849.653159), main carry2111.3607063/2700(잔588.6392937), 준비/새읽기 포함/동결대기별도/원시간 cap·source8범위·원판정·실물제외 불변. 새 시간예산/새 unit/이름변경으로 reset0. R3는 코드·실효 검수이며 prior PASS를 덮어쓰지 않고 F2/source8/보고서/실패를 exact archive한다. 이후 추가라운드는자동허용하지않는다.

수리: helper.run 직전 owned transport dir를 exclusive로 만들고 exactpath/reparse/current authority를 재검산. previous_gate는 기존 REAPED closure경로를 유지하며, 실제 raw WinJob NOT_CREATED/child_pid null/unknowncreation비해당/GO없음/원prepared/run/transport identity와 파일흔적을 결합한 NO_PROCESS_CREATED 경로만 추가한다. 존재하지않는SDK/SSH를REAPED나exit0으로꾸며쓰지 않는다. UNKNOWN·created/unreaped·malformed/missing·성공후재진입은거절한다. actuallocal WinJob child 경로와 미생성 경로 HOST를 비작성자가 직접 재현하며 이들은 실제Isaac/물리수용으로 표시하지 않는다. 원01 consumedmarker/기간/파일삭제0, 새02 freshidentity+2700고정/GO1/retry0, 전체원allocation합5400/SDKmax2는늘리지않는다.

## 실제 첫 SDK 홈 실패 후 마지막 R4 수리 — 기존 시간 안, 실제 SDK 두 번째 슬롯

실제02 SDK39288은importPASS 후6.0초/720step에서J3위치오차0.629135681deg·속도1.160265365deg/s(원기준0.5deg/1deg_s) 및pinionerror0.727803448rad로정지했다. transport54344/SDK39288 모두소유기록REAPED·active0,SDKexit1,frame60/validmotionrows720,큰동작/집기NOT_RUN. 모든원raw/ZIP/lifecycle/기간475269.078→477969.078을무수정보존한다.

피니언은qA>1mm 구간 actualqR/qA median−1.2938153 vs명령−74.074074rad/m, degree/radianfactor패턴과8.96e−6rad관계잔차가관측됐다. 단순시간부족으로기각하지않는다. 현재rc14가어떤mimiccompatibility를적용하는지는확정0; 공식6.0schema는degrees,6.2문서는Newtonmimic을PhysX가소비하지않는다고쓰므로전제를섞지않는다. 이번수리는의도된software-target coupling을명확히하기위해reset전PINION의importednewton:mimicEnabled만false로명시하고실제USDreadback/기준joint/coef/unit기록한다(원URDF·모델·다른mimic·armgain/cap/velocity0변경). 실제pinion이원SI targets를추종하는지home기준으로다시검증하며미확인정규화를성공으로표시0. degree계수로소프트웨어target를57배늘리는우회0/기준완화0.

초기home동작6초뒤2초stationary dwell을삽입한다. 정착검사는8초끝,이후원scenario85초의시간을2초이동해총87sim_s/10440steps/10441rows/871RGB/87.1s video. 원132planner/scenario85는불변·logicaltime source0..6→실제0..6,실제6..8→logical6고정,이후logical=actual−2. 모든Task checkpoints/close/lift/transfer/release는같은logical시점/원조건으로유지,6초FAIL원문은그대로이며8초수용으로old6PASS를제조0. legacyouterhold8/small31/large48,renderer/frame schedule/consumer/replay/ffprobe기대개수전부연결. initialdwell은18logicalsubphase 안 home의stationaryextension으로명시.

계산상한만native1980s(33분),phasehold200/small600/large1000s 교집합, recovery600s 유지. remoteperiod2700s안에서parentlimit=min(1980,remaining−602)로끝을늘리지않는다. actualfirstimport484.391s와6초모션약90s를근거로87초변경의계산여유를정한다. arm64/16/cap12_7/모든원속도·floor·.5deg1deg_s·슬라이더/피니언오차기준은변경0.

첫local01은CreateProcess전/GO0/SSHSDK0이므로실제remote/SDK슬롯을소비하지않았다는원증거가있다. originalrecords/명목기간삭제재arm0,로컬attempt03은실제SDK두번째슬롯이며freshID/nonce/고정2700/GO1/retry0. actualremoteperiods2개합5400/SDKmax2라는원allocation은늘리지않는다. thirdlocalattempt입장은sourceF에pin된01미생성+02실제reapedFAIL/SDK1+parentclosure와원identity를모두요구;미확인/PASS후/created-unreaped/4번째거절. 02기존grant재무장0. task-scope의원quote/SDKmax2/2700each총5400객체불변,로컬attempt개수와실제SDK count를구분한다.

Root는자기launch제한의마지막R4를이실제새code/control수리에한해명시등록한다(global4한계,이후추가round0). 추가시간/새unit/oldclasscountreset0: author carry2119.524048/2700(남580.475952),main carry2398.4246255/2700(남301.5753745),각재준비포함·동결대기별도. L2보정논리검토를main잔예산의55초이내에하고동결→author local수리/HOST/F4→같은main잔clock으로마지막코드검수. Source8+plan1/2groupM 유지. src132별도예산리셋0/모델URDF0변경/실물0. 실제user R4/분승인제조0,근거는현시뮬구현실행·자율계속지시이며판정만추가로받는발사가아닌실제새수리/실경로증거가필수다. 원3class·실패·SOURCE_EXH 충분임계와독립관할을보존하고재귀/소진판정은main이내린다.


## 사용자 승인 후속 R5 구현 결속

Root-user-followup-approval-r5.json의 실제 「진행ㅎ9」 승인과 Root-next-repair-proposal.md(61db1793…) 및 최종 L2-followup-r1(9534dbc2…)에 따라 같은133 후속을 누적한다. source9(jaw_components.json 포함)+이계획1=M. 원F4/source8/계획은 author/r4-preserved-before-followup/에 byteexact 보존. 원URDF/메시/132경로/질량관성은 읽기 전용. 실제SI 각jaw6성분의 convexhull12개를 같은rigidbody에 childcollision으로 추가하고 oldwholecollider off, 전후reset 실제12active/owner/points/topology/offset/material을 검산한다. padband432ray 및 boxfullheight576ray의 원면/void 일치 확인. 새shape는 task material .8/.6/0에 명시binding, 이전jaw effectivefriction은 UNKNOWN이므로 실효동일 주장은 하지 않는다. cooked vertices/성공grasp는 실제SDK 전 NOT_RUN이다.

actual93→source85 map과 Jacobian0/.5/1(초기6..8·source_lower50..52 정지, close52..56·release74..78 반속), legacy8/31/54,11160steps11161rows931RGB93.1s를 공통연결한다. 원grasp/정착 사건 actual8/39/57/80/93의 기준을 유지하고52초새gate는 추가하지 않는다. 새positivejaw/object contact는 실제활성component12 colliderpaths와 결속한다. native1980/remote2700/recovery600·gain/caps/sourcevel 원값 유지, poseclamp/weld/teleport0. local04만 새explicitapproval/원03closedFAILreaped증거로 승인,05거절, oldinternalSDKmax2·원periods/history/raw/EXH는 그대로 보존한다. 원130 cap결정은 cap입력이지 새원격권위가 아니다.


## 사용자 추가승인 종료 후속 global R7/R8

Root-user-termination-approval-r7.json SHA5a2f2e4656fdb0d9b9ed4d082751a3d001ea2d9059f509bd14def3b0355611fc의 실제 「추가 승인」과 L2 termination R1/R2에 따라 같은133에서 종료/예산/새입장만 수정한다. 원F5/source9/계획은 author/f5-preserved-before-termination/에byteexact보존. 실제04의86.79초prefix·원93미완/SDK124/parenttimedoutfalse를 유지하며 종료원인을124만으로단정하지않는다.

Native2280/recovery360/large1120을 parentmin(2280,remaining-362), owner native<=remote-360, 두bootstrap leaseheadroom362와 연결한다. 전체2700/handshake20/cleanup2·물리/93map/931PNG/원predicate/immutablecodecpipe는 불변이다. 기존watchdog의PIDhandle/birth/handshake를 유지하면서 prestarted bounded daemonloggerqueue에 phase/global/pipe/disarm intent를 전달한다. stop경로는fileIO/join을기다리지않고, targetkill후최대50ms drain만한다. logger오류/정지는UNKNOWN이며 원kill을무력화하지않는다.

Logger는ownedrun직하파일을쓰고, 부모가모든jobchildREAPED/rawcomplete 후bounded single read하여기존process.json 안에rawSHA/bytes/identity검증entries 또는UNKNOWN을한번embedding한다. 새6번째seal제외/SDKartifact추가0, nativeSeal=RecoveryMinus기존5를유지한다. Log의killintent와실제OSexit/인과는구분한다. 임의124를timeout으로승격하지않는다.

새local05=actualSDK4만새5a2f승인/원04SDK124reap·fullrecovery/currentmissingfinalfiles·job/run/nonce/PIDbirth에결속하며06은거절한다. 역사04의731승인은분리검증하고원01..04기간/GO/실패를재무장하지않는다. 기존작성자3530.478413에추가900을누적한cap4869.838413 및main누적cap5232.1357206/본후속L2L4max2를유지한다. 원class/EXH/historyreset0.
