> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 113 실행 계획 — 형식별 결정 숫자 정책과 현재 입력 전건 검증

현재 사용자 지시 「좋아 일단 내일 사무실가면 테스트할거니깐 이제 시뮬관련 작업이나 계속 하자」를 직전에 제시한 [113 구체안](113-typed-decision-artifact-boundary-proposal.md)의 재개 지시로 기록한다. B2/C4 각1500초·D4 2400초, L2/L4 각각최대2회·각 비작성자2700초, 모두 코드PASS 뒤 조건부 새 첫 원격2700초를 적용한다. 실물 CAN/RS485·급전·flash·모터·설치/UAC/시각·네트워크 설정 변경은 없다. 게인64/16·cap·원모델/program·물리/시간 기준은 그대로다. 기존 same-family 비작성자 폴백의 명시 승인을 유지하고 공통편향을 기록한다. 기존 차단 bridge 재시도·수리·설치·새 외부 모델 비용은 없다.

이 문서는 새 L1이며 L2 PASS 전 운영 source0이다. 원112 L4R2 BLOCK9/3/숫자 class union2/open1·현재 D 숫자 검증/지원시험 SOURCE_EXHAUSTED/noR3와 모든 과거 원장은 읽기 전용이다. 원112 남은 작성 시간·미시작 원격45분을 이관하지 않는다. 비작성자가 이미 닫은 JSON instance와 reuse 수명 instance도 그대로 보존한다. 새 정책을 기존 소진 구현의 이름 변경으로 만들지 않는다.

## 1. 소유·시계·보호 자료

SRC=`src/simulation/typed_decision_preflight_113`, OUT=`outputs/typed-decision-preflight-113`다. 전체10파일/3그룹은 L→S2/S4/S4로 분할한다. D40분은 별도 정책과 시험까지4파일인 상향 예산을 launch 전에 명시한 것이다.

| 그룹 | 운영 소유 파일 | 구현·HOST·root 귀속 검증 누적 cap |
|---|---|---|
| B2 | bootstrap.py, test_bootstrap.py | 첫 운영 소스 쓰기부터1500초 |
| C4 | driver.py, config.json, test_driver.py, OUT execute.py | 첫 운영 소스 쓰기부터1500초 |
| D4 | validate.py, test_validate.py, decision_schema.py, test_decision_schema.py | 첫 운영 소스 쓰기부터2400초 |

작성자는 혼자 작업하지 않는다. 다른 소유 파일·기존 원본·공유 문서·Git/index를 고치거나 되돌리지 않는다. root가 통합과 공유 인계를 맡는다. 각 작성자는 첫 쓰기 UTC/mono, 자기 HOST, 실패, 수리까지 같은 누적 시계를 기록하고 root 재검증/실제 producer용180초 이상을 남긴다. 단위 완료 뒤 검토 대기는 분리하되 수리 재개 시 기존 누적을 이어 쓴다. 전체 coordination wall envelope도 별도로 남기며 작업 시계와 바꾸지 않는다. 예산을 모두 쓰면 미완료로 동결하고 늘리지 않는다.

보호 입력은 원108/109/110/111 source51+원112 source7/harness1=59, 현재 CAD22와112의 freeze/receipt/검토/결과/errata다. OUT/protected-baseline.json으로 현재 SHA/길이를 확인한다. 다른 CAD 작업은 원위치로 되돌리지 않는다. 원111 실제 import/정지 성공을113의 새 native 수용으로 쓰지 않는다. 정착15·velocity-only소진·PD/포화UNKNOWN·moving-root 독립교정NOT_DONE·물성가정·링보류·과거실패/회차/次임계는 유지한다.

## 2. 닫힌 파일 집합과 로컬 생성 순서

runtime21 = 원 immutable108 중 validate 제외15 + 새 bootstrap/driver/config/validate/decision_schema5 + exact A helper1이다. helper SHA는 `2ca8c90616026a103eb41da18c33f34b012bcd56439cb39af967ea9bf2f683b0`로 고정한다. `source_A`8과 `source_B`13의 합21이며 source_B에 decision_schema.py를 추가한다. 모든 actual source inventory/admission/proof/caller도21로 닫는다.

key48 = source21(template config 정확int0) + model16 + 원ref11이다. receipt와 import/smoke proof는 key 밖이다. 모델16은 JSON3/URDF1/STL11/README1이다. key48의 형식 전건 분류는 JSON8+URDF1+STL11=typed20, 나머지 실행 source/참고코드/README=opaque28이다. opaque는 숫자 데이터로 파싱하지 않고 동일 바이트 SHA/길이로 결속한다. 소스 주석 속 `nan` 같은 문자열을 숫자로 검색하지 않는다.

immutable deps46 = source10815+refs10811+model16+USD3+helper1이다. OUT/dependency-census-pre-receipt.json은112의46개 순서를 유지하고 helper target alias만 SRC/winjob.py로 바꾼 실제 SHA/길이 목록이다. 로컬에 alias가 없으면 원110 helper만 읽는 기존 예외를 유지한다. 운영 source0 연구 관측 스크립트·그림은 이10개/21개에 포함되지 않고 승인·검증기로 사용하지 않는다.

코드/HOST 완료 뒤 root가 실제 B→D producer를 로컬 finite Fence600 아래 명시 호출해 OUT/workspace-preflight.json을 배타 생성한다. source21/model16/ref11의 같은 immutable bytes 복사본으로 key와 전건 검산을 수행한다. 최종 L4/context가 receipt 생성보다 먼저 필요해지는 순환은 만들지 않는다. freeze는 source9+harness1, deps46+receipt1=47이다. metadata5(plan/최종L2/freeze/해당L4/nativeapproval)를 더해 capsule payload62+manifest1=63이다. import job은 key48+receipt1=49 input이며 후속 proof 입력은 별도로 원 규칙을 따른다. cfg.refs는 원11개 그대로다.

root freeze는 현재 값으로 새 객체를 만들어 source21/소스9/harness1/deps47·actual receipt SHA·실제 HOST 수·기록 시각의 사건을 교차 확인한다. 이전 freeze 객체를 통째로 복사해 요약을 물려받지 않는다. AUDIT-112-R2-01은 원문+errata로 보존한다.

consumer/context/run은 receipt 누락/변경 때 항상 거절하고 자동 재생성·overwrite·full-math fallback을 하지 않는다. L4R1 코드 수리로 입력 key가 바뀐 명시 로컬 author revision만, nativeapproval/attempt0에서 old source/receipt/freeze/review/raw를 before-L4-r2에 정확 보존한 후 active receipt를 이관하고 같은 누적 cap 안에서 새 producer를 배타 호출한다. 같은 key면 불필요하게 재생성하지 않는다.

## 3. 새 policy의 구현과 선언 데이터의 경계

`decision_schema.py`는 새로 작성하는 단일 형식 dispatch/수치 파싱/coverage 모듈이다. 112의 `_decision_json`·검사 helper·지원 시험 구현을 복사하지 않는다. 새 시험 파일도 이전 시험을 통째로 복사하지 않고 원 반례/유한 대조/관측 데이터를 입력으로 재구성한다.

JSON의 이미 닫힌 **필드 의미 데이터**는 내용 자산으로 보존한다. OUT/json-numeric-role-contract.json은 기존 선언의 제한된 AST 데이터 추출로 재표현한 L2용 IR이며, 이전 모듈/검증기를 실행하거나 후보 데이터 타입에서 기대 타입을 추론하지 않았다. provenance와SHA를 기록한다. 이 선언 자산의 L2 고정 후 구현은 그 IR을 policy source 안에 상수 데이터로 포함할 수 있다(추가 runtime 파일 없음). 이 데이터를 평가하는 파서/인터프리터·coverage·XML/STL dispatch와 시험은 새 구현이다. 연구 observed-JSON/URDF/STL-shapes는 관측자료일 뿐 schema/validator가 아니다.

policy에는 caller가 바꿀 수 없는 JSON_ROLES 선언과 이 L2 IR 파일의 SHA 상수를 둔다. L4가 선언과 IR의 정확 대응을 독립 비교한다. IR은 runtime의 외부 파일에서 읽지 않으며 policy source SHA가 실제 실행 선언을 결속한다.

### 3.1 JSON8: 필수 역할과 실제 leaf coverage의 두 방향 대조

역할 IR은 number(정확int/float·bool제외·유한), integer(정확int), boolean(정확bool), object(필수필드), array(비어있지 않음·지정길이), mapping(비어있지 않음·값 역할)이다. object에서 미선언 metadata는 문자열/null/그 컬렉션만 허용하고 그 안의 int/float/bool leaf는 거절한다. 필수 역할 자리에 문자열/null·다른 컬렉션/누락을 두면 거절한다. legitimate boolean을 숫자로 금지하지 않고 선언된 logical 역할에서 정확bool로 받는다.

새 policy는 선언된 필수 노드·카디널리티가 모두 도달했는지 확인하고, 실제 입력에서 만난 모든 numeric/logical leaf가 정확히 하나의 선언 역할에 속했는지 별도로 대조한다. 부모 object 하나를 검사했다는 이유로 하위 leaf를 검사된 것으로 세지 않는다. 후보 현재 타입을 보고 숫자/논리 역할을 만들지 않는다. JSON duplicate key, NaN/Infinity 상수, `1e999` float overflow는 거절한다. `1e-999`처럼 원 float 파서의 유한값으로 귀결되는 표기는 새 물리 범위 판단 없이 유한성만 판정한다.

cfg/program/workspace의 원 물리·시간·integer/bool 역할, model/provenance/submission의 bytes/count, asset-ledger의 mass/COM/inertia/triangle 및 printed, prefix-seal의 schema_version 등 IR의8개 문서를 전부 적용한다. 필수 cfg deadline은 producer/template에서 정확int0이며 active projection은 §5를 따른다.

### 3.2 URDF: 현재 모델의 명시 closed profile

URDF를 수정하지 않는다. policy는 UTF8 XML의 현재 프로젝트 subset을 검사한다. DOCTYPE/ENTITY 선언은 실제 XML 선언 경계에서 거절하고 외부 I/O를 하지 않는다. 주석의 단어를 수치/DTD로 오판하지 않는다. 미선언 element/attribute는 거절해 새 파싱 계층이 조용히 빠지지 않게 한다. 단순 tag 전체 허용이나 현재 값의 숫자처럼 보이는지에 따른 분류는 사용하지 않는다.

| 역할 경로 | 허용 속성 / numeric arity | 자식·필수 관계 |
|---|---|---|
| robot | name:text | link/joint만; 원 topology는 별도 원 검사 유지 |
| robot/link | name:text | frame-only link는 비어있을 수 있음; 물리 링크의 inertial/visual/collision 구조는 아래 기준 |
| link/inertial | 속성없음 | origin1/mass1/inertia1 |
| inertial/origin, visual/origin, collision/origin, joint/origin | xyz:number3, rpy:number3 둘 다필수 | 자식없음 |
| inertial/mass | value:number1 필수 | 자식없음 |
| inertial/inertia | ixx/iyy/izz/ixy/ixz/iyz:number1 전부필수 | 자식없음 |
| link/visual | 속성없음 | origin1/geometry1/material1 |
| visual/geometry | 속성없음 | mesh1 |
| visual/geometry/mesh | filename:text, scale:number3 필수 | 자식없음 |
| visual/material | name:text 필수 | color0또는1(이름참조 material 허용) |
| visual/material/color | rgba:number4 필수 | 자식없음 |
| link/collision | 속성없음 | origin1/geometry1 |
| collision/geometry | 속성없음 | box1 |
| collision/geometry/box | size:number3 필수 | 자식없음 |
| robot/joint | name:text, type:text 필수 | parent1/child1/origin1; revolute/prismatic에 axis1/limit1/dynamics1; fixed는 그 numeric 자식 없음; mimic0또는1 |
| joint/parent, joint/child | link:text 필수 | 자식없음 |
| joint/axis | xyz:number3 필수 | 자식없음 |
| joint/limit | lower/upper/effort/velocity:number1 전부필수 | 자식없음 |
| joint/dynamics | damping/friction:number1 전부필수 | 자식없음 |
| joint/mimic | joint:text, multiplier/offset:number1 전부필수 | 자식없음 |

이것은 일반 URDF의 모든 선택적 표현을 구현한다고 주장하는 schema가 아니라 현재 제출 모델의 명시 subset이다. 현재 모델은12 link/11물리 link/11 joint/9 movable이며 표의24개 전체 경로를 가진다. inertial/visual/collision이 있는 link는 각1개이며 partial 물리 구조를 허용하지 않는다. material의 선택 color 외에, 기존 노드에서 필수 numeric attr를 빼고 암묵적 기본값으로 바꾸지 않는다. 허용 joint type은 현재 revolute/prismatic/fixed다. 이름/parent-child/mesh 경로/양의 질량·관성 물리조건/limit관계·FK 검사는 기존 full/물리 소비자의 원 역할을 유지하며 numeric policy가 대신하지 않는다.

필수 numeric 역할은 후보가 빈 link를 만들었다는 이유로 사라지지 않는다. 이 profile의 link 이름 집합은 Base/Link1~Link6/KG1/KG1_A/KG1_B/KG1_R/tool0의 정확12개이고, tool0만 자식이 없는 frame-only다. 나머지11은 위 inertial/visual/collision을 모두 가져야 한다. joint 이름/종류는 J1~J6=revolute, KG1_mount/tool0_mount=fixed, KG1_slide_A/KG1_slide_B=prismatic, KG1_pinion=revolute의 정확11개다. KG1_slide_B와KG1_pinion은 mimic1개가 필수이고 다른 joint에는 mimic을 두지 않는다. parent-child의 실제 공간·기구 관계는 원 소비자가 따로 검증한다. 이 명시 profile은 현재값을 보고 학습하지 않는다.

모든 number token은 부호·소수·과학표기의 명시 decimal grammar 전체 일치 뒤 float 변환·isfinite 검사한다. bool 단어/underscore/빈 token·NaN/Inf·overflow·벡터/행렬 arity 불일치를 거절한다. 같은 유한값의 다른 표기와0/음수 off-diagonal도 숫자 유한성 단계에서는 허용한다. positivity/물성 수정·clamp·자동 보정은 없다. 실제 파서가 읽는 mass·inertia6성분·origin·axis·limit·dynamics·mimic·mesh scale·box size·RGBA를 모두 coverage에 센다.

### 3.3 STL11: binary/ASCII 파싱 계층

binary는84+50*N 길이와 header count N을 전건 대조하고 triangle마다 normal3+vertex9 float32를 검사한다. header80 bytes는 opaque다. 16bit attribute는 format scalar로 읽고 범위를 따르며 임의 숫자 문자열로 해석하지 않는다. binary header가 `solid`로 시작해도 먼저 정확 binary 길이로 판별한다. truncated/surplus/count 불일치와 비유한 component를 거절한다.

ASCII 지원은 closed solid/facet normal3/outer loop/vertex3×3/endloop/endfacet/endsolid grammar를 전건 소비하고 남는 token/좌표 누락/비유한·overflow를 거절한다. 이름 text는 opaque다. binary 길이가 아니라고 오류를 무조건 ASCII로 통과시키지 않는다. 정확한 ASCII grammar도 만족해야 한다. 정상 모델11은 모두 binary이므로 ASCII 양성은 policy 단위 대조이며 원 full/물리 소비자가 ASCII를 수용한다고 확대하지 않는다. mesh 재생성·수정은 없다.

## 4. policy와 D API / receipt exact schema

policy public API는 `validate_decision_inputs(bundle48)->fresh_contract`다. 입력은 닫힌48개 상대 이름→정확bytes이며 private immutable copy를 사용한다. policy는 실행된 자신의 `__source_bytes__`와 bundle의 source/decision_schema.py가 같은지 확인한다. 입력 type/이름/빈 raw·추가·삭제·alias를 거절한다. 파일별 parser 배정은 현재 값이 아니라 고정 filename dispatch다. policy 호출은 실제48개 전부를 typed20/opaque28로 분류해야 한다.

numeric_contract는 closed7키다:

```
schema_version: exact int1
unit: str113
scope: str TYPED_DECISION_INPUTS_NOT_NATIVE_AUTHORITY
policy_sha256: SHA256(actual executed policy raw)
inputs_sha256: SHA256(canonical input48 {name:{sha256,bytes}}))
files: mapping48[name] -> {kind, numeric_components:nonnegative exactint, logical_values:nonnegative exactint}
totals: {numeric_components, logical_values, typed_files:20, opaque_files:28}  # exactint
```

kind는 JSON/URDF/STL_BINARY/STL_ASCII/OPAQUE의 고정 열거값이다. JSON 숫자 개수는 int+float, 논리값은 bool을 별도로 센다. URDF는 실제 파싱한 선언 속성의 scalar component다. binary STL은 header count1+triangle마다12float+attribute uint16이므로1+13*N, ASCII는12*N이다. opaque는 두 개수 모두0이다. totals는 files의 실제 합이다. 외부 caller가 제공한 contract로 실제 검증을 생략하지 않는다.

D public API는 다음으로 고정한다:

```
bind_decision_schema(policy_raw:bytes) -> None
produce_workspace_receipt(template_bundle48) -> canonical bytes
verify_workspace_receipt(template_bundle48,receipt_raw,independent_expected_sha) -> (fresh_data,fresh_metrics)
bind_workspace(workspace_use_contextmanager_factory) -> None
verify_workspace(expected_model_path) -> (fresh_data,fresh_metrics)
```

**bind_decision_schema는 bytes만 고정하고 code 실행·I/O를 하지 않는다.** 다른 raw로 재binding하면 거절한다. 같은 raw를 다시 제시하도록 허용해도 권위 갱신으로 쓰지 않는다. D의 매 producer/consumer 사용에서 같은 bundle의 private 복사본·policy raw 일치·actual D source 자기 pin을 확인한 후 private module로 그 raw를 새로 compile/exec해 실제 API를 호출한다. caller object의 callable/coverage를 받거나 cache하지 않는다. sys.modules/global Path/ET monkeypatch·real FS fallback은 없다.

B는 actual freeze source21 전건 확인 뒤 같은 raw로 D를 load/bind한다. 명시 로컬 producer는 작성한 source의 같은 raw를 finite owner 안에서 쓴다. C는 captured input의 policy raw를 bind하지만 이때 실행하지 않으며, §5 provider가 actual current B authority와 전 입력을 새로 검증한 with 안에서만 D가 policy를 실행한다. binding을 먼저 했다는 이유로 미검증 code/숫자를 사용하지 않는다.

receipt는 closed12키다:
schema_version/unit/scope/inputs/algorithms/full_sampling/sample_count/path_state_count/workspace_sha256/metrics/result_sha256/numeric_contract。
unit113, scope `PURE_WORKSPACE_PREFLIGHT_NOT_NATIVE_AUTHORITY`, full_sampling=true, sample_count8192/path_state_count6241이다. algorithms는 actual validate.py/decision_schema.py와 fixed workspace.py/sampling-oracle.py의4pin이다. inputs는 exact48 SHA/bytes다. result_sha는 canonical `{workspace_sha256,metrics,numeric_contract}`의 hash다. 시각·native/실물 권한·자기SHA 순환은 없다.

producer는 samebytes 전건 policy+원 full=True8192/6241·model16 inventory/hash/길이·oracle/generator 자기SHA·원52→42program을 실행한다. consumer는 독립 expected SHA, closed receipt/type/unit/scope, current input/algo/result 및 **fresh actual policy contract**의 일치를 확인하고 full math는 재실행하지 않는다. data는 결속한 workspace bytes를 매번 새로 parse하고 metrics도 fresh copy다. policy/receipt 실패에 fallback은 없다. 원45 physical 함수는 verify_workspace 외에 원AST와 같고 physical import API는 workspace/policy unbound에서도 원래대로 사용한다. policy가 모델의 잘못된 값을 clamp해 통과시키지 않는다.

## 5. B→C→D 현재 권위와 수명

원112의 actual Runtime.phase token/thread/original end, pure scope check, parent/global min, first stateless HELLO20과 차감, canonical float exact equality, subsequent known-end 전read0, helper pin, single zlib/actual 완성argv8000미만, callee 다섯째admission/export None, 원 process/EOF/known-facts/UNKNOWN을 보존한다. runtime inventory만21로 갱신하며 남아있는 old20/old112 계약은 거절한다. native600/motion900/cleanup150/headroom1380/1680/총2700을 완화하지 않는다.

`Runtime.workspace_authority(scope)`는 schema_version1/unit113/receipt_raw/receipt_sha256/template_config_raw/active_config_raw/decision_inputs mapping48의 원7키로 반환한다. actual current context+execution을 owner 안에서 검증한다. budget/execution/activation/fetch도 current receipt와 source21을 결속한다.

C의 세 caller prepare_workspace/smoke_verify/consume은 already armed original parent에서 scope를 capture한다. 같은 D module의 verify_simulation 내부 두 번째 호출도 매번 provider를 사용한다. provider는 pure 원token/thread/end 검사→actual min-childphase→actual B workspace_authority→원job bytes/hash/identity와 전체 현재input 이름/bytes/pins freshread→current source21/policy/receipt와 독립 authority 대조 순서다. active config의 exactstamp 일치 확인 뒤 config만 B의 원template bytes로 바꾸고 나머지47개 raw를 바꾸지 않은 tuple4(bundle48,receipt_raw,expectedSHA,expected_model_path)를 yield한다. job/proof 재귀는 없다. policy 실행 전에 이 독립 확인을 끝낸다.

provider child owner는 D policy/receipt/fresh result/with exit까지 유지하며 postyield에서도 원scope/end를 검사한다. 부모 종료 뒤 같은end의 새phase·다른thread·다른RT·current job/source/policy/ref/model/receipt/authority 변경을 거절하고 옛bundle/contract/결과로 복구하지 않는다. source load는 samebytes `__source_bytes__`를 설정하고 policy는 bundle raw와 actual 실행raw를 일치 검증한다. native 물리/proof 검증은 cache하지 않는다.

## 6. 12필수 AC와 독립 검증

| ID | 필수 수용 조건 |
|---|---|
| B1 | plan/finalL2/freeze·12AC/각unitPASS·nativeapproval의 typed unit/pin이 없으면 actual root에서 첫remote 전 거절 |
| B2 | first HELLO20/원float/known-end 전read0·actual source21/helper·완성argv8000을 원exact 반례와 새nonce entropy로 검증 |
| B3 | deps47/capsule63/key48/receipt12·source9+harness1/census/새policy 결속·USD gate/배타생성·변조 거절 |
| B4 | 원 token/thread/end/parent-min·process/EOF/return/known facts/UNKNOWN과 code-freeze 원이력 유지 |
| C1 | 세caller→actualB→D/policy 도달, 같은D의 두 번째 사용/원scope/전체current input/독립policy pin을 매번 검증 |
| C2 | template→exactactive stamp·source21/fifth admission·원clock 및 물리/시간값 유지 |
| C3 | current policy/model/ref/job/receipt/authority 변경·부모종료/다른thread/owner 내block에서 옛결과 없이 거절 |
| C4 | import→정지render_smoke 성공→42초motion의 원순서·headroom/실패/회수/정지 보존 |
| D1 | 새JSON 양방향coverage+URDF 전numeric속성+binary/ASCII STL 전숫자를 actualpolicy/producer/consumer의 양성/반례로 검증해 원JSON3·ET03을 폐쇄 |
| D2 | actual full reference와 memory producer의 data/metrics 일치·real FS block 아래full·consumer math0/새policy actual호출/receipt12/actualsource·원physical45AST 유지 |
| I1 | 실제Bproducer→D 및 C→B→D의 source21/input49·새policy/두 번째use·원ET 반례producer와 정합 재결속consumer를 비작성자가 독립 재현 |
| I2 | exactfreeze 전요약·원source59/CAD22·과거실패/class/임계·cap/회차·native 전actual부정경계와 최종unit 수용을 확인 |

HOST synthetic review/lease/receipt seams는 `SYNTHETIC_HOST_FIXTURE_NOT_REVIEW_OR_NATIVE_AUTHORITY`로 명시하며 actualproducer/독립 numeric guard와 섞지 않는다. 타입guard 시험에서 input hash 불일치만 성공 근거로 세지 않는다. 원3JSON변형과 requiredURDFixx inf/nan/overflow, 다른5tensor성분·mass/origin/axis/limit/dynamics/mimic/mesh scale/box/RGBA, JSON 각역할/metadata 내미지numeric/logical, binary 모든component/attribute/count/길이, ASCII grammar/overflow/오판별·comment문자열 정상대조를 포함한다. 파싱계층이나 값 정규화로 반례를 지우지 않는다.

같은D 두 번째 호출에서 policy현재입력/authority 변경·부모종료/같은end 재entry/다른thread를 확인하고, policy미binding/raw불일치/호출생략 변형과 양성을 실경로에서 관측한다. producer는 fixedworkspace/oracle의 원full math를 실행하며 새policy가 먼저 거절하는 차이만 허용한다. 비작성자는 writer와 다른 관측 기전을 쓰고 source/실행observer/같은raw입력/stdout·stderr/반례·양성을 selectedmanifest로 보존한다. 자기verdict는 허용하지 않는다.

## 7. class 원장·마지막 회차와 조건부 native

numeric class의 과거112 union2/open1·현재112 숫자sourceEXH를 유지한다. 113은 새 전체format policy/coverage와 bind계약으로 원ET 결함을 재상정하고 L2/L4 비작성자가 그 수리와 새설계 폐쇄를 판단한다. **다음 DISTINCT continuous union3을 새policy/결정입력 검증·지원시험의 current-sourceEXH 충분 임계로 첫L2 비작성자에게 심사·사전 확정을 요청한다.** 같은반례/여러AC/렌즈중복의 증가는0이며 수리생성인과는 직접 관측 없이 주장하지 않는다. 원reuse class union1/open0/다음distinct2,111 command/float 각1/0/다음2,oldB/FS/raw/restoration/109/finite/heartbeat 등의 판정을 reset하지 않는다. 새class도 해당회차 안에서 landing과 다음임계를 명시한다.

main/lens는 L2/L4 각각최대2회·회차당2700초를 재고12AC와 B/C/D/integration 개별disposition·전체unresolved를 typedJSON으로 반환한다. 최종main은 보조최종SHA를 pin하고 상호순환을 만들지 않는다. BLOCK수리는 원작성자만 하고 reviewer는 제품/계획/권한/shared/index를 고치지 않는다. 마지막 뒤R3는 없다. sourceEXH/미완료는 원raw/잔여예산/미결을 보수적으로 보고하고 native0으로 종결한다.

모든 마지막codePASS 및 actualroot missing-nativeapproval 거절 확인 후에만, 이번 재개 지시와 exact최종plan/freeze/L4를 unit113의 closed12-field nativeapproval에 결속한다. scope는 `113_SINGLE_REMOTE_45MIN_IMPORT_STOP_THEN42S`, duration2700, native_limits import1/render_smoke1/motion1, clock_mutation=false/hardware_approved=false, native_budget_starts_after_review=true다. 추가 일반확인으로 멈추지 않는다. 첫remote 요구부터 새2700초를 단일소비하고 배치/회수 포함retry0이다. localdaemon/peer를 read-only 확인하고 접속실패도 그시도로 기록한다. sandbox가transport pipe/network를 제한하면 기승인 범위의 일반사용자 transport를 적절한 tool권한으로 첫시도부터 실행하며 실패 뒤 같은시도를 재실행하지 않는다.

import1→정지1 수용→42초/5040step/5041obs/421frame motion1 순서다. headroom/원clock/stop/physics 실패면 후속NOT_RUN이다. global기한 뒤 추가SSH cleanup/read를 하지 않는다. 회수한 닫힌자료의 process/provider/원physics consumer를 localfiniteaudit로 재실행하고 remoteRuntime/cross-hostmono비교를 만들지 않는다. clip은 실제frame/duration으로 만들고 first/mid/last를 본다. CLI0만으로 nativeaccepted로 쓰지 않는다. 자료와codePASS, 완주와physicsPASS, 실물수용을 구분한다.

## 8. L2 고정 입력

- OUT/json-numeric-role-contract.json SHA256 698307f7ece43d64e9d0d044553d6b5bbcf3237545f1630c7577d8975faaf4a8.
- OUT/dependency-census-pre-receipt.json SHA256 37cdcef6f740ce9aed702f60e869dc89236a8f06092622734930ea66a1b3d98e.
- OUT/protected-baseline.json SHA256 b5b39ee5d20766bd6fb0f68f37788008f5dd44fc1a4670cc688b1127bf59af63.
- immutable46 canonical records SHA256 14a039face1e93b7ca29bfb0d41509b94dfbf34933c51aa277fde04e70680ac1.
- normal 관측은 observed-JSON/URDF/STL-shapes.json이며 schema가 아니다. 기존 URDF read-only CAD snapshot은11parts/unmeshed0으로 시각 확인했으며 새 joint sweep·Isaac·물리 수용은 주장하지 않는다. CAD CLI 미가용 상태를 변경하지 않고 제공된 CAD 도구만 사용했다.
