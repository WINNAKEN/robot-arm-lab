> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 062 — 12열 generalized force와 관절6토크 매핑

2026-10-29 사용자 「12열에서 관절6개 토크를 정확히 매핑하는 새 계획…수정하고2초자세유지랑낙하·접촉시험까지검증」을 따른다. 061의실제[1,12]거절/중력step0/명령0·047미해결원본을보존한다. 실제12값과매핑을먼저측정하며 shape만으로실제base가자유롭다고판정하지않는다.

M급새src/simulation/mapped_gravity9파일+이계획1, outputs/isaac-mapped-gravity-v1소유. 05:48~06:33UTC45분. L2/L4각max2비작성자정적검토. 이전외부hook차단재시도/우회없음same-familyfallback한계. .dev/CAD/BOM/047~061원본무수정. 기존provenance7EXHAUSTED/physical6EXHAUSTED/eligibility2+다음동종독립실측작성자수용1충분임계와first-fault이력유지;예산내class착지/소진미소진판정요구.

061source9를새namespace로복사해원061/nested원장SHA·3예약을새원장에결속한다. baseline0g10step/11row·physics9·nativeclock·4facet·metadata/GPU·source/PID/job/해시·actual/policy/shell/SSH/local종료코드·7번째gravityartifact·最初오류/cleanup우선순위를유지한다. 새audit900/diag300/connection600각max1,freshness300,실패도소진하며재실행으로튜닝하지않는다. 기존일반동작047/28checkpoint worker·학습을재개하지않는다.

현재pinned SDK Articulation3842~3925는원본열을고정baseD 또는root-wrench6+D로정의하고전체generalized열에서dof_indices를선택한다. 새순수mapper는실제N=1,정확한D=6/6이름중복없음과shape[1,6]또는[1,12]·전체유한값을검사한다. 6열은offset0/DOFS_ONLY,12열은offset6/ROOT_WRENCH_THEN_DOFS로선택한다. native이름순서에서J1~J6의위치를찾고offset을더한절대열번호로canonical6값을만든다. 앞6 root-wrench는원본그대로기록하고명령·포화판정에사용하지않는다. 임의slice/이름없음/다른shape/NaN/DOF이름·절대열번호의중복과잘못된순열을거절한다. 토크값의중복과여러0값은합법이다.

runtime은전체getter(no선택인자)원본shape·값·nativeDOF이름을선택전에기록한다. 실패에도원자료가남도록gravity-report의pending_native에관측단계/shape/유한여부·값(비유한은repr·명시표시)을저장하고,완료row가없어도보존한다. 성공시전체원본/native_shape/native_offset/native_layout/native_root_wrench/native_dof_names/native_columns/canonical값을각actuation에결속하고pending은완료전에제거한다. 실제API의class/module/method정의·바인딩동일성·source위치/핀·Articulation path·DOF이름을기존physicssource/원관측과대조한다. sourcefixedjoint그래프와실제Base시작pose를별도로기록하며WorldFixed존재를6열보장으로사용하지않는다.

명령직전actualLINK/검증된COM·mass/jointframe으로토크를재계산하고mappednative6값과최대1e-3Nm이내인지검사한다. 불일치하면pending원자료와오차를보존하고명령·step전실패한다. wrongoffset을잘못된동역학실행으로확인하지않는다. 같은clock/pre-step/직전자세결속,원cap[3,6,5,2,2,1],zeroPD를유지한다. native의prefix6값을관절토크나측정모터토크라고표현하지않는다.

root는terminal에hash결속된같은cachedrobot순수소비부에서원본shape/값길이·finite·실제이름을검사하고offset/절대columns/layout/prefix/canonical을독립재계산한다. producer의offset선언을권위로쓰지않는다. root도보낸명령의사전native↔math적격성을확인한다. API·source·base그래프/실제pose·같은run/job/PID/view/clockowner를묶는다. 기존041/060/061의모든frame·COM/inertia·contact행렬/인덱스/활성접촉재구성·읽기불변/절대시간·240step/241state조건을삭제·정규화·대체하지않는다.

2초동역학수용은061과동일: 전체q≤0.5°·qd≤1°/s,토크일치1e-3Nm·미포화,원치않는robot/probe접촉≤1e-3N(Base-floor장착면제외),probe낙하≥.05m/1초후z=.025±.002m/바닥양성힘>.1N. 자료오류/API/매핑적격성위반은FAILED/INVALID_EVIDENCE,유효자료의hold/contact실패는GRAVITY_DIAGNOSTIC_FAILED/local1로actualworker0과구분한다. baseline연결사실과중력성공을합치지않는다.

호스트:06120시험보존(이전12열거절사례는지원양성으로개정하고이상8열/2행거절을유지),6/12열·큰prefix·합법DOF순열양성,틀린offset/columns/prefix/native원본/이름누락·NaN·이상shape/재해시root변조음성,actualcollector240명령·앞prefix미사용·명령전불일치차단/pending보존·최초오류/cleanup회귀,root유효동역학FAIL을확인한다. AST/whitespace/L4후실제3purpose를순차실행·정리·인계·scopecommit한다. 정적/host와실제SDK결과를구분한다.

질량·관성가정/047미해결/링보류유지. 재부팅/설치/실물보정/모터운전/CAN/flash/구매/학습없음. 성공해도047전체56.5초동작·28checkpoint·RL·실물수용이아니다. API참고 https://docs.isaacsim.omniverse.nvidia.com/6.2.0/py/source/extensions/isaacsim.core.experimental.prims/docs/index.html (설치source3842~3925와실측우선).

## L2 R2 입력 — 접촉 관측값의 float32 구간 대조

실제062 SDK실행전, 기존047 c5f834…의첫241원관측을작성자가읽기전용대조했다. row19/probe-floor/Z: matrix22.562053680419922N,4개scalar합22.562055110931396N,차이1.430511474609375e-6N으로기존절대1e-6을넘는다. matrix/scalar가float32정확표현값임을확인했다. 이는062측정이나실제backend알고리즘증명이아니며원자료/해시·example을보존한다. 단순히이한건을PASS시키는임계튜닝대신, 새중력phase에서관측값자체의float32양자화구간을명시대조하도록L2에재상정한다. baseline0g검사는무수정이다.

각force/normal/matrix성분은유한하고float32왕복표현이동일해야한다. δ(x)는해당float32의보수적인반ULP(정규수frexp지수e이면2^(e-25),0/비정규수2^-150)다. scalar f와normal n의곱불확실성은 |f|δ(n)+|n|δ(f)+δ(f)δ(n),합은각구간합이다. component재구성오차허용은기존floor1e-6+δ(matrix)+Σ곱불확실성으로산출하고,예산이1e-4N을넘으면정밀도불충분INVALID_EVIDENCE로거절한다. 이는관측값구간의양립성이지실제C++연산순서/참힘의증명이아니다. 1e-3N원치않는물리접촉기준·probe양성>.1N·모든물리/시간/frame기준은불변이다. 원자료고정절대검사차이·구간예산·최대실제차이를별도기록한다.

호스트에역사적roundoff양성/같은자료+.001N 및+.01N matrix변조음성·비-float32/NaN/정밀도예산초과거절을추가한다. 기존raw집합·mapping/count/active재구성은유지하고새구간검사및원1e-6기준결과를병기한다. L2 R2의독립논리판정전에는이수치변경을구현/SDK실행하지않는다. 실제목적별1회·L4최종R2·06:33UTC캡은늘리지않는다.
