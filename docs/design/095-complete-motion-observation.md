> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 095 실행 계획 — 원기준 52초 완주 관측

사용자 승인 원문: 「좋아 095 계획대로 진행해. 게인·cap·기준은 그대로 두고 모션 한도를 900초로 늘려서 52초 완주를 확인해. 검토 후 첫 원격 실행부터 새 45분 쓰고, 실물 CAN은 계속 건드리지 마.」

094 결과와 095 제안에 따른 별도 관측 재실행이다. 094의 600초 TIMEOUT·39.5초 부분 증거와 J3/J5 34초 endpoint 정착 위치 미달은 보존한다. 시간 연장이 물리 수용 통과를 보장하지 않는다. 동일계열 비작성자 검토 폴백은 기존 사용자 승인을 따른다. 공통편향이 남으며 외부 계열 검토 가능 시 전제를 재검증한다.

소유: src/simulation/complete_motion_run/ (새 source17), outputs/isaac-complete-motion-095/ (새 원장·하네스·검토·증거), 본 계획과 095-results.md, 최소 HANDOFF prepend/SESSION_HANDOFF append. 기존 self_collision_policy_run/094 및 그 보호 목록을 전후 SHA256으로 보존한다. CAD/URDF/BOM/펌웨어/기존 원장·실패·소진 임계는 수정하지 않는다.

## 변경과 고정

source17을 094에서 독립 복제한다. driver/config의 실험명·로컬/원격 경로·계획 해시를 095로 결속한다. timeout_s=600 유지, motion_timeout_s=900 및 motion_launch_headroom_s=1200을 정확 int로 추가한다. 목적은 import/render_smoke/motion만 허용한다. 공통 순수 함수가 목적별 native watchdog와 launch headroom을 반환하고 prepare, launch, 원격 worker, SSH 대기에서 일관되게 사용한다. import/정지 =600/900, motion=900/1200. 불리언·다른 수·목적 혼용·기한 경계를 거부한다. 모션 SSH 대기도 900+150으로 늘려 원격 watchdog보다 먼저 끊기지 않게 한다. 절대 deadline은 모든 작업을 계속 제한한다.

씬/프로그램/게인64/16/cap/물성/경로52초/COM/정착0.5도·속도1도/s/한계·수용 코드는 바꾸지 않는다. fixed9·typed PhysX OFF·제공 API 정확 delta·전체 USD 비교를 유지한다. 정착 검사는 phase endpoint 한 행의 절대 위치/속도 오차이며 지속창 최대값으로 표현하지 않는다. 물성 가정·링 보류·포그 숨김·자기충돌OFF/바닥ON·moving-root 독립교정 NOT_DONE·실제 PD/포화 UNKNOWN을 유지한다.

## 검토와 증거

새 L2 최대2회, L4 최대2회(코드 1회, 사후 증거 감사 1회 예정). 비작성자는 원 계획/코드/config/cross-doc를 직접 읽고 호출부·SSOT·오류경로·순서·규율의 5종 위험과 9개 이진 AC를 판정한다. UNMET가 있으면 native를 시작하지 않는다. 검토자는 코드를 수정하지 않는다. 과거 지적/실패·모든 검토 원문을 보존한다. 예산 소진 시 자동 추가 라운드·튜닝·실행은 없다.

AC1 범위/원승인/실물false; AC2 보호된094·과거실패 불변; AC3 typed 목적별600/900와900/1200 일치; AC4 HOST 양음성·경계·timeout/transport/worker 연결; AC5 검토 전 inactive clock와 검토 후 단일 토큰 활성화/재시작 금지; AC6 source17·harness·plan·review·job 입력 결속; AC7 실제 USD 양음성/API/policy 회귀; AC8 fresh import→정지 수용→52초 모션 게이트와 회수·프로세스 종료; AC9 결과·52초 완주와 전체 물리 수용을 분리하고 원기준/실패를 정직하게 보존. L2/L4 코드 단계의 AC8/9는 실행 전 게이트/판정 계약을 검토하며 native 수용을 미리 주장하지 않는다.

HOST는 094 전체 회귀에 목적별 제한/기한 typed 음성 및 하네스 활성화 변조·반복 실패를 더한다. 독립 검토 실행은 HOST/오프라인 증거 소비만 허용한다. 기존 원격 USD 라이브러리로 SimulationApp 없이 실제 snapshot 양음성을 확인할 수 있다(physics step0/native budget 비활성). 새 실행 소스/단일 deadline 외 16파일과 물리 코드 동일성을 SHA로 기록한다.

## 새 45분 활성화 및 실행

리뷰 전 config.deadline_unix=정확 int0, runtime-budget/activation 없음. 코드 L4 PASS/source-freeze/HOST/USD 결속 후 reviewed execute.ps1가 첫 native prepare/원격 발사 직전에 activate-budget.py를 한 번 호출한다. 그 한 번 읽은 start+2700초가 deadline이다. 검토·수리·USD-only 검사는 이 45분 밖이다. runtime-budget.json을 먼저 exclusive 생성하여 부분 실패도 시계 소비로 남긴다. config 원본 보존 후 deadline 숫자 토큰 하나만 교체하고 17파일 execution-freeze/READY를 결속한다. 삭제·시계 초기화·재활성화 금지.

runtime budget closed schema에 import/정지 native_timeout_s600·minimum_launch_headroom_s900·launch_deadline=end-900과 motion_timeout_s900·motion_launch_headroom_s1200·motion_launch_deadline=end-1200을 정확 typed 값으로 보존·재검증한다. coordinator와 driver는 목적에 맞는 cutoff를 모두 검사한다. deadline 임박 시 새 발사를 막고 증거 회수만 한다.

fresh import 1회 IMPORT_VERIFIED → fresh 정지 1회 SMOKE_VERIFIED → motion 1회 52초 실행한다. 각1회 예약은 실패도 소비, 재시도/추가SDK 없음. 정지 실패·기한 초과·소스 변조 시 이후 목적을 발사하지 않는다. 094 runtime 증거를 새 native proof로 재사용하지 않는다.

완주 여부는 원봉인 terminal/report·연속 journal·최종step/time·frame sidecar·모든 phase endpoint로 검증한다. 원 M9/C9/G9·COM·한계·바닥·그리퍼·FK·렌더·정착을 그대로 소비한다. 전체52초를 관측했더라도 정착 실패면 전체 WORKSPACE_MOTION_VERIFIED를 주장하지 않는다. 실패 terminal도 원본 보존, 부분 회수면 PARTIAL로 별도 표시. 영상은 로컬 1x/3x(가능하면)로 인코딩하고 전체 decode/첫중끝 직접 확인한다. 원격 task PID/lock과 종료 상태를 확인한다.

실물 CAN/serial/flash/급전/모터/물리보정/설치/재부팅/전원정책/구매/학습/외부 업로드는 제외, hardware_approved=false. 로컬 저장·검토 후 정확 소유 경로만 commit하며 push하지 않는다.
