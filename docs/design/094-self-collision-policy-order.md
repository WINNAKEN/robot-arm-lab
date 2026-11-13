> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 094 — 승인된 PhysX OFF 순서 수리·검토 후 native 45분

2026-10-31. 사용자가094제안대로 수리/검토를 먼저 끝내고 첫 원격 native 실행부터 새45분을 쓰도록 명시 승인했다. 물리 없는 USD 검사·HOST·검토는 준비 단계이며 SimulationApp을 시작하지 않는다. 새 L2 max2/L4 max2, native import/정지/motion 각1회·각600초·발사시900초 여유를 첫 검토 전에 고정한다. 093의 실패/소스/검토/시간 원장은 무수정 보존한다. 소유는 새 `src/simulation/self_collision_policy_run/`, `outputs/isaac-self-collision-094/`, 본 계획/결과·최소 인계다.

## 원 지적과 변경

093 native의 최초 오류는 Self collision remains false였다. Root는Scope하나, Newton false는 작성됐지만 새 PhysxArticulationAPI 자기충돌 값은 미작성 기본 true였다. scene은 OFF 설정 전에 after 관측/검증을 했다. native물리step0/COM미도달이다. 기존 SDK의 bool(None)=false는 명시적PhysXOFF 관측이 아니다. 이 제품 초기화 순서 결함과 증명 계약의 누락을 재상정한다. 비작성자는 class·재발/소진을 독립 판정한다. 이전 F1/F2/목록 누락의 수리 및 원COM가설·정착15실패·velocity-only EXHAUSTED·임계는 유지한다.

- timeline stopped를 확인한 원 prepare_self_collision_api 반환 attr에 false를 실제 Set하고 typed readback을 한 뒤 base-after 저장과 root_binding.verify를 수행한다. 이후 기존 robot.set_enabled_self_collisions(False)도 유지한다. 순서/값 검사를 제거하지 않는다.
- root_binding의 Newton2속성/API 검사는 유지한다. 별도 정책 관측을 추가해 정확한 이름 `physxArticulation:enabledSelfCollisions`의 존재/type/작성 여부/시간샘플/variability/custom/유효값을 기록한다. 설치generatedSchema는 nonuniform bool 기본true이며 지원정책은 bool·Sdf.VariabilityVarying·custom=false·시간샘플없음·작성된false다.
- before의 목적지Scope에는 이 속성이 존재하지 않아야 한다. after에는 위 정확 계약의 속성 하나가 새로 작성돼야 한다. 원Base 속성은 이동/삭제하지 않는다. proof의 API와 Newton 원검사를 먼저 통과하고 정책 전후 관측을 정확히 검증한 뒤에만 선언한 Scope 정책 속성 하나와 원 Newton 복사를 제거하여 전체 authored USD 불변을 검사한다. 임의 이름/값/타입으로 허용 변경을 넓힐 수 없다.
- HOST consumer도 같은 정책 이름·타입·전후 상태를 검증하고 SDK after.self_collision=false 및 원 USD SHA와 결속한다. native 전후USD에서 정책 미작성기본true·명시true·잘못된타입·시간변화·삭제·허용외PhysX속성 변경·RigidBody삭제·Newton목록 누락을 거부한다. 실제 scene 호출 순서 변형도 검출한다. 기존358건은 새 필수계약 fixture를 명시적으로 보강하며 유지한다.

## 검토 후 마감 시각 확정

실행 코드17파일을 검토 전에 복제·수리하되 config.json의 deadline_unix는0인 미활성 템플릿으로 둔다. 이 상태로 기존 driver의 시간 게이트는 실제 prepare/run을 거부한다. driver의 시간 게이트/수명주기/제어 코드는 변경하지 않는다(094경로·실험·plan SHA 결속만 바꾼다).

검토하는 activate-budget.py가 L4 PASS와 plan/template freeze/script SHA, 모든17템플릿 파일을 대조한 뒤 native 최초 prepare 직전에 한 번만 실행된다. 단일 현재시각start를 읽어end=start+2700, launch_deadline=end-900을 계산한다. config의 **deadline_unix 한 숫자 토큰만** 변경하고 나머지 원 바이트와16개 파일이 같음을 검증한다. 마감시각/파일 해시·원설정·template SHA를 별도 activation/runtime-budget/execution-freeze 기록에 결속한다. 코드 템플릿 검토 뒤의 이 숫자 생성은 검토된 생성기의 데이터 출력이며 소스 로직의 재수리가 아니다.

활성화 기록은 exclusive create로 한 번만 만들고 재실행/기존 budget/예상외 config 변경/불리언·비유한 시각/해시 불일치를 거부한다. 실패해도 시간을 재설정하거나 활성화 기록을 지우지 않는다. config 교체는 검증한 임시 파일의 같은 소유 경로 내 원자교체로 한다. 실행 하네스는 이후 실제17해시·activation의 정확45분·동일 deadline을 매 단계 확인하고 원 launch.ps1의 public prepare/run만 호출한다. native도 해당config의 기존900초/절대마감/600초/원장 게이트를 적용한다. 승인 기록과 최초 remote 발사 시간을 보고해 템플릿과 실행 데이터 변경을 혼동하지 않는다.

HOST에는 허용 한 필드 외 변경, source 변경, 반복 활성화, stale review/freeze, 잘못된 시각/기간·경로를 거부하는 반례를 넣는다. 활성화/execute 하네스도 freeze와 비작성자 검토 범위다. 검토 전에는 활성화하거나 native를 준비하지 않는다.

## 실행과 종료

L2→구현→Layer A/B/HOST/실제USD→비작성자L4 순서다. 기존 Sonnet bridge 차단을 수정해 우회하지 않고 이미 승인된 동일계열 비작성자 폴백·공통편향을 기록한다. L4 두 번째 라운드는 수리 또는 사후 감사용이며 추가 라운드를 자동 생성하지 않는다.

코드 수용 후 활성화와 fresh import →2초 정지→통과할 때만52초 큰동작 각1회다. 정지는 native fixed_base=true/M9/C9/G9·root COM/pose/velocity/clock·원 정착 기준을 모두 만족해야 한다. 실패/마감/한도면 원자료·최초오류를 보존하고 다음 단계를 실행하지 않는다. 실제PNG 영상/전체decode·첫중끝 확인·프로세스/lock 종료·보호파일/인계 원바이트 보존·로컬commit까지 포함한다. 물리 수용과 코드/정적USD 수용을 분리한다.

실물CAN/flash/급전/모터/보정/설치/재부팅/전원정책/구매/학습/외부업로드 제외·hardware_approved=false. SDK·물성·게인64/16·cap·52초 경로·COM 허용·정착 기준은 그대로다. CAD/URDF/BOM/펌웨어 무변경, 물성가정·링보류·포그숨김·자기충돌OFF목표/바닥ON·moving-root 교정미완료·로봇PD/포화UNKNOWN 유지.
