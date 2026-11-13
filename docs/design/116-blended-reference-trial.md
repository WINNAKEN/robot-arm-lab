> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 116 — 위치·속도 공통 참조 혼합의 구현과 단일 원격 검증 (L1 수리 R2)

2026-11-06 KST. 사용자의 「승인」은 직전 구체 질문과 `outputs/settling-reference-analysis-115/116-proposal.md`(SHA9c211724426f08075079fd60330dcafb8058a356f7b78dbd25e1271cbc3a0a60)의 B2/C4/D4/E4 각1500초·수리/HOST/독립검토 뒤 첫원격부터새2700초 단일시도를 승인한다. 이 문서는 그 승인 범위의 실제 연결을 구체화한 실행 계획이다. 원제안·115 L4/정착실패/소진원장을 덮지 않는다. 승인정본은 OUT116/user-approval.json이다. 최종코드PASS 뒤 같은 범위의 일반 재확인을 반복하지 않는다.

## 목적과 불변

114는 가져오기/정지PASS·motion42초완주지만34초 J3 0.584715°·J5 0.520335°로 원0.5°를 초과했다. 115의 원자료전건/이동32~33 대 hold33~42 비교·별도 AR시간분할은 잔류진동을 재현했으나 유일원인·PD포화를 확정하지 않았다. fullseptic는 J6 .501100391>원.5rad/s로 폐기했다.

새 곡선은 `reach_high_right`(25~33초8초)에만 `s=.5(10u³−15u⁴+6u⁵)+.5(35u⁴−84u⁵+70u⁶−20u⁷)`다. 위치와 정확한 도함수속도를 함께 바꾸며 모든팔축에 같은 s를 쓴다. peak기울기65/32·J6 .465307506rad/s/binary32 .465307504, endpointjerk원50%, peak속도8.333%·peak가속도12.694419%증가를 명시한다. 물리정착 개선은 미확정이다.

그 외 phase·gripper40mm·같은 시작/끝 자세·33초도착·34초판정·42초/5040step/5041obs/421frame·원gain64/16·cap·0.5°/1°/s·물성/한계/모델/바닥·카메라/중력·고정root/완전9DOF·자기충돌OFF/링보류·실물미보정은 불변이다. 원20초/cleanup2/native600/motion900/headroom1380/1680/전체2700도 불변이다. 실물 CAN·RS485/포트·급전/flash·모터/설치·구매/UAC·시계/네트워크/보안설정 변경은0이다.

## 소유와 분할

SRC=`src/simulation/blended_reference_trial_116`, OUT=`outputs/blended-reference-trial-116`. 원114/108과모든기존src·CAD/모델/BOM/펌웨어는 읽기만 한다. root는 본계획·OUT 메타데이터/관측기·최소 HANDOFF prepend/SESSION append를 소유한다. 공유문서는 현재바이트를 보존하고 foreign MP18/후속작업을 되돌리지 않는다. `protected-baseline.json`의 source79/CAD22/critical1129/11313/11411/11513을 전후 확인한다. MP18 HEAD726b306c…와 current CODING_RULES는 별도 소유다.

| 단위 | 실제 운영 소유 | 구현+HOST+수리+root귀속 cap |
|---|---|---:|
| B2/root | bootstrap.py, test_bootstrap.py | 1500초 |
| C4/구현자C | driver.py, config.json, test_driver.py, OUT/execute.py | 1500초 |
| D4/구현자D | validate.py, decision_schema.py, test_validate.py, test_decision_schema.py | 1500초 |
| E4/구현자E | scene.py, workspace.py, program.json, test_scene.py | 1500초 |

mutable13+harness1=14(compile Python12/JSON2). generated workspace/IR/census/관측raw는 별도 증거이며 운영소스 수에 감추지 않는다. 각작성자는 첫 copy/write 이전 UTC/monotonic을 저장한다. 5/19/22분 실측·root검증 reserve≥150초를 남기고 동결한다. 의존입력 대기는 바이트동결+시작/끝기록으로만 분리하며 진행중작성시간을 대기로 숨기지 않는다. 재개는 같은누적시계·reset0이다. 시간소진은 보수종결이며 타그룹으로비용을옮기지않는다.

L2/L4 각max2·main/lens 각각2700초·noR3, L+ 다관점 병렬이다. 기존 두 비작성자를 재사용하고 구현자는 자기그룹 최종검토자가 아니다. 막힌 Sonnet bridge를 재실행/수리하지 않으며 기승인 동일계열 비작성자 폴백·공통편향을 기록한다. 외부계열 재가용 시 전제 재검증 우선이다. 라운드 지적은합집합, 작성자는수리하고검수자는patch하지않는다.

## E → D/C/B 입력 연결과 새 데이터

고정 profile은 program에 `reference_profile={"name":"reach_high_right_half_quintic_septic_v1","phase":"reach_high_right","blend_numerator":1,"blend_denominator":2}`로 명시한다. 정확한 key/type/value를 요구하며 unknown/missing/boolean/nonfinite/옛프로필의 조용한quintic fallback을 거절한다. 파생2초 render_smoke에도 같은메타데이터를 유지하지만 해당phase가없으므로 초기hold 명령은 원본과같다. full42 motion은 원prefix9+observehold8의 동일 segment 구조를 유지한다.

E는 새 scene.target_at/validate_program peak와 workspace.make_program/target_at/build/validate_result의 peak속도·가속도·전경로를 수정한다. 정규화미분 `s'=15u²(1−u)²+70u³(1−u)³`, `s''=30u(1−u)(1−2u)+210u²(1−u)²(1−2u)`와 analytic extremum을 쓴다. 다른phase는 원quintic다. 공간직선경로가같아도 시간표본을다시평가한다. PD/FF/remaining_caps/checkpoint기준은수정하지않는다. 아래USD 증거 경계 때문에 **scene.py는 위 기존두함수의본문만 바꾸고 모듈docstring/import/global/기타함수와두함수signature는바꾸지않는다. 새scene helper정의나모듈상수는추가하지않고profile/curve/peak를inline한다.** workspace.py에는계획상필요한순수helper를둘수있다.

중요한 실제 의존: 원D.produce_workspace_receipt는 기존 `ref/workspace.json`을 validate_result(full=True)로검증하며새데이터를만들지않는다. 따라서 원workspace JSON을 복사/부분패치하거나 새프로필의수용으로 재사용하지 않는다. **E의 동결된새workspace.py로 원모델16/원oracle을 사용해8192샘플/6241경로상태의전체52초 sampler를새로 build하고 full검증**하여 OUT/workspace.json을exclusive 생성한다. sampler52와실제motion42를구별한다. 이 데이터의program으로부터 D._program_check가 원prefix9/34초+8초hold의42초를도출한다. 동결된 E코드 SHA와 모델/oracle SHA가 새데이터에들어간다. 코드수리가필요하면 이전데이터/코드/핀을보존하고명시새revision으로다시생성한다.

refs11는 **원래10개불변+새workspace1개**다. C cfg.refs['workspace.json']은 새경로 OUT/workspace.json/실제SHA를 가리킨다. source/runtime 이름21·model16·ref11·key48는 그대로이며 typed20/opaque28도 그대로다. immutable old10815에서E4를빼11로만들고owned9(원5+E4)+A1과합쳐runtime21을구성한다. A는 원110 winjob.py SHA2ca8c90616026a103eb41da18c33f34b012bcd56439cb39af967ea9bf2f683b0 그대로의116 alias만허용한다.

현재설계 census는 `dependency-census-known41.json`(기존42에서새workspace자리1개대기)이다. 새workspace가확정되면 실제SHA/bytes record1개를더해 **pre-receipt42**, fresh receipt를더해 **deps43**으로seal한다. 그때raw census/records canonical SHA를 B와C가결속한다. 원114의46/47 상수를단순남기거나새데이터를검사에서빼지않는다. fullreceipt12·import49·payload62/capsule63은실제구성으로다시유도·검증한다.

E가profile코드/새workspace 데이터를 먼저 동결한 뒤 D의_WORKSPACE_CODE_SHA와 C config.refs, B census를 최종결속한다. D 새정책과C/B를결속한 뒤 전체HOST/receipt를생성한다. 부분작성중피어를수용freeze로오인하지않는다. targeted HOST는명시된대역만쓸수있고 실제full producer/새reference 검증은 root가별도로실행한다. 그 비용은 B/D/E에보수귀속한다.

E의실제연결에는 test_scene의capture를immutable108에서,scene/newD를owned116에서읽는resolver와새workspace경로·exclusive115와별도E보고서경로가포함된다. 원29 HOST case를보존하고회귀를추가한다. workspace.write_json/main의옛073출력경계/덮어쓰기기본값도새OUT116 exclusive경계로바꾼다. 원073/108파일은쓰지않고실패partial은보존한다. sampler-program52는OUT의별도이름이며SRC/native42를덮지않는다. D._memory_modules의닫힌import facade와맞는기존stdlib만사용하고불필요한새import/global IO를추가하지않는다. 독립3-way수식대조는sampler52와native42가같은0~34초에서하며native42의33~42고정hold는원42source와별도로검산한다.

## R1 지적 수리 — 원 USD 증거와 새 참조 소스의 경계

원b11368e0…계획/주L2R1 fe7a21bf…·보조bdd1328f… BLOCK16/2(B1/I1)·distinct1을 before-L2-r2/manifest.json에보존했다. 원B.context는검증된old108 USD기록에대해runtime scene.py/root_binding.py의전체byte SHA가oldfreeze와같아야한다고요구한다. 정당한참조함수수정도이조건에막히므로이충돌을수용했다. 原보고서를PASS로바꾸지않고이실질수리를새L2R2에서검토한다.

원USD와현재소스를연결할때oldscene 전체byte동일성만요구하던조건을아래제한된증거로대체한다. **USD검증자·원USD/oldfreeze 핀·root_binding.py의원byte 동일성은그대로유지**한다. 단순guard삭제/oldscene이라고라벨만붙이기/새현재source검사생략은불가다.

1. 원scene raw SHA `f3b4e08491124ea3daf13949dc994618374c0be8cd6267f56ef7ac4789fd1807`이old108freeze.source.scene.py와같음을계속확인한다. L4비작성자가이원raw와아래투영의연결을원보호소스에서독립재계산한다.
2. 원Python3.12 `ast.dump(ast.parse(raw),include_attributes=False)`에서최상위기존 `target_at`·`validate_program` 두 FunctionDef만제거하면37개node중35개의module투영이남는다. 그 UTF-8 SHA는 **5babee70c8f3c8a85026ee51e86b52b12e04943fc6788206f901bfd59ab61f9f**다. 새현재scene도정확히이두정의가각1개여야하고,나머지전체module 투영은이SHA와같아야한다. 새import/helper/global/물리함수/초기화/PD/FF/COM/캡/기구학표현변경은거절된다. 현재전체scene의source/freeze/48현재byte핀은별도로계속검사한다.
3. 제외하는두정의는원서명 target_at(program,time_s), validate_program(program,model) 그대로다. decorator/annotation/default/vararg/kwarg/posonly/kwonly/type_params/type_comment/async·중복/누락정의는거절한다. 정의시점에실행되는우회가없어야한다.
4. 두본문은 `scene-physical-binding-contract-r2.json`(SHA **6a16257628ab47f84cc65bdbe02313b0ef10b35f0f2b5e154ca5e59c3da0041c**)의닫힌참조수식언어를만족해야한다. statement는Assign/For/If/Expr/Raise/Return뿐이며 Import/Global/Nonlocal/nesteddef/ClassDef/With/Try/While/Yield/Lambda/NamedExpr/AnnAssign/AugAssign/Delete/Starred 등은거절한다. 원본에있는안전한이름call 및math.isfinite/sqrt·컨테이너읽기(get/items/keys/values/copy)만허용한다. 이름call whitelist는계약에고정되어있고외부call/callable별칭/Call·Subscript를callee로쓰기/IO·SDK·eval·exec·globals등은거절한다. type call은1positional인자만허용한다. callback/stararg/keyword인자도거절하되원형의q.update/velocity.update에세고정KG1 keyword를쓰는경우만예외다.
5. 모든Load 이름은인자·본문의local Store이름·고정callee/builtin scalar type·math에한정한다. 고정callee/type/math이름및인자에는Store를허용하지않는다. Attribute는허용된단순이름receiver의허용call callee위치에서만가능하며다른attribute load/store는거절한다. update는local q/velocity dict에만허용한다. q/velocity/maximum은literal Dict/DictComp로만직접대입하고다른대입·루프/별칭으로재결속하지못한다. Subscript Store는그local maximum[name]만가능하며인자program/model·그하위객체는수정하지못한다. 현재old두함수본문은이언어의양성이며새scene도같은제한안에서inline수식을작성한다.
6. B는이검사를context의이미열린원owner/Fence안에서현재source bytes에수행한다. ast는stdlib이고새설치/SDK모듈을요구하지않는다. 제어경로에큰JSON/수치policy실행을추가하지않고원20/cleanup2·현재읽기·token/thread/end를유지한다. 해당설계JSON은설계pin/리뷰입력이고runtime추가파일로읽지않는다. 원raw/projection 상수와검사코드는검토된B소스에결속되어deps43/runtime21/key48/capsule63을유지한다. AST표현은사용중Python3.12로고정하고다른버전/표현이면조용한대조생략없이거절한다.

이증거의범위는옛USD의물리authoring/초기화/PD/FF와새참조수리의영향경계다. 참조수식정확성·새profile의수용·물리정착·임의Python에대한일반보안sandbox를이투영만으로증명한다고주장하지않는다. 수식은독립D/E·全HOST·실제새native가각각검증한다.

HOST에는old양성·실제새E양성과현재actual-B.context 양성을포함한다. 물리함수/모듈상수/import/global/최상위helper/root_binding변조·두함수중복/누락·default/decorator/annotation side effect·본문IO/외부call/인자변조/callback/이름shadow/locals별칭/attributewrite의coherent negative는실제새B검사/최종context에서거절해야한다. 2함수참조수식만변경한경우투영양성이라는사실을곡선정확성으로세지않으며잘못된수식변형은E/D gate가거절해야한다. guard자체의actual read/parse stall도원20내거절하고control timing/policy0를재관측한다.

새logical class CURRENT_REFERENCE_OVERRIDE_CONFLICTS_WITH_LEGACY_WHOLE_SOURCE_PROOF의R1 union1/open1과B.context physicalUSD↔Ereference/support착지를유지한다. 주·보조가사전판정한next DISTINCT2는이current bridge와실제support sourceEXH의충분임계이며runtime전체/물리USD도메인·oldsettling/numeric/performance/FS/115coverage로확장하지않는다. 이번수리는아직실제폐쇄가아니며L2R2논리판정후L4에서코드폐쇄를독립확인한다. 원q+qd대안진입허용판정은이번BLOCK을무효화하지않는다.

## D 숫자 역할과 독립 소비

설계 IR `OUT/json-numeric-role-contract.json` SHA **c0a162d8a90f72d8f7c8141ef93c99a0fe27277fa856b007c7668090318766ff**를 사용한다. 원IR자산/과거판정을보존하고 source/program.json 및 새ref/workspace.json.program에만위profile의역할을추가했다. `kind=literal_string/value`는정확문자열을검사하되숫자/booleancoverage합에더하지않는다. profile object의 `exact_keys=true`와 integer의 `exact_value`를해석기에추가해정확1/2·정확keyset을검사한다. 그외기존numeric/boolean/array/mapping/URDF/STL/opaque 규칙은보존한다. 실제수치소비자가profile을사용하면서IR에서누락되는경우는허용하지않는다.

D는 producer E를정답함수로호출하지않고 독립식으로 target/reference_velocity와profile정확성·_program_check를검증한다. 기존물리45함수 중 target/reference_velocity의필요부분외나머지(verify_workspace의기존fresh경계포함)와FF/COM/fixedbase/torque/PNG/관절·바닥·정착판정은AST/실효로보존한다. 필요추가profile helper는단일폐쇄정책이다. 새workspace generator pin과역할IR pin은현재바이트에결속한다. 원helper·oracle·model은그대로다.

제어용API는기존 closed4 identity-only이고 D가결정값을소비할때는매번actual policy를새로실행한다. cache/skip/fastflag·자료/계약반환우회·현재48값검사축소·큰JSON파싱을control clock경로로다시넣는수리는금지한다. C/B의 token/thread/end/claim/lease/OS세션수명·현재바이트·exit+EOF+reap과原20/cleanup2는불변이다.

## HOST·검토·원장

다른phase0~25·33~42는원114와전체9축 targets/reference_velocity/binary32/gravity/phase를비교하고,25~33은혼합독립식과대조한다. 실제profile source 경로와독립consumer/workspace경로를함께검증한다. 양성은원모델·완전source·새workspace/receipt를사용한다. fullseptic·qd만혼합/q만원본·producer만변경/consumer옛값·누락/다른profile·bool/nonfinite·비정상비율·원34초삭제·기준완화·누락source/old15/oldworkspace/oldreceipt/변조pin을거절한다. 새profile2초smoke파생/42초full·위치/속도한계·C2/endpointjerk·analytic peak/float32경계도검사한다.

원oldJSON3/ET03의coherent재봉인·全format/현재byte변조/두번째use·lifetime stall/largeargv/원수명·missing-nativeapproval·singlequota·회수실패보존을회귀한다. Root는 각그룹전체HOST·Python12compile/JSON2parse·actualfullsampler생성기록/新D fullreceipt producer·typedcontract/원receipt구조를확인한다. 이HOST는실물/native수용이아니다.

첫L2비작성자가반드시판정: old SETTLING_VARIANTS union15 및 VELOCITY_ONLY EXHAUSTED/원34초 J3J5 OPEN은유지한다. 이번은q와qd의동일공통시간법칙+새generator/reference/독립consumer이고oldqd만패치의자동재개가아니다. 대안source/기전·잔여지적답변·새예산/사용자승인에대해신선116진입허용여부를사전판정한다. BLOCK이면코드/시뮬발사0이다. 단순새폴더이름만으로소진을해제하지않는다. 원실행실패114는코드검토PASS로소급닫지않는다.

그외連続原장: numeric2/current114closed·historical112open1/BLOCK/sourceEXH/noR3·次DISTINCT3, performance1/current114controlcodeclosed/target3admission成功·old113failure原문/次DISTINCT2 B/Cidentity↔Ddispatch実착지support sourceEXH, FSsemantic3/currentobserverclosed/次4, workspace-reuse等原scope도유지한다. 115 coverage1/currentR2closed/原R1BLOCKopen1·次DISTINCT2 currentresponse inclusion/support sourceEXH는진단scope에만결속한다. 116실제물리정착실패를새numeric/performance/coverageinstance로자가가산하지않는다. 매라운드지적합집합/중복/착지·폐쇄·소진/다음충분임계는비작성자가기록한다.

## 18개 이진 수용 기준과 gate

| ID | 필수 검증 |
|---|---|
| B1 | application read 앞원수명·현재authority/input identity·native없는권한거절 |
| B2 | exact116 plan/freeze/userapproval·원A·최종typedreview18/0·그룹6미결0 |
| B3 | 原HELLO/clock/claim/lease/EOF+exit/reap·단일firstremote·largeargv부적합거절 |
| B4 | mutable14/runtime21/key48/model16/ref11/deps43/receipt12/import49/capsule63 실제구성 |
| C1 | provider현재source/input48·scope/thread/token/end·두번째usefresh·closedreturn |
| C2 | 原20/cleanup2 actualclock path·lifetime stall/현재변조거절·시계리셋0 |
| C3 | quota1/1/1·헤드룸1380/1680·기한후추가원격0·실패원본회수분리 |
| C4 | 원native600/motion900·실제caller/template/sourceoverride·prepared/pinned바이트일치 |
| D1 | 全format/numeric역할·literalprofile/requirednodes·coherentJSON3/ET03 회귀 |
| D2 | controlidentity closed4 policy0 / 각numeric use actualfreshpolicy·oldreceipt거절 |
| E1 | 정확고정profile·smoke파생/42초full·unknown/bool/nonfinite/옛프로필거절 |
| E2 | 실제q/qd/encoded命令·독립혼합식·원나머지phase全9축보존/C2/jerk |
| E3 | 새workspace full8192/6241·generator/model/oracle/프로필핀·fullreceipt재생성 |
| E4 | 원위치/속도/cap/34초정착/重力/floor·새analytic peak·잘못된변형거절 |
| I1 | B↔C↔D↔E 전체입력·役割IR/模板/프레임·수용/原실패 구분 |
| I2 | source79/CAD/critical보호·그룹누적caps·관측기prearm/선별raw·원장/공통편향 |
| P1 | control clock경로정책0/新수치결정fresh·원20·일반입력정상성·역성능기각 |
| P2 | 수량/경로/전source/current변조·Windows완전argv·전체caller/runtime/회수bound |

typed review는 unit116/정확phase/round/plan/freeze·required18/met18/unmet0·criteria정확18ID·B/C/D/**E**/integration/performance각PASS/미결0이다. main은lens최종SHA를pin하고순환하지않는다. old14행·old114검토/receipt·未검토E를통과시키지않는다. **이번L2의최종R2와L4의실제최종round는별개**다. B의옛hardcodedL2-r1 path/round1을최종L2_ROUND=2/path/실제최종main SHA로결속하고,context metadata/capsule/test fixture/root bind도정확한L2-r2를읽어야한다. L4는자기실제round1또는2를사용하며이를L2 round와혼동하지않는다. BLOCK인R1을runtime권한으로읽지않는다. 이codePASS와아래targetnative수용을구별한다.

## 최종 codePASS 뒤 승인된 새 원격45분

모든gate통과뒤root가실제production CLI의missing-nativeapproval음성(exit2/attempt0)을확인하고새closed12 nativeapproval에userquote「승인」/본plan/현재freeze/mainL4를결속한다. 그전nativeapproval/remote-attempt/SDK/SSH0이다. 로컬Tailscale daemon/peer는읽기만조회하고dummySSH를하지않는다. 첫원격직전에새2700초exclusive예약, 실제import1→2초render_smoke1→motion42초1이고실패도소비/retry0이다. 새codeprofile의기하/정착을실제관측한다.

import/정지수용·現在pin·원헤드룸이충분해야motion을발사하며실패면원기한내닫힌증거만회수한다. 원시계20/cleanup2/native600/motion900/headroom와원2700을늘리거나늦게시작하지않는다. 남은시간재사용/기한뒤SSH·SDK·cleanup0이다. wrapper의대기한계와전체prefix IO한계를혼동하지않는다. 원A로prearm된로컬offline관측기는現在116 context/실제닫힌raw만소비하고그본실행이아니다. frame이있을때만실제영상생성한다.

원34초정착/J3J5·그밖原checks를그대로평가하고늦은42초통과를소급정상으로바꾸지않는다. user기준/gain/cap/모델변경없는단일변경시험으로114와비교하고실물성능·실물CAN수용을추론하지않는다. 종결은정확현재결과/실패/예산·sourceEXH判定/인계·선별localcommit이며push0이다.
