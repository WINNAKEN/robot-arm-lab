> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 112 실행 계획 — 동일 바이트의 정적 workspace 전건 검산 선행 및 권위 있는 결과 재사용

2026-11-05 KST. 사용자 「승인」을 직전112 후보의 mutable8/B2·C4·D2 구현 각1500초·검토 각2700초·각L2/L4최대2·조건부 첫 원격2700초 승인으로 기록한다. 전체8파일/3그룹의 정확 등급은 L→S2/S4/S2 분할이며 원 후보의 M8 표기는 역사 원문으로 남긴다. 파일/권한/예산 확대는 없다. [원 후보](112-static-workspace-preflight-proposal.md)와 [111 결과](111-results.md)를 보존한다. 111 회차/시도/기한 재개가 아니다. 동일계열 비작성자 폴백의 기존 명시 승인을 유지하고 공통편향을 기록한다. bridge 수리·설치·새 모델 비용·실물CAN/급전/flash/모터·시각setter/UAC·네트워크 변경0이다.

이 파일은 L2 R2 후보다. R1 plan4c053fe8.../주 bfee5b65.../보조 ee7bef5b... BLOCK9/3(C1/D2/I1), 같은112-MAJOR-01 union1/open1 및 두 advisory를 before-L2-r2에 무수정 보존했다. 아직 source0/원격0이며 최종 비작성자 PASS 전 구현하지 않는다.

## 소유와 예산

SRC=`src/simulation/static_workspace_preflight_112`, OUT=`outputs/static-workspace-preflight-112`. 새 mutable8: B는 bootstrap.py/test_bootstrap.py(S2), C는 driver.py/config.json/test_driver.py와 OUT execute.py(S4), D는 validate.py/test_validate.py(S2). 각 첫 source write부터 구현·HOST 누적1500초이며 L4 대기만 분리한다. L2 전 source0이고 각 단위+통합 L2/L4최대2, 검토 각2700초다. BLOCK 수리는 작성자만 하며 마지막 회차 뒤 R3는 없다. main/lens가 B/C/D/통합을 분리 판정하고 지적은 union으로 처분한다.

보호 원10831+1098+1106+1116=51 source와 현재 CAD/MP10 22개를 intake 기준으로 보존한다. 최신 HEAD878ad6c9...는 다른 CAD 작업이 반영된 정상 기준이며 옛111 foreign22 SHA로 되돌리지 않는다. shared-before-112 이후 공유문서는 추가만 한다. 원 정착15/velocity-only 소진·PD/포화UNKNOWN·moving-root 독립교정NOT_DONE·물성가정/링보류는 유지한다.

## 문제와 선택

111 실제 import·정지2초/241관측/21frame은 원 물리 소비자에서도 통과했으나, motion 준비 뒤1680초 headroom이 부족해 launch 전에 거절됐다. 로컬 profile에서 workspace full3회80.591/114.453초, 원 C의 prepare/snapshot/consume/smoke proof에 같은 전건 수학이 반복된다. 원격 함수별 정확 비용은 미계측이다. 기존 gate를 낮추거나 simulation 시간을 늘리지 않고, **pure static workspace 계산만 첫 원격 전에 실행**한다. 실제 SDK/native observation·import·provider·COM·속도·정착·고정기저·프레임·종료 검사는 각 실제 바이트에서 그대로 수행한다.

runtime source20=원 immutable108 중 validate를 제외한15+새bootstrap/driver/config/validate4+exact A helper1. 고정 helper SHA2ca8c90616026a103eb41da18c33f34b012bcd56439cb39af967ea9bf2f683b0는 읽기 전용이다. immutable deps46=source15+refs11+model16+USD3+helper1, 여기에 새 receipt1을 더해47. 원108 순수 USD gate와 실제 scene/root_binding pins/typed8 negatives도 유지한다. runtime20과 mutable8을 혼합하지 않는다.

capsule payload는 deps47+mutable8+metadata5=60, manifest1을 더해61이다. metadata5는 plan/최종L2/해당sourcefreeze/최종L4/nativeapproval다. sourcefreeze.source는 SRC7개, harness는 execute.py1개, dependencies는 정확47개이며 group별 census를 닫는다. receipt는 OUT/workspace-preflight.json이고 새 group workspace_preflight1이다. cfg.refs는 원11개를 유지한다. receipt 자신의 SHA를 config/source/receipt 입력에 넣지 않는다.

## D: 닫힌 메모리 입력과 순수 검산 계약

template_bundle47은 **source20(template config 정확int0)+model16+원ref11**의 닫힌 상대 이름 집합이며 값은 정확 bytes만 받는다. receipt 자신과 import/smoke proof는 이 집합 밖이다. D는 dict를 별도로 복사해 immutable bytes로 고정하고, key 계산과 실제 알고리즘 실행은 그 동일 메모리 사본만 사용한다. 외부 경로/삭제·추가·중복·비bytes/다른unit/비유한·bool 숫자는 거절한다.

D 공개 API:

```
produce_workspace_receipt(template_bundle47) -> canonical receipt bytes
verify_workspace_receipt(template_bundle47, receipt_bytes, expected_receipt_sha256) -> fresh(data, metrics)
bind_workspace(workspace_use_contextmanager_factory) -> None
verify_workspace(model_path) -> fresh(data, metrics)  # bind 없으면 거절
```

producer는 원 workspace.py/고정 sampling-oracle.py와 원 validate_workspace의 전건 의미를 유지한다: validate_result(full=True), 8192 sample·6241 path·model16 inventory/hash/길이·generator/oracle 자기SHA·canonical52→승인42 program 대조까지 실행한다. MemoryPath/ET facade는 모듈별 전용 loader에서만 제공하고 전역 pathlib/ET를 monkeypatch하지 않는다. workspace ROOT 초기화의 resolve/parents, model_pins의 rglob/is_file/stat/read, oracle.pmodel의 ET.parse도 동일 bundle만 읽는다. 알 수 없는 이름/경로 alias는 실제 FS fallback 없이 거절한다. 원형 realpath full verifier와 메모리 producer의 data/metrics가 실제 동일해야 하며 이 가능성은 L4 실측 전 수용이 아니다.

receipt는 닫힌 typed JSON이다: schema_version1/unit112/scope PURE_WORKSPACE_PREFLIGHT_NOT_NATIVE_AUTHORITY, input47의 SHA/길이, 실제 producer/source 알고리즘 pins, full_sampling=true/8192/6241, 원 workspace bytes SHA, 원 metrics, canonical result SHA를 결속한다. 시각/기한/실물권한/자기 SHA는 넣지 않는다. data는 이미 결속된 ref/workspace.json에서 매 사용 새 parse하고 metrics도 새 복사한다. 단순 PASS 문자열·caller가 공급한 임의 result는 권한이 아니다. expected SHA는 B의 실제 freeze/activation에서 독립 전달되며 SHA가 맞아도 scope/unit/closed fields/type/input/result 일치 전에는 사용하지 않는다.

D.bind는 값 bundle·경과시각·권위 사본을 저장하지 않고 C의 workspace_use contextmanager factory만 저장한다. D.verify_workspace는 **매 호출 반드시 with workspace_use() 안에서** fresh `(template_bundle47,receipt_bytes,expected_receipt_sha256,expected_model_path)` packet을 받고 closed type/path/key47/receipt/result를 검증해 새data/metrics를 만든다. 같은 module의 verify_simulation 내부 두 번째 호출도 예외가 아니다. packet을 만든 현재 owner는 D 사용과 context exit 검사까지 살아 있어야 하며, 값 return은 그 exit 뒤에만 호출자에게 전달된다. provider 실패/만료/다른thread/파일변경을 옛 result로 바꾸는 fallback은 없다. standalone pure producer/verify_receipt는 native 권한이 아니고 실제 B/C caller가 아래 owner를 제공한다.

D는 원 validate.py의 physical 함수를 유지한다. 허용된 의미 변경은 verify_workspace와 새로운 receipt/메모리 adapter API뿐이다. pmodel/verify_import/verify_simulation의 물리 체크·기준은 그대로이며 verify_simulation 내부의 verify_workspace만 같은 결속된 정적 결과를 사용한다. scene.py의 직접exec loader는 verify_import/pmodel만 쓰므로 원scene을 수정하거나 미bind import 자체를 거절하지 않는다. workspace 함수만 unbound 시 거절한다.

## B: 순수 preflight 생성과 실제 권위 결속

build_static_receipt(root)는 SDK/네트워크 없이 기존46 census SHA/길이·source20/template config·model/ref를 owner 안에서 읽고, 같은 template_bundle47로 D producer를 호출해 OUT/workspace-preflight.json만 배타 생성한다. 실제 파일 읽기 전 exact helper의 로컬 finite Fence600을 켜며 native45를 시작하지 않는다. 최종 L4가 필요한 context를 producer가 먼저 호출해 생기는 순환은 만들지 않는다. 코드/HOST 완료 뒤 receipt를 생성하고 마지막 sourcefreeze에47번째 dependency로 넣어 L4 대상에 포함한다. **consumer/context/run**은 receipt가 없거나 달라지면 언제나 거절하고 자동재생성/자동fallback/overwrite하지 않는다.

작성자 명시 revision-generation은 이 consumer 동작과 별개다. L4 R1 source 수리로 key47이 달라졌으면 nativeapproval/attempt0인 로컬 작성 단계에서만 원 source/receipt/freeze/review/raw를 before-L4-r2에 정확 보존하고 현재 receipt를 그 보존 위치로 이관한 뒤, 같은 누적1500초·기존2회 안의 작성자가 producer를 명시 호출해 현재 canonical 경로에 새 receipt를 배타 생성한다. old bytes/SHA/원 실패는 남긴다. producer는 기존 파일을 덮어쓰지 않으며 작업 경로를 OUT 안으로 확인한다. native 권한·시도·기한·회차 reset은 없다. 원 source key가 같으면 새 producer를 불필요하게 실행하지 않는다.

context는 원111의 finite owner/typed unit·sourcefreeze·plan·최종L2·최종L4·USD gate를 유지하되 모든 필수12AC와 B/C/D/통합 각PASS/미결0을 요구한다. L2 최종 파일은 실제 완료한 회차를 고정하고 L4 회차와 혼동하지 않는다. context는 deps46와 source7/harness1뿐 아니라 receipt SHA/typed input47·알고리즘/결과를 D consumer로 검증한다. receipt input의 source config는 원 template bytes이며 dependency/config/receipt 자기참조가 없다. nativeapproval는 원12필드 구조에서 unit112/scope112_SINGLE_REMOTE_45MIN_IMPORT_STOP_THEN42S와 exact 최종pins를 요구한다.

activate/verify_execution은 원 runtime20 budget/activation pin 사슬에 workspace_preflight_sha256를 추가해 독립 authority로 검증한다. Runtime.phase는 기존 actual helper Fence를 arm한 **뒤** TLS의 기존float끝 stack과 나란히 고유 opaque frame token을 push하고 finally 모두 원 parent로 복원한다. workspace_scope()는 현재 actual-armed frame의 Runtime identity/thread/token/end를 불변 scope로 캡처한다. require_workspace_scope(scope)는 파일 I/O 없이 같은Runtime·같은thread·원token이아직현재TLS ancestry에존재·그frame끝일치·현재시각<그끝을 확인한다. 같은float끝으로 임의 재진입해도 옛 token이 없으면 거절한다.

Runtime.workspace_authority(scope)는 이 원 scope를 먼저 순수 검사하고 현재부모/원global끝의actual childphase를 켠 뒤 context+verify_execution을 실제 실행해 unit/schema, receipt bytes/SHA, template config 원bytes, 원 lease end로 stamp한 expected active config bytes, template_bundle47의 승인 SHA/길이를 반환한다. receipt에서 기대 SHA를 거꾸로 읽지 않으며 반환된 메모리 값 자체를 owner로 취급하지 않는다. 모든 source20/model/ref 현재 검증은 cache 사용 전에도 유지한다.

Runtime.phase/bind/bind_config/verify/entry_code의 소유순서·thread/parent-min/global끝·source20·실제Centry 다섯째admission·export None·known facts·UNKNOWN 의미는 원111과 같다. 최초 stateless HELLO20(control 실패의 entry20/UNKNOWN 범위 포함), canonical float equality, subsequent known end 전Bsource/claim읽기0, 정확helper+단일zlibbundle/실제완성argv8000미만도 유지한다. 고정nonce 한 사례만으로 한도를 주장하지 않고 frozen pins+실제UUID/해시 entropy를 관측한다.

## C: 실제 caller와 config projection

C의 _bind_workspace(ctx,module)는 prepare/proof/consume의 **이미 actual-armed인 부모 frame**에서 workspace_scope()를 캡처한다. 새bind전용phase를 곧 닫아 token을 잃는 구조로 만들지 않는다. 검증된 원run/job SHA/typed identity/input inventory pins/model lexical path를 메모리 불변값으로 캡처하고 실제 D.bind_workspace에 `_workspace_use` contextmanager factory를 전달한다. 다른 alias·누락 API/인자·source21/old111 authority는 거절한다.

_workspace_use는 **매 D 호출** 처음에 require_workspace_scope(scope)를 순수 검사하고 원parent/global의 min인 rt.phase를 실제 arm한다. 그 아래 actual workspace_authority(scope), 캡처한 원run의 현재 job bytes SHA/identity와 **전체 현재 input 이름/bytes/pins**를 새로 읽고 검증한다. snapshot/consume/verify_smoke_proof를 재귀호출하지 않고 raw input 검증만 수행한다. 현재 source20/config가 승인된 active bytes와 같음을 확인한 뒤 config만 authority의 원 template bytes로 바꿔 key47을 만든다. JSON 재직렬화는 없다. 다른46 bytes도 authority의 SHA/길이에 맞아야 하며 현재 workspace-preflight.json도 actual authority receipt bytes/SHA와 같아야 한다. 읽은 동일 bytes packet만 yield한다.

provider의 child owner는 D의 path/key/receipt 검사·fresh result 생성·return context exit 검사까지 열린다. yield 복귀 뒤에도 원scope와끝을 확인하고 나서 종료한다. 원bind parent가닫힌뒤다른phase/다른thread로호출하거나현재job/model/ref/receipt/source/authority가변하면새읽기·순수scope검사에서거절한다. bind때 material이 같았다는 이유로두번째use를통과시키지않는다. 물리게이트의 원proof 재검산은 별도 유지하고 static영수증을 쓰기 위해재귀하지않는다.

명시 bind 위치는 원 _prepare_body의 prepare_workspace, verify_smoke_proof의 smoke_verify, consume의 validator 세 callsite다. D.verify_simulation 내부의 static 호출도 같은 binding을 소비한다. 기존 SDK scene의 직접exec는 physical API를 그대로 사용하므로 수정하지 않는다. 필요 시 bare validate의 VerifiedSource.exec_module에도 같은 ctx로 명시bind하되 새 Runtime 생성은 하지 않는다. 실제C caller→Dconsumer와 생략 변이를 HOST에서 관측한다.

prepare는 모든 job에 workspace-preflight.json 한 개를 추가 입력으로 복사해 import48 input으로 시작한다. cfg.refs는 원11, source는20 그대로다. snapshot expected와 job/common_signature는 새 receipt 입력도 정확히 결속한다. 모든 import/smoke proof의 원 hash·process/physics 소비는 유지한다. 준비 완료가 launch 가능함을 뜻하지 않는 원111 사례를 보존하고, 준비/검산/실제child·회수 단계의 시간표를 원 host mono/wall 축에서 기록한다. headroom 조건은 원값으로 다시 확인하며 실패 시 실행0·사실 보존이다.

## 수용 기준 및 실제 독립 관측

| ID | 범위 | 필수 조건 |
|---|---|---|
| B1 | authority | unit112·12AC typedPASS·모든단위PASS·누락/oldunit/hardwaretrue/무승인실제run의원격전거절 |
| B2 | first/subsequent | HELLO/control scope/20차감·canonical float·완성argv8000·원끝전read/claim·helper20source 결속 유지 |
| B3 | capsule/receipt | 47deps/61entries·samebytes/배타·USD8negative·receipt SHA/47input/source20/결과변조 거절 |
| B4 | process/recovery | actualWinJob·owner-prefix/EOF/return·partial capture/UNKNOWN·원5operation/closedfetch 사슬 유지 |
| C1 | owner/API | 매use 원opaque phase/thread/end→actual childowner→현재rawinput·권위→D반환까지owner·C→actualB→actualD 세caller/생략거절 |
| C2 | config/clock | 원template bytes/active stamp equality·20source·±.25/±1/age120·admission5/4arg변이·물리/시간값 그대로 |
| C3 | lifecycle | 실제 child/clock facts·NTFS publication failure·UNKNOWN·truthful prelaunch headroom차단·원proof/recovery 그대로 |
| C4 | pipeline/physics | SDK 직접load/physical함수 유지·새 receipt job/common binding·import→stop→42 chain, 실제물리gates 캐시0 |
| D1 | producer | 원 realpath full와메모리 samebundle data/metrics 전건동등·실제FS read차단상태 full math완주·key/사용같은bytes |
| D2 | consumer | 매useprovider호출·missing/unbound/oldunit/key47各그룹/receipt결과·typed/alias/stamp변조거절·fresh result·원parent종료/다른thread·변경파일/권위거절 |
| I1 | integration/perf | exact B/C/D actualcallee·같은Dmodule첫외부/두번째internaluse·그사이변경/만료·같은end새phase변이·blockexpiry·full sampling/반복 proof비용 실측·임계무완화·sealedfetch연결 |
| I2 | preservation | 보호51/CAD22/공유원bytes/원111439native·모든실패/원장·budget/회차·공통편향·승인전SSH/SDK/CAN0 |

HOST는 자기 비관리자 process/OUT112 fixture만 사용하고 SDK/remote transport는 명시 seam으로 분리한다. writer suite와 다른 관측 기전으로 owner block/부모종료/원래2반례/새producer·provider를 비작성자가 검증한다. 같은Dmodule의두번째use직전/도중실제model/ref/receipt/job/source·authority변화, 원parent종료뒤같은end로새phase, 다른thread, provider현재read block·원끝경과를관측한다. 실제C→B→D consumer도달과오류·정상양성을함께핀하고마커문자열만세지않는다. 이전11147 HOST나7953보호파일을 새시험 수에 더하지 않는다.

112-MAJOR-01 class WORKSPACE_REUSE_OBSERVATION_OMITS_CURRENT_AUTHORITY_AND_INPUT_STATE는 R1 union1/open1, landing PRODUCT_B_C_D_INTERFACE_AND_BINDING_LIFETIME이고 R2가폐쇄를독립판정할대상이다. 다음 distinct continuous union2(수리생성매핑포함)는현재 B/C/D workspace-reuse interface+검증 source EXHAUSTED 충분임계로R1주/보조에사전박제했다. 같은반례/여러AC/중복렌즈는증가0이다. 현재 소진/도메인소진을선언하지않는다. 원111 두class각union1/open0/다음distinct2 충분sourceEXH, oldB/FS/raw/restoration/109/finite/heartbeat 및 원5cap이력을 reset하지 않는다.

모든 unit·통합 마지막 codePASS와 exact typed nativeapproval 이후에만 첫 remote 요청부터2700초를 한 번 소비한다. import1→정지1 통과→motion1(42초/5040step/421capture), 배치/회수 포함·자동retry0. native600/motion900/cleanup150/headroom1380/1680·gains64/16·cap·모델·program·물리/시간 gate는 그대로다. 미사용111 시간/승인/정지성공을 새112권위로 쓰지 않는다. 실제 회수 뒤 원process/provider/물리consumer를 로컬에서 다시 실행해 artifact seal과실제42초결과를 확인하고 첫/중간/마지막프레임을본다. 원격시간경과뒤 cleanup/read SSH를 추가하지 않는다.
