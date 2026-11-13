> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 093 — 승인된 루트 제공 API 수리·COM 정지 검증·조건부 큰 동작

2026-10-31 KST. 사용자가 093 계획과 새 45분 예산을 명시 승인했다. 첫 승인 확인 시계는 03:22:19Z다. 종료 04:07:19Z, 새 발사 마감 03:52:19Z, 각 native 최대600초, import/정지/큰 동작 각1회, 발사 시900초 이상 여유를 강제한다. 검토는 L2 max2/L4 max2이며 첫 검토 전에 고정한다. 기존 091/092 예산·실패·class·원 소스/후보/진단은 무수정 보존한다. 소유는 새 `src/simulation/root_provider_run/`, `outputs/isaac-root-provider-093/`, 본 계획/결과와 최소 인계다.

## 이전 지적에 대한 답

092 최종 비작성자 R3는 BLOCK6/3이다. 실제 root normalize 실패, F1 원속성 미작성 시 목적지 기작성 충돌 누락, F2 메타데이터 전체 원복으로 허용 외 API 삭제를 숨기는 증명 장치 결함을 모두 재상정한다. 원 COM 원인의 유일성은 미확정이며 기존 정착15실패·velocity-only EXHAUSTED를 초기화하지 않는다.

- NewtonArticulationRootAPI와 기본 PhysicsArticulationRootAPI를 함께 Base에서 fixed joint 조상으로 이동한다. 기존 선택 조건과 비물리 identity 조상·11개 body·고정 joint·중복 루트 거부를 유지한다.
- F1: 설치 Newton root schema의 모든 property를 열거하고 **원속성 작성 여부와 무관하게** 목적지 기작성값·시간샘플을 먼저 거부한다. 원속성 시간변화도 거부한다. 원본 작성 속성만 동일 타입/variability/custom/value로 복사하고 모든 속성의 유효값을 대조한다. 현재 자기충돌 false를 유지한다. 지원하지 않는 property/value 형식은 실패 처리한다.
- F2: 실제 before/after USD를 별도 저장하고 재독한다. 두 prim의 작성 API 목록과 합성 API 목록을 모두 관측한다. Base는 허용된 두 API 제거, Scope는 허용된 세 API 추가 이외 변화가 없어야 한다. **이 정확 대조를 먼저 통과한 뒤에만** API 메타데이터를 원복하고 선언된 목적지 속성 복사를 제거해 나머지 authored USD 전체 텍스트 불변을 검사한다. RigidBodyAPI 삭제/추가·제3 API 삽입·다른 속성 변경은 거부해야 한다.
- 실제 SDK observe before/after body/joint/collider/세계 프레임 원검사와 별도로 provider 속성 관측 및 완전 delta proof를 fixed_binding에 결속한다. HOST consumer도 목록/속성값/원시 USD SHA를 검증한다. 원복 후 텍스트 일치만으로 정확 delta를 선언하지 않는다. USD-only 재현은 SimulationApp/native 시뮬과 구분한다.

## 구현·검증 순서

092 실행 소스17파일을 새 단위로 복제한다. driver/output/experiment/remote root/plan SHA·deadline을 새로 결속하며 root_binding과 scene의 provider proof 호출만 추가한다. SDK 수명주기·제어·물성·게인64/16·cap·52초 경로·floor 문맥·COM 허용오차·원 정착 기준은 그대로다. 기존 HOST325건을 새 소스에서 유지하고 provider 합성·F1/F2·속성 누락/충돌/시간변화·원 API 누락·원복 은폐 변형 검사를 추가한다. 기존 검사의 fixture는 새 provider 계약을 충족하도록 명시적으로 갱신한다.

L2 통과 후 구현, Layer A/B 및 HOST 후 비작성자 L4로 F1/F2 음성을 재현한다. 표준 Sonnet 경로의 기존 차단을 도구 수정으로 우회하지 않고 이미 승인된 동일 계열 비작성자 폴백을 사용하며 공통 편향을 남긴다. L4 두 번째 라운드는 필요 수리/실행 후 감사에 할당한다. 마지막 라운드에서도 남은 결함은 수용·보수 정지하며 새 라운드를 만들지 않는다.

물리 없는 실제 설치 USD 검사에서도 원 스냅샷의 수정 전 중복 루트와 수정 후 유일 루트/자기충돌 false, source 미작성+dest true 거부, RigidBodyAPI 삭제 변형 거부, 정확 delta와 나머지 전체 USD 불변을 검사한다. 원본은 읽고 익명 복사본만 변경하며 SimulationApp/timeline은 시작하지 않는다.

fresh import 수용 → 2초 정지 수용 → 52초 큰 동작 각1회다. 정지에서 native fixed_base=true·M9/C9/G9 원차원·실제 root COM/pose/velocity/clock 원검사·원 정착 기준을 모두 통과해야 큰 동작을 시작한다. 실패/마감/예산 부족이면 다음 단계 없이 원자료와 최초 오류를 보존한다. 실제 PNG로 영상 생성·전체 decode·첫/중/끝 확인을 수행하고 프로세스/lock 종료, 보호파일 해시, 인계 원바이트 보존, 로컬 commit으로 끝낸다. 통과하지 않은 물리 관측을 성공으로 승격하지 않는다.

실물 CAN/flash/급전/모터/보정/설치/재부팅/전원정책/구매/학습/외부 업로드는 제외한다. hardware_approved=false. CAD/URDF/BOM/펌웨어는 수정하지 않는다. 질량·관성 가정, 링 보류·포그 숨김·자기충돌 OFF·바닥 ON, moving-root 독립 교정 미완료와 로봇 PD/포화 UNKNOWN을 유지한다.
