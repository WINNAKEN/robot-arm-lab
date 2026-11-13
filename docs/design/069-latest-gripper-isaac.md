> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 069 — 최신 팔·개폐 그리퍼 Isaac 시험과 실제 렌더 영상

사용자 명시 권한: 068 개폐 URDF를 최신 Isaac 모델로 가져와 시뮬레이션하고 영상을 기존 Google Drive 프로젝트 영상 폴더에 보관. 실물 보정·실제 모터/CAN·플래시·재부팅·설치·구매·학습 없음. 질량·관성 가정, 링 형상 검증 보류. 작성root, 비작성자 공통 L2 최대2(원R1보존/이번R2최종). 068은 별도 작성자/경로/검토다. 초기L범위는운영규칙대로069A와069B의M두단위로분할한다. 11:53부터현재까지읽기전용조사·통합L1/L2이며M구현전이다. 069A는SDKbootstrap/import/source-actual검증/전송(driver.py,sdk.py,validate.py,test_host.py,launch.ps1,config.json 총6파일),069B는실제물리동작/촬영(scene.py,capture.py,program.json,test_scene.py,README.md 총5파일)로소유와코드검수를분리한다. 각M은L2승인후작성시작부터45분, A/B병렬가능하나Bnative는Aimport수용후만가능하다. 각각L4최대2회이며처음소스구현시실제시작/종료시각을고정한다. 원13:23UTC전체상한을넘지않는다. L2R1finding/소진계보/남은R2를분할로초기화하지않으며R2에서A/B통합논리를함께검토한다.

## 소유와 원본

소유는 이 문서, `src/simulation/latest_scene/`, `outputs/isaac-gripper-v1/`와 Drive의 기존 날짜별 영상 폴더 안 신규 영상/출처 파일. 068/기존CAD/BOM/core/.dev/구URDF/041~067코드는 읽기만 한다. 기존066의 외부 고정PD가 실패한 사실을 유지하고 같은 gain 후보나 같은 worker를 재실행하지 않는다. 이 단위는 새 11물리링크·9물리관절(독립7좌표)의 가져오기/내장 acceleration drive/실제렌더 경로다. 모든 기존 provenance7/physical6 EXHAUSTED·eligibility2-next1/firstfault/047·063·066이력을 유지하고 비작성자에게 착지·소진 판정을 요구한다. 기존 외부 hook 차단을 재시도하지 않고 같은 계열 비작성자 fallback 한계를 기록한다.

068 L4 PASS 이후 canonical XML/11mesh/manifest/provenance/source를 실제SHA와 정확한 파일집합으로 동결한다. 상위 068모델 q0는 기존팔 표시자세, gripper opening=.040m. root는 canonical XML에서 직접 parent/origin/rpy/axis/limits/mimic를 파싱해 독립 FK·질량원장을 계산한다. 068 helper를 root수용 오라클로 호출하지 않는다. 068의 마지막 승인 지문에서 어긋나면 실제 착수 전에 FAILED다.

## 단계·실행 예산

1. 읽기 전용 SDK 소스/API 조사(앱 초기화 없음)는 단계 예산과 별개로 근거를 저장한다. 실제 importer config/converter·Articulation·Replicator create/annotator/orchestrator를 기존 SDK에서 읽어SHA를 기록한다.
2. 새 `import` 목적 native1회, 상한600초. 고정 SDK6.2rc/SDK NumPy/SciPy·Warp + 기존 sealed048 Torch2.11cu130을 proven 순서로 초기화, 실제 module origin/version/CUDA GPU합6/before-after identity/SDK부트스트랩을 관측한 뒤 검사한다. 설치나 새 provider 탐색 없음. URDFImporter는 실제 canonical XML을 가져와 saved USD와 snapshot을 보존한다. fix_base=True, merge_fixed_joints=False, collision_from_visuals=False, allow_self_collision=False. 원 XML/mimic를 임의 제거하지 않는다. 실제 static USD의 canonical11관절(9가동+KG1_mount/tool0_mount고정2), fix_base world고정제약과11물리body 전체를 원 XML에서 유도한 정확한집합으로 대조한다. 이름/종류/parent-child/양끝world앵커·회전closure/axis/limits·11mass/COM/principal회전/fullinertia·visualmesh/scale/worldbounds·q0/tool0를검사한다. 모든11canonicalcollider의owner/localorigin/rpy/box8corners/scale/enabled가 source와맞고 누락/추가가없어야한다. 8corner는 실제USD Cube/boxMesh점과링크local matrix에서계산하며collision이있는데body필터로누락시키지않는다. importer가mimic을유지했는지실제API/schema/topology로관측한다.
3. 새 `simulate_capture` 목적 native1회, 상한600초. A가검증한같은model+SDK+backend코드지문과정상원본import결과가선행조건이며 새 작업원장에 실패도 예약소비한다. 저장USD 참조를 다시 열고 실제 관절/링크 이름에서 배열 인덱스와 경로를 구한다. 생략된 링크/축/미지원DOF는 명령 전 실패한다. reset뒤 실제11RigidPrim tensor의mass/localCOM/principal quaternion/fullinertia(실제arrayshape/배열순서포함)를관측하고 canonicalinertial origin/rpy/tensor를변환한것과대조한다. 정적USD통과가 runtime물성대조를대신하지않는다. 모든physics소비자와명령9관절·11body의이름/경로는정확한canonical집합과일치해야한다. 단일 CPU IsaacLab SimulationContext(dt1/120, use_newton_actuators=False)와 실제 SDK native engine time을 사용한다. 검증된 단일 physics view 바인딩을 새 동적11링크 소비목록에 일반화하며 기존 private API/source/manager identity 검사를 유지한다.
4. `render_replay` 목적은 계획상 이번에 사용하지 않는다. 실제 시험 중의 native RTX frame을 얻지 못하면 software replay로 대신하지 않고 영상 미실행/실패로 남긴다. 각 목적 native는 실패 포함1회이며 소스 수정 후 조용히 재실행하지 않는다. 기계·독립 L4를 먼저 끝내고 native를 시작한다. A import에쓴model/SDK/A-backend코드지문이변하면전단계증거를새입력의전제로사용하지않는다. B전용scene/capture/program추가는A원본을포함한명시적인별도입력서명으로검증하며A결과와원job/terminal/USD SHA를원본채로결속한다. A/B소스서명과공통model·SDK서명을혼동하지않는다. 자식은 숨김 실행, keep-awake process-scoped, 600초 시 실제 owned PID 종료/회수·timeout 판정·원 종료코드와 정책코드를 별도 보존한다. SDK init 중 예외·app.close 예외도 nonzero/firstfault로 보존하고 미생성 영상은 명시한다.

## canonical 전수 프레임과 허용 정상화

현재 068 source의12link(11physical+빈tool0)/11joint/11boxcollider를 직접파싱해 기대집합을만든다. 관측이있는것만기대로삼거나 DOF9개만으로고정제약을생략하지않는다. 고정KG1_mount와실제fix_baseworldconstraint는각bodypose×localjointframe양끝이world에서닫히는지 검사하고canonicalfixedtransform과비교한다. rootworldfixed는body0없음을worldidentity로해석하고Base의constraint위치/회전을검사한다.

tool0는원canonical에inertial/visual/collision이전혀없는frame-only link이며 이조건이아니면아래정상화금지다. importer rawUSD/snapshot을먼저보존한다. tool0가autophysical로만들어졌을경우에만 그tool0의RigidBody/Mass/PhysxRigidBodyAPI와그tool0를child로하는단하나tool0_mount물리constraint를제거하고, 같은이름의KG1자식Xform으로canonical+Z.103m/회전을명시해보존한다. 원canonical과외부URDF는무수정이다. 이정상화의전후11physicalbody/다른joint/mesh/collider/물성은동일해야하고, 결과tool0는물리body가아니면서canonicalFK를따르는지대조한다. 원고정frame의표현을물리제약대신Xform으로옮긴명시mapping이며 자동질량수용/프레임누락이아니다. importer가이미nonphysical이면그대로두고같은frame검사를한다. 임의의다른link/joint삭제·좌표보정은허용하지않는다.

floor는sourceconfig의 `/World/Floor` Cube size1,scale[2,2,.02],translation[0,0,-.01],회전identity,CollisionAPIenabledTrue인정적형상으로만든다. root는실제8worldcorner/topZ0/ownerworld/static/bodyAPI없음/enabled를원config와대조한다. 로봇11collision전부+floor의exactpath/owner/shape/basis/points/활성·selfcollisionFalse를보존한다. 이결속은collision-free경로/쥠힘수용이아니다.

## 제어와 시험 조건

논리 gripper opening_m 0..094m에서 d=opening/2-.020, raw A/B=d, pinion=-d/.0135. 실제 import의 mimic/DOF 구조를 기록하고, native에9DOF가 노출되면 세 대상에 이 식의 일치 target을 준다. native mimic가 없는 경우 이 제어는 명시적인 target 동기화이며 물리적인 기어/랙 힘결합 검증이 아니다. 다른 DOF topology는 자동 대체하지 않고 명령 전 FAILED다. canonical URDF의 의미는 보존한다.

내장 acceleration position drive Kp64/Kd16은 이 모의 모델용 명시 가정이며 사용자 승인 물성/실물 게인이 아니다. 기본 arm effort cap[3,6,5,2,2,1]와 068의 jaw/pinion effort/velocity/position 한계를 그대로 읽어 적용하고 actual readback을 저장한다. 외부066 explicit PD를 쓰지 않는다. q/state/velocity를 재설정하여 관측을 목표값으로 바꾸지 않는다. 초기화 이후에는 targets/efforts만 명령한다.

프로그램은 source JSON 고정: 초기1초, opening .04→.08 3초→0 5초→.04 3초, 팔6축 동시 ±3deg 3초→표시0 3초, 1초 정착, 중력ON 표시0 3초. 각 전환은 quintic smoothstep이며 각 원 URDF velocity 한계 이내임을 실행 전 분석한다. 접지판은 로컬 USD primitive, selfcollision OFF(그리퍼 group AABB가 겹치는 proxy임을 명시), grasp물체/쥠힘/충돌없는 경로를 검증했다고 하지 않는다. 실제 런타임의 position/velocity/FK/조인트 앵커·축/좌우대칭/피니언비율/실제 native 시간과 settle checkpoint를 기록한다. 팔 정착0.5deg·1deg/s, jaw 각0.5mm·1mm/s, pinion2deg·3deg/s를 조건별로 판정한다. 명령 추종 transient와 정착 구간을 구분한다.

중력ON에서는 actual native generalized gravity query 전체 shape/full values/names를 관측하고 offset=width-DOFcount인 0/6 두 layout만 허용한다. 실제LINK pose+actual mass/COM 및 canonical tree로 root와 producer가 각각 계산한9축 gravity reference와 각각 force/torque 단위1e-3 이내여야만 명령한다. 각 drive cap은 original cap-abs(FF)로 남은 만큼 적용해 FF와 drive가 합쳐 원cap을 넘는 접근을 피하고 cap이 음수면 유효 부하FAIL(임의 cap확대 없음). 고정9DOF 순서나 기존7LINK downstream 합을 재사용하지 않는다. 중력OFF/ON 결과는 별도이며 전체 FAIL을 부분PASS로 덮지 않는다.

## 실제 렌더

로컬 설치 Replicator와 UsdGeom.Camera/DomeLight만 사용(외부 asset/texture 다운로드 없음). `create.render_product(camera_path,(640,480),force_new=True)`, RGB annotator deviceCPU attach. 기록 frame마다 `orchestrator.step(rt_subframes=1,pause_timeline=False,delta_time=0.0,wait_for_render=True)` 후 `get_data(device='cpu',do_array_copy=True)`의 실제 uint8 RGBA480x640x4를 저장한다. 렌더 전후 native engine time/physics step은 같아야 하며 별도 physics integration으로 세지 않는다. RGB의 유한/shape/비어있지않음/복수 장면 해시 차이/파일집합·SHA를 검사한다. physics dt1/120과 영상15fps는 구분하고 PNG별 실제 관측 time/target/관절/phase를 sidecar에 결속한다. 이미지 첫/중간/끝을 실제로 열어 카메라·모델·그리퍼·바닥이 보이는지 확인한다. 렌더 clock이 움직이거나 blank면 별도FAILED로 보존한다.

같은 render product에 ReferenceTime annotator도 붙여 time numerator/denominator를 기록한다. ReferenceTime과nativeengineclock은서로다른관측채널이며절대시간동일성을가정하지않는다. fresh wait_for_render뒤RGB와같은renderproduct의referenceTime을얻고,직전/직후nativeengine/step/q/poses가같다는원자료를저장해그상태의픽셀에결속한다. camera frame count를physics step수로간주하지않는다. 설치된 viewport.window 확장을 확인한 뒤 활성화하며 부재면 설치 대신 명시 실패다. capture-on-play만으로 새프레임을 주장하지 않는다.



`wait_for_render=True`만을완료판정으로쓰지않는다. 실제설치orchestrator가한도초과때log+break후정상반환함을수용한다. timeline정지상태에서별도warmup후현재RP에붙은rgb.get_node()/ReferenceTime.get_node()와 `/Render/PostProcess/SDGPipeline/PostProcessDispatcher`의실제OGnode 경로/id/type/compute_count를관측한다. 각capture에서호출전각compute_count를보존하고호출후세count모두엄격증가해야한다. orchestrator내부scheduled `_sim_times_to_write[-1]` rationaltime과postdispatcher referenceTime을읽어post가예정시간이상임을검사하며,동일RP ReferenceTime numerator/denominator가postdispatcher time과맞아야한다. 실제renderer가한번도갱신되지않은경우·예전RGB/ReferenceTime·누락dispatcher/node·동일compute generation·미완료scheduledtime는즉시FAILED다. 부동소수절대시각이아닌유리수분자/분모로대조하고물리engine clock과는분리한다. raw에before/after카운터/식별자·scheduledtime·ref시간·nativeclock/q/poses를저장해root가독립재계산한다. 수신된stdout/stderr의 `renderer failed to advance to the scheduled frame` 또는step scheduling실패문구가있으면그림이있어도renderFAILED로판정한다. native캡처요청자체를재시도해timeout을감추지않고정상warmup은계획된1회초기화로별도기록한다. host음성에는stale동일count/oldref/미완료scheduledtime/유효shape의묵은RGB/렌더실패로그가포함된다.

로컬 기존 ffmpeg로 원 PNG에서 MP4를 만들고 fps/frame수/길이/full decode를 확인한다. 픽셀은 실제 Isaac RTX 출력이며 기록을 CAD software로 다시 그리지 않는다. 파일과 출처 JSON/시험PASS-FAIL을 기존 `docs/GOOGLE_DRIVE_ARCHIVE.json`의 날짜 폴더에 신규이름으로 업로드하고 metadata의 이름/크기/MIME/부모를 재조회한다. Google 원격 digest 미노출은 로컬SHA확인과 구분한다. 결과 영상이 유효시험FAIL을 담으면 파일명/설명도FAIL이다.

## 호스트·반증·종결

입력/모듈패키지/SHA·경로탈출·중복/비유한JSON·파일누락·core없는시작·render firstfault/close/timeout/실패코드·목적중복·서로다른입력 import재사용·기록 bool↔number·native열 permutation·FK/관절/mass/clock·opening follower/mimic·fresh frame shape 등의 의미 음성을 정상 대조와 실행한다. root는 colliderowner/local8corner/shape/scale/floor·fixedconstraint양끝/빈tool0정상화허용범위·runtimeCOM/principal/fullI를하나씩변조하고나머지관측및모든해시를재봉인해거절함을확인한다. 음성기대집합은별도고정이름/개수로선언해빈목록/누락도실패해야한다. root는 savedraw에서 actual pose/FK/각종속관절/engine dt/drive state/원cap/FF 원자료와PNG SHA를 다시 계산한다. simple metadata label만 수용하지 않는다. 원자료·음성대조·L2/L4·manifest·인계/로컬소유커밋을 남기고 같은계열 검토 범위/실제SDK 범위를 분리한다. 실패하면 먼저 원본을 회수하고 소진된 namespace를 바꿔 같은 run을 반복하지 않는다.
