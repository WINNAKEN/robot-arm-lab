> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 067 — 수정된 전체 CAD 기반 URDF v2 계획

2026-10-29. 상태 PLAN_READY / L2 PENDING. 작성 urdf_update, 비작성자 검토는 부모가 조율한다. 시간 예산 09:21–10:06 UTC, L2/L4 각 최대 2회. 사용자 추가 URDF 작성 권한은 부모 작업 지시에 결속한다.

## 범위와 원천 선택

정본 전체 조립은 `models/arm-v3-kg1-assembly/assembly.json`(MP9 rev1), 그리퍼 설정은 `src/cad/arm-v3-kg1-assembly/parameters.json`, 팔 형상은 `models/armold-mks-product-v3/bodies.json`의 링크 소유권과 `meshes/*.stl`, 관절 원점/축/표시 자세는 `models/armold-mks-concept-v1/kinematics.json` 및 독립 `parameters.json`이다. MP9 실제 입력 SHA를 현재 파일과 재대조한다. 구 URDF v1의 J1..J6 origin/axis/표시0를 비교한다.

MP10 J5 실부품은 목 결정 대기인 독립 모듈이며 전체 v3에 통합되지 않았다. MP11 분해도도 J5는 v3 외장이라고 명시한다. 따라서 이번 전체 URDF는 MP9 rev1 전체 조립을 반영하고 MP10은 비교/제외 이유를 원장에 남긴다. MP10 부품을 v3 J5 외장에 겹쳐 넣거나 미정 접속을 만들지 않는다.

그리퍼는 MP9 `g_to_link6_local` 행렬(위치 +X28 mm, G x/y/z = Link6 y/z/x), FLAT 패드, u=20 mm인 현재 표시 조립을 고정 공구로 넣는다. 쥐는 점은 G (0,0,103) mm로 고정 frame-only `tool0`에 둔다. 그리퍼 개폐/서보/감속기 내부 DOF는 이번 모델에 없다. 검증된 표준 URDF 관절 대응이 없는 상태에서 움직임을 추정하지 않는다.

## 소유 경로와 불변 입력

수정 허용: 이 계획, `models/robot-arm-urdf-v2/`, `outputs/urdf-revised-v2/`, 계산/검사 보조 `src/simulation/urdf_revised/`. CAD/BOM/core/.dev/기존 URDF/기존 simulation source는 읽기만 한다. 동시 작업자의 변경을 되돌리지 않는다. 설치/SDK/SSH/실제 시뮬레이션/모터/CAN/물리보정/재부팅/학습/출력/구매 없음. 링 형상 검증 보류를 유지한다.

## 구현

1. 불변 입력의 path/bytes/SHA256 및 원본 파일 집합을 시작 시 고정한다. CAD 기존 STL을 읽기만 하며 링크별로 정확히 변환/합친다. 팔 STL mm 세계좌표를 v1 R_child/origin의 역변환 후 0.001 배해 링크 좌표 m로 저장한다. 한 링크의 명시적 시각 메시 집합 또는 단일 합친 STL을 사용하고 시각 origin은 identity로 한다. 그리퍼는 소스 STL와 기존 assemble 함수의 읽기 전용 조립 계산으로 u20/FLAT를 복원한다(구매품 proxy 포함 여부를 명시). 보조는 URDF를 생성하지 않는다.
2. `.urdf` XML 자체를 정본으로 직접 작성한다. 상단 주석 원장에 각 링크/관절의 프레임·부호·단위·메시·가정·소스를 싣는다. J1..J6 이름과 기존 표시 delta rad 규약을 보존한다. q=0은 [15,-50,70,15,25,-10] deg 표시 자세다. 고정 `KG1`과 frame-only `tool0` 추가. 원래 ±170deg는 모의 한계이며, J5는 MP9 표본 검사 절대 [-110,110]deg를 표시 delta [-135,85]deg로 변환한 보수적 표시 범위다. 어느 한계도 물리 안전범위/충돌 없는 경로로 주장하지 않는다.
3. 질량은 기존 arm의 임의 7값 [1.2,.65,.7,.65,.4,.35,.2] kg 유지하며 새 v3 메시 AABB 중심/균일상자 관성을 계산한다. KG1은 기존 mass-properties의 약184.2g 추정 질량만 사용한다. 원본 COM은 닫힌 자세 값이므로 u20 물성으로 옮기지 않고, 실제 u20 메시 G좌표 AABB 중심/균일상자 관성을 새 가정으로 계산한다. collision은 각 링크 AABB proxy이고 가짜 접촉 가능성을 명시한다. 실측 물성·actuator rating은 아님.
4. manifest/assumptions/provenance에 실제 쓴 mesh/URDF SHA와 입력 경로·소스를 묶는다. 신규 모델의 physics/runtime 상태는 NOT_RUN으로 시작하며 065 결과를 상속하지 않는다.

## 수용과 음성 대조

- 고정 입력 전후 path/bytes/SHA 일치. MP9 입력 지문과 현 v3/kinematics/그리퍼 지문 일치 또는 어긋남을 BLOCK/명시한다.
- 실제 작성 URDF 재파싱 후 J1..J6 parent/child/origin/rpy/axis를 기존 v1 및 독립 v1 parameters FK와 비교한다. 표시0·각 축 ±5deg·mixed 자세·lower/upper 포함 최소 26자세/156관절 frame을 m 단위 계산으로 대조한다. 메시를 실제 STL로 재독해 q0 세계 복원 최대오차를 float32 범위(5e-8m)에서 검증하며 source body/link 누락·중복 0을 요구한다. G→Link6 고정행렬과 TCP131mm도 수학적으로 대조한다.
- 실제 asset AABB와 collision/COM/관성 원장을 재계산 대조하여 metadata만 reseal한 거짓 자료를 막는다. SHA를 새로 맞춘 joint-origin 변경, axis flip, visual-origin rotation, mesh scale1000배, collision size 변경, inertia 변경, mesh vertex 변경, body ownership 누락, fixed mount translation 변경, TCP 변경 최소10개 대조가 실제 검증 소비부에서 거절되어야 한다. 정상 자료 전후 PASS를 확인한다.
- 설치돼 있는 `cadgen +0.8.2 urdf validate ... --strict --json`를 실제 실행한다. 미설치/캐시 없음이면 doctor/설치 없이 명령 실패와 간극을 남긴다. `check_urdf`가 있으면 실행, 없으면 NOT_RUN.
- CAD Viewer에 실제 정본 URDF를 표시하고 `cadgen snapshot`으로 표시0와 J1..J6 각 양음/끝 자세를 검토한다. 동작 범위/부호 검토를 실제 시행한 만큼 기록한다. 도구/엔진 부재면 viewer sweep을 NOT_RUN으로 보고하고 수학 검증을 viewer 완료로 바꾸지 않는다.
- 독립 L4는 읽기 전용이며 원래 지적/반례/클래스 원장을 요구한다. 기존 provenance7/physical6 EXHAUSTED, eligibility2-next1, first-fault·047/063/064 실패 이력과 링 보류를 보존한다. 새 모델은 static-only이며 RViz/Isaac/IsaacLab/접촉/중력/경로추종/하드웨어는 NOT_RUN.

## 전달과 종결

모델 README, 검증 JSON, 원천/가정 원장, static 배포 ZIP과 인계를 소유 경로에 쓴다. 비작성자 L4 통과 전 완료/로컬 커밋을 선언하지 않는다. 전용 경로만 로컬 커밋하고 부모의 동시 변경과 분리한다. 외부계열 검토 부재/동일계열 fallback은 부모 검토와 구분해 기록한다.
