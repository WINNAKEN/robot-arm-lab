> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 111 — 최초 읽기 전 수명 소유와 고정 lease 전달

2026-11-04 KST. 사용자 「작업 게속이어가」를 직전111 구체안·B/C 각25분/검토45분·각L2/L4최대2의 새 범위 진행 승인으로 기록한다. 앞선110 B 추가1회 질문을 대체한다. 원109·110의 닫힌 회차/실패/소진/동결은 수정하지 않는다. [111 원 제안](111-lifetime-redesign-proposal.md), [110 최종 R2](../../outputs/single-host-controller-110/review/AC-L4-r2.json)가 입력이다. 동일계열 비작성자 폴백의 기존 명시 승인을 유지하며 공통편향을 기록한다. 외부 bridge의 과거 lint 차단은 재실행/수리/설치하지 않는다.

## 소유·등급·새 예산

mutable는 정확6개/2그룹(M6)이다. B는 worker가 `src/simulation/known_lifetime_controller_111/bootstrap.py`, `test_bootstrap.py`(S2/25분), C는 root 책임 아래 별도 Codex worker가 같은 폴더 `driver.py`, `config.json`, `test_driver.py` 및 `outputs/known-lifetime-controller-111/execute.py`(S4/25분)를 작성한다. 각 첫 source write부터 구현·HOST 완료까지 누적1500초이며 L4 사이 휴지기간을 분리한다. B/C/통합 각각 L2 최대2·L4 최대2, 검토 각2700초다. A는 변경하지 않는 내용 자산으로서 새 구현/회차가 아니다. L2 전 소스0이며 실제 B/C와 연결 계약 전체를 주/보조 비작성자가 병렬 검토한다. L4도 단위별/통합별 verdict·union/미해결을 명시한다. BLOCK 수리는 작성자만 하며 마지막 회차 뒤 자동 R3가 없다.

로컬 코드/시험/검토는 원격45분을 시작하지 않는다. 모든 단위·통합 코드 L4 PASS와 typed native 권한 이후만 원격을 연다. 기존 조건부 새45분은 첫 요청부터2700초로 계속 미사용이며 한 번만 소비하고 업로드·SDK·회수를 포함한다. 원 게인64/16·cap·097 program·모델·정지/42초·물리/시간 gate는 무완화, setter/UAC/실물CAN/급전/flash/모터/설치/물리보정0이다.

## 의무·연속 원장

1. 원109 actual5초 cap은 새 폐쇄에서 OS 시각 변경 경로0으로 대체한다. pending launch는 exact110A의 생성순간 Job/고정 handle 경계를 실제 새 caller가 사용한다. 원109 과거 OPEN과 source 소진은 소급 폐쇄하지 않는다.
2. 110 B `REMOTE_BOOTSTRAP_LIFECYCLE_UNOWNED` union1/open1: 후속 원격 요청은 최초 claim 읽기 전 이미 확정한 원격 end를 받는다. initial=min(now+20,expected_end)이며 동일 claim SHA/nonce/start/end를 검증한다.
3. 110 C `LOCAL_FILESYSTEM_STAGE_LIFETIME_UNOWNED` union2/open1·현재 owner-placement/proof source EXHAUSTED: 새 설계는 metadata에서 end를 구해 owner를 늦게 켜는 소스를 폐기한다. 부모가 검증한 lease scalar와 메모리 helper만으로 phase owner를 켜고 난 뒤 metadata를 재검증한다. 원 copy/extract 폐쇄·repair-added prefix 반례를 함께 승계한다. 같은 class의 계보는 연속이며 이름/세션으로 초기화하지 않는다. 기존 source 소진과 대안 소스의 새 판정은 구별한다.
4. 110 C의 명시 NOT_CREATED/위임후 UNKNOWN, known clock process 메모리 envelope 및 fifth admission 폐쇄 내용도 그대로 회귀한다. 원 finite-stage union2/next3, raw/restoration/109 source 소진3 등 별도 원장은 변경하지 않는다. 매 검토는 class 재발/재귀/착지/소진 범위·남은 충분 임계를 명시한다.

## 실제 의존성과 배치

root=`C:/isaacsim_remote/robot-arm-lab/111/controller/<nonce>`; worker=`C:/isaacsim_remote/robot-arm-lab/111/worker/runs/<uuid>`. 원108 source16은 원 경로 `src/simulation/clock_ready_resume_108/` 아래 정확 bytes로 복사한다. 모델16·cfg refs11·USD 검증 자산3(원108freeze/usd-check stdout/activate-budget.py)을 같은 상대경로로 승계한다. 마지막 파일의 순수 verify_usd만 호출하고 oldcontext/activate/nativeapproval는 호출하지 않는다. 원 evidenceSHA·scene/root_binding 동일성·typed8negative를 새 template/activation/offline검증에서 모두 적용한다.

새 runtime은 **20 source**다: 원 immutable16 + 새 driver/config/bootstrap + exact110 winjob helper. bootstrap이 SDK entry의 수명을 처음부터 재구성하는 실제 소비 코드이므로 원 제안의19에 포함을 명시해20으로 바로잡는다. mutable 수6은 변하지 않는다. A helper SHA `2ca8c90616026a103eb41da18c33f34b012bcd56439cb39af967ea9bf2f683b0`는 읽기 전용이고 복사된 bytes도 같은 SHA다. tests/execute는 capsule검증 입력이지만 SDK runtime20과 구별한다. 7953전체·옛 run/승인/예산/인증서는 복사하지 않는다.

capsule ZIP은 정확 allowlist/상대경로/중복·link·기존목적지·추가파일 거절, 읽은 동일 bytes SHA→사용·배타생성을 지킨다. root/src/outputs 상대구조를 유지하되 activeconfig의 deadline만 정확 int0 token1개에서 원lease wall끝으로 변경한다. template freeze6/dependency/metadata와 별도 execution freeze/runtimebudget/activation은 결속하며 template 승인이나 옛 PASS를 activation으로 승격하지 않는다. 원 SDK 고정 prefix/설치는 기존것을 검사만 하고 재설치하지 않는다.

## B/C 명시 API와 데이터 흐름

B `load_helper(root)`는 원격시도 전 로컬 preflight에서 정확 SHA를 확인해 메모리에 로드한다. 첫 원격 이후 helper를 파일에서 다시 읽어 owner를 준비하지 않는다. 원격은 inline으로 전달한 압축 helper 고정 bytes의 decode/import/SHA만 owner 전에 허용한다. 이후 module/file/stdout/managed I/O는 이미 owner 안이다.

B `context(root,round_number,*,helper,owner_end,require_native=False)`는 typed finite scalar owner_end로 helper.Fence를 실제 armed한 뒤 파일을 읽는다. preflight owner는 로컬 준비의 별도 유한 끝이며 native2700 시작/권한이 아니다. context는 unit111/plan/L2/sourcefreeze6/deps/requiredAC 전건MET의 typed PASS L4(B/C/통합)/동일 round·비작성자 판정/물리false/USD gate를 검증한다. require_native이면 별도 native-approval의 unit111/user quote/plan/freeze/finalreview/2700/목적별각1/clock_mutation=false/hardware=false를 검증한다. L2 PASS만으로 native 권한을 만들지 않는다.

B Runtime은 root/helper/검증한 lease를 보유한다. lease는 닫힌 typed 값(unit111,nonce,원 remote/client start/end,claimSHA,plan/freeze/review/nativeapproval pins,고정20차감)이며 권한을 대신하지 않는다. Runtime.phase(limit=None)는 순수 monotonic 산술만으로 Fence(min(원global끝,현재부모phase끝,phase진입mono+limit))를 만들어 실제 armed하며 with 값은 절대 mono끝 float다. Runtime.bind_config(dict)는 dict subclass에 runtime 속성을 붙여 JSON key/bytes/물리값은 추가하지 않는다. Runtime.bind(ctx)는 ctx.runtime 및 ctx.cfg.runtime을 붙인다. C는 runtime의 typed 값·하드웨어false를 순수 확인한 뒤 phase를 켜고 B Runtime.verify()의 실제 authority/claim/execution 검증을 owner 안에서 한다. verify는 current-thread phase가 armed되지 않으면 파일읽기0으로 거절하고 검증한 budget dict를 반환한다. 임의 lease/공개 CLI 입력만으로 runtime 실행 권한이 생기지 않는다.

C `public(role,run_dir='',purpose='',*,runtime)`와 `entry(run,job_hash,driver_sha,role,admission=None,*,runtime)`는 runtime 없는 호출을 SDK/file 전에 거절한다. pure runtime check→global owner→모든 snapshot/source/config/hash/경로/진단/출력 순서다. 새 snapshot/prepare/load가 만드는 cfg/ctx에는 runtime을 명시 승계한다. 기존 exactdict 검사는 plain dict에 먼저 적용하고 bind하거나 dict projection으로 재검증하며 중첩 물리 type 조건은 그대로다. master budget/activation/model/ref의 root는 실제 runtime.root를 쓰고 SDK snapshot driver의 __file__.parents3를 capsule root로 오해하지 않는다. snapshot의 source20 지문은 B가 검증해 돌려준 budget.execution_source(파일명→active SHA20개)와 정확히 같아야 한다. 기존 순수 물리/proof/acceptance 함수들은 metadata unit/name 및 SOURCE20 조합 외 알고리즘을 바꾸지 않는다. 원108 자체를 monkeypatch하지 않고 새111 소스의 호출 배선을 바꾼다.

C `session_now(cfg)`는 cfg.runtime의 owner 아래 Runtime.verify가 검증한 budget으로 원 effective_clock ±.25를 검증한다. C가 budget/activation을 중복 읽어 다른 사본을 권한으로 쓰지 않는다. budget 필드는 unit111/duration_s2700/remote started_unix·started_monotonic/deadline_unix/hardware_approvedFalse/plan_sha256/execution_source20이다. C `_job_helper(ctx/runtime)`는 메모리 helper를 돌려줄 뿐 파일을 읽지 않는다. C clock/localprocess/launch/recover/verify/publish는 runtime을 명시 전달받거나 ctx/cfg.runtime에서 얻어 순수 phase끝으로 owner를 먼저 켠다. phase 밖의 `_operation_end` metadata 읽기는 없다. 회수600은 session_now/목적지검사 전에 시작하고, export/각copy300과upload/extract각120/OSclock20은 각 managed작업 첫 읽기·해시·쓰기 전부터 진단/출력 완료까지 소유한다. global끝보다 길게 만들지 않는다. 실제 helper.run work/cleanup은 같은 끝에서2초를 예약하며 capture EOF/종결 UNKNOWN을 성공으로 바꾸지 않는다.

C literal은 B Runtime.entry_code(ctx,role)를 사용한다. 이 코드의 고정 inline helper가 원 scalar 끝의 owner를 먼저 켜고 bootstrap bytes를 읽어 원pin을 확인/로드한다. B `_child_entry`는 같은 원lease/claim·activation·입력/source/job을 확인한 뒤 C entry의 **다섯째 admission**을 native/supervise에 실제 전달하고 export에는None, runtime은별도kw로 전달한다. bootstrap은 source20/snapshot 안에 포함한다. SDK entry 늦은 도착·원끝 경과는 첫 managed읽기/SDK 전에 거절한다. literal/relay의 실제 완성 명령 길이도8000미만을 HOST에서 측정해 초과시거절한다.

## 최초 고정 HELLO와 후속 managed relay

R1 111-L2-R1-F1을 수용한다. 첫 고정 제어 actor와 소스/파일/claim/SDK를 소비하는 application actor를 구별한다. **첫 요청에는 bootstrap/source/ZIP/manifest bytes를 보내지 않으며, 첫 actor는 어떤 파일·claim·application payload도 읽거나 쓰지 않는다.** 고정 inline helper+고정 HELLO 코드만 전달하고 decode/import/SHA 뒤 remote entry+20 owner를 실제 armed한다. 허용 I/O는 닫힌 READY/LIVE/GRANT 제어 메시지의 stdin/stdout뿐이다. 첫 LIVE 대신 B소스를 미리 쓰는 복원은 프로토콜 실패여야 한다.

로컬 prepare_capsule은 nativecontext의 exact allowlist bytes/해시로 ZIP과 manifest를 첫 원격 전에 만든다. coordinator run은 helper를 이미 메모리에 두고 local mono t0를 고정해2700 fullFence를 armed한 뒤 remote-attempt를 배타 소비하고 첫 SSH를 요청한다. 모든 SSH는 exactA helper.run의 Job 자식이다. 첫 SSH는 work18+cleanup2=총20이며 input_sender는 실제 READY를 client t0+18 전에 검증한 뒤 LIVE 한 줄만 쓴다. prewrittenLIVE파일·미리 보낸 bootstrap 데이터가 없다. stdout/실제return/rawEOF/정리도 같은20안이다.

첫 inline actor는 파일/Kit 없이 OS wall/mono/uptime/sitefalse/nonce의 READY를 보내고 bounded LIVE 한 줄을 읽는다. LIVE는 닫힌 키/typed finite 값/nonce/plan·templatefreeze·review·nativeapproval·bootstrap/helper 핀과 client원start/end를 고정 request와 대조한다. LIVE가 없거나 틀리면 grant 없이20에 종료한다. 이 actor는 LIVE 뒤에도 application 파일이나 claim을 만들지 않고, READY 시각 R에서 remote start=R−20/end=start+2700을 계산한 **순수 GRANT 제어 값**만 내보내고 종료한다. remote source module을 stdin에서 먼저 로드하는 R1 순서는 제거한다.

client는 두 protocol rows/nonce/모든핀·고정20차감·clientstart/end를 검증하고 first SSH actualexit0/policy0/terminal/active0/양rawEOF/전체E<=20을 확인한 뒤에만 grant를 receipt로 수용하고 다음 요청을 연다. 첫 교환이 실패/불명/late면 localattempt와예산은소비된실패,source전송·claim·controller·SDK·다음명령0이다. 새2700이나재시도가없다. firstremoteentry가client끝뒤에늦게생겨도remote에서읽을Bsource/application payload가애초에전송되지않으며stateless제어actor만20수명을갖는다. 이실패한 제어 actor의종료시각을client t0+2700안이라고주장하거나SSHdaemon/defaultshell의종료를소유했다고주장하지않는다. 별도실제관측/불명은UNKNOWN이다. 이는허용된SDK/파일/application업로드의2700끝을늘리는예외가아니다. 모든client작업은t0+2700,모든accepted application작업은아래원remote끝안이다.

READY가client18안에관측되고wholefirst20이종결했으므로물리이벤트R<=client t0+20이고remote end=R+2680<=client t0+2700이다. 서로다른PCmono숫자나walloffset을직접비교하지않는다. 고정20을전부차감하며실측E만빼거나첫교환뒤새2700을주지않는다.

lease는17개닫힌키다: schema_version,unit,nonce,claim_sha256,plan_sha256,template_freeze_sha256,review_sha256,native_approval_sha256,client_started_monotonic,client_deadline_monotonic,remote_started_monotonic,remote_deadline_monotonic,remote_started_unix,remote_deadline_unix,bootstrap_sha256,helper_sha256,handshake_deduction_s. client는client축,Runtime/SDK는remote축을쓴다. claimSHA는자기자신을뺀16키의고정canonicalJSON bytes SHA다. 첫GRANT는그값만전하고claim파일은아직없다. grant는native권한그자체가아니다.

**첫 후속 install/upload부터** 원remote start/end·nonce/claimSHA·핀을typedscalar로명령에전달한다. inlinehelper뒤pure validation에서이미지난끝이면bootstrapstdin/file/claim/child0으로거절한다. 유효하면initialFence(min(now+20,원end))를실제armed한뒤에만길이/SHA가고정된B소스bytes를stdin으로받아검증/로드한다. 첫후속install은이미알려진원끝아래에서만base111 attempt claim을배타생성하고,그bytes가순수GRANT의canonical16키/SHA와정확히같은지확인한다. 중복목적지/기존claim은실패이며기존영수증으로재시도하지않는다. 나머지후속명령도initialowner아래claim을읽어SHA·nonce·원start/end·핀을검증한다. 같은원end fullFence를실제armed하고initial을close/join하며끝을늘리지않는다.

SCP/SFTP는쓰지않는다. 각후속stdin은고정header/Bsource/operationpayload의길이·EOF·SHA를검증하며원끝을모르는상태에서Bsource/application bytes를읽지않는다. operation끝은initial entry mono+고정한도와원끝의min으로고정해module로드시간도포함한다. upload/extract/activate각120,controller는fullglobal(내부native600/motion900/cleanup150·headroom1380/1680),fetch300이다. 후속controller를actualA Job자식으로띄우고종결/원stdout/actualreturn을관측한다. fetch는닫힌ZIP길이/SHA header+bytes를fullFence안stdout으로내보내며client도원client끝안에서만읽어검증/배타저장한다. command/source/claim/정리I/O가막히면owner가자기process를끝내며불명은UNKNOWN이다. 일반OS스케줄정지중즉시실행을보장하지않는다.

활성화는원lease를늘리지않고inactiveconfig의단일token과runtimebudget/executionfreeze/activation을새capsule안에서결속한다. controller는import→정지(render_smoke)→motion42초진단 순서이며 앞목적실패/불명에서뒤목적0,각목적1회·원예비retry정책을자동늘리지않는다. 실패회수도원global안에서만수행하고원실패를덮지않는다. 실제SDK/정지수용/원영상·원시행을회수검증한뒤에만별도결과를수용한다.

## 수용 기준·독립 검토

| ID | 대상 | 필수관측 |
|---|---|---|
| B1 | context/authority | 실제unit/typedPASS/누락·다른unit·hardwaretrue·期限0/비유한·USD typed8negative·무승인run/controller의I/O/SDK전거절 |
| B2 | firstREADY/LIVE | 고정HELLO만/첫Bpayload·파일·claim0,실제owner·stdin/EOF/누락LIVE·늦은READY·first20종결·고정20차감/후속배타claim/noreset |
| B3 | subsequentrelay | 원끝뒤entry read0/원끝직전정확min/claim불일치/실제blockingclaim·진단/전송/ownproducer고정handle종결 및실제command8000미만 |
| B4 | packaging/activation | source20/deps/model/ref/USD·exactallowlist·single-readSHA·새목적지·단일configtoken·template/execution/lease결속·옛approval불사용 |
| C1 | inheritedphysics/wiring | 실제literalentry 다섯째admission/None·정확원4인자복원mutation거절·consumer AST/원physics config 및original10831/1098불변 |
| C2 | lifetimeprefix | actual111recover budget/configread차단에서첫읽기전owner존재·원global1.2초끝종결·phase단독대조·원110frozen반례/양성대조와기전다른관측 |
| C3 | executionfacts | actualchild뒤post-helper예외UNKNOWN·명시NOT_CREATED만NOT_STARTED·heldFILETIME/exit/raw;realprocess.json발행실패+partial/decoy에서knownfacts보존/clock인증거절 |
| C4 | closedlocalpipeline | prepare→snapshot→launch→verify/publish의명시runtime전달·기한산술전I/O0·복사/추출/진단차단owner·동일원끝·활성화없는기본거절 |
| I1 | integration | exactB/Ccallee+controller/SDKentry+stdout/return→회수consumer실제연결. B/CpartialPASS를통합/native로승격하지않음 |
| I2 | preservation | 코드/검토/raw/실패/원장동결·commonbias·각회차/cap실측·nativeapproval전SSH/SDK/CAN0·보호원10831/1098/CAD22불변 |

HOST는자기비관리자프로세스/고정handle·실제파일잠금/pipe를사용하고실물과분리한다. fixture는OUT111아래만쓰며productionmarker와구별한다. HOST의가짜SDK/activation서비스seam을선언하고실제600/120wall경과·원격/SDK수용으로세지않는다. 비작성자는작성자suite반복과다른관측기전을사용한다. 기존A24/110C44/108587을새시험총수로재합산하지않고새111시험수를별도로기록한다. 모든필수MET/미해결0인exact동결source만PASS이며새class/instance는실제union으로기록한다.
