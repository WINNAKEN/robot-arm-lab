> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 118 — MP18 최신 작업 모델을 URDF v4로 옮기기

2026-11-07 KST. 사용자 「모델링이 좀 많이 바꼈어 확인하고 urdf 다음버전으로 만들어줘」가 새 v4 작성 권한이다. 116은 종결됐으며 117 제안 구현과 새 원격 실행은 이번 범위가 아니다.

## 범위와 소유

입력은 현재 작업 트리의 `src/cad/manipulator-v2`, `models/manipulator-v2`, MP18 loads/printprep/build/check, MP16/MP10 및 KG1 원본이다. HEAD의 이전판으로 바꾸지 않는다. CAD 소유 파일, v1~v3, 펌웨어, 실행기 및 116 증거는 읽기만 한다. 출력은 `models/robot-arm-urdf-v4`, `src/simulation/urdf_mp18_v4`, `outputs/urdf-mp18-v4-118`, 이 계획과 공유 인계문서의 추가 기록이다. 실물 CAN/RS485/포트/전원/flash/SDK/SSH/네트워크/설치/출력/구매/프린터 작업은 없다.

## 설계

정본은 사람이 직접 작성하는 `robot_arm.urdf` XML이다. 보조 Python은 메시/계산/검사만 만들고 XML 생성기를 만들지 않는다. 상단 주석에 단위 m/kg/rad, 소비자(CAD viewer/RViz 및 향후 별도 Isaac 가져오기), 프레임·축·양의 방향·각 메시/물성 출처와 가정을 기록한다.

Base/Link1..6/KG1/KG1_A/KG1_B/KG1_R/tool0 이름과 기존 그리퍼 mimic을 유지한다. URDF 팔 0은 CAD 표시 자세 [15,-50,70,15,25,-10]deg이며 CAD 절대각=URDF 상대각+표시각이다. 새 링크 길이는 layout.py의 J3→J4 165mm 등 현재 값, J3 구동 모듈 90도 전환과 91mm 위팔 높이를 따른다. 관절 origin은 실제 CAD 행렬로 계산한다. 링크 메시에는 inv(T_link(CAD0))*T_part_frame을 적용하고 mm→m을 정확히 한 번 적용한다. 색상별 visual 여러 개가 필요하면 동일 링크/동일 local frame의 명시적 예외로 기록하고 전체 링크 메시와 대조한다.

저장 메시의 정확한 식은 `local=inv(T_k(CAD0))*Fr*source_local`이고 표시 배치는 `T_k(display)*local`이다. 이는 `inv(T_k(display))*placement(P,k,frame,display)*source_local`과 같다. CAD0의 Fr를 표시자세 월드 행렬로 잘못 해석하지 않는다.

출력 부품은 최신 catalog STL을 사용한다. 모터/드라이버 등 구매품은 명시된 어림 형상만 표시한다. 단자 여유, 장력 슬롯 끝, 케이블 고리 여유 등 검사 envelope를 실제 중복 부품처럼 넣지 않는다. 충돌은 부품별 convex hull 또는 명시적 단순 근사로 구분하며 기구 안전/자가충돌 통과를 주장하지 않는다.

질량은 MP18 구성별 원래 질량을 재구성해 173개 기록과 보존 대조한다(현재 반올림 합계 8.8639kg). 출력 질량은 슬라이서 추정, 금속/모터는 원장 가정이다. 메시는 부피 중심·텐서를 질량에 맞춰 계산하고, 구매품은 원장 primitive/point 근사를 명시한다. MP18 KG1 총량은 한 번 제거하고 184.2g을 F/A/B/R 구성으로 한 번만 나눈다. 그리퍼 각 실제 primitive/printed part의 질량·COM/텐서를 계산하며 일괄 AABB 물성을 실제값으로 표기하지 않는다. link aggregation은 회전과 평행축 정리를 사용한다. 기존 loads의 point inertia가 0인 품목을 그대로 사용할 경우 추정 한계와 해당 품목을 공개한다. 질량·COM 보존, 대칭 양정치 텐서와 주관성 삼각부등식을 확인한다.

관절 범위는 CAD C5 일축 표본검사와 desk 결과를 분리하여 기록한다. 소스의 `wanted_ranges_deg`는 설계자 제안이며 하드웨어 안전 한도가 아니다. v4의 잠정 시각/운동학 범위는 이 제안(각 일축 표본 범위 내부)으로 하고 URDF 영점 차이를 반영한다. 조합 자세/책상 충돌은 별도 제약이다. 기존 effort/velocity cap은 확대하지 않고 잠정 simulator cap으로 명시한다. 새로운 무거운 모델의 동역학/정지/동작 수용은 NOT_RUN이며 이전 116 수용도 이어받지 않는다.

## 단계·예산·검토

L1 계획 후 L2 비작성자 검토를 통과한 다음 작성한다. 표준 Sonnet bridge는 기존 Python lint 절대경로 지적으로 차단됐다. 도구 수정/우회 없이 사용자가 앞서 승인한 동일 계열 비작성자 폴백을 적용하고 외부 계열 부재·공통 편향을 남긴다. 검토자는 작성자가 될 수 없다. 지적 합집합 처분, L2/L4 각 최대 2회이다.

큰 묶음은 다음 소단위로 분할한다. 생성 STL/JSON 증거는 파생 데이터이며 source file 수와 구분한다. 시간은 각 단위 첫 작성부터 누적하고 대기 시각을 별도 기록한다. 원격 예산은 없다.

* A: 자산·수치 scaffolding 1~3 source files, S 1500초, 최소150초 검증 예비. 작업자는 A 경로만 소유한다. 결과 asset-ledger/provenance/numeric-ledger와 source-preservation 대조. XML 작성 금지.
* B: root의 정본 XML·README·그림/변경표, S 1500초, 최소150초 예비. A 계산 수령 전에는 XML 작성하지 않는다.
* C: 독립 HOST/FK 검증 helper 1~3 source files, S 1500초, 최소150초 예비. 입력/출력 hash, 행렬 기반 FK, mesh/물성/범위/mimic, 기존 자료 보존을 확인한다.
* L2/L4 읽기 중심 검토는 각 M 2700초/회. 동일 계열 비작성자 2렌즈를 사용하며 code 작성자 제외. 수리 시간은 원 소단위에 누적한다.

## 수용 증거

입력 hash와 working-tree 상태를 먼저 봉인하고 CAD build/loads pins의 현재 일치·불일치를 공개한다. source drift가 생기면 해당 입력을 재확인한다. 새 XML 모든 local mesh 경로를 해시 봉인한다. HOST는 독립 URDF FK vs 현재 CAD의 중립/표시/ready/각 축 min/max/조합 표본, gripper 0/40/80mm와 mimic 방향을 확인한다. 길이·질량/COM/관성 및 mesh 프레임·경계를 수치 검증한다.

`cad urdf validate --strict --json`을 통과시킨다. 설치된 check_urdf가 없으면 SKIPPED로 남긴다. CAD viewer에 현재 CAD 및 새 v4를 보여 주고 cad_snapshot으로 6개 팔 관절 각각 양 끝과 그리퍼 leader 양 끝(총14개 끝 자세), 기본 자세를 시각 검토한다. follower를 직접 구동하지 않는다. 샘플 관절끝이 책상/다른 링크와 충돌할 수 있음을 별도 판정한다. 스냅샷은 운동학/외형 증거이며 물리 수용이 아니다.

L4 지적 처분과 최종 원본 보존 대조 뒤 RESULT/README/HANDOFF/SESSION_HANDOFF에 완료·가정·NOT_RUN을 기록한다. 이전판과 CAD는 보존하고 새 v4만 전달한다.
