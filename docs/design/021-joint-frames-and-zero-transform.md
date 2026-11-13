> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 021 — 관절축·영점 수학 코어

사용자 2026-10-23 지시: 링 형상 검증을 보류하고 관절축·영점 변환에 집중하는 새 계획으로 진행한다. 020은 동결 BLOCK이며 수용을 승계하지 않는다.

## 범위와 입력 계약

- 새 `src/joint_frames/`에서 stdlib Python만 사용한다. 입력은 `models/armold-mks-concept-v1/kinematics.json` **한 파일**이다. 이것은 v1 표시 자세의 후보 수학 기준이며 v2 native CAD와 일치한다는 증명은 이번에 하지 않는다.
- units=mm, joint_count=6, joints 길이6, J1..J6, Base→Link1..6 순서를 검증한다. 소비 필드는 name/parent/child/origin_mm/axis_world/axis_parent_zero/pose_deg/R_parent/R_child다. 원본의 다른 키는 해석하지 않는다.
- JSON 중복 키·비유한 값·64단계 초과·1MiB 초과를 거절한다. 모든 소비 객체/배열/숫자 형식을 확인한 뒤 frozen dataclass로 만든다. bool은 숫자가 아니다. 좌표 크기1e6mm, 각도±360도, 회전행렬 원소±1.000001의 유한 범위를 검증한다.
- SO(3), 단위축, 부모 회전 연속성, 부모축→월드축, Rodrigues(axis,pose)와 상대 회전 일치를 검사한다. 타입 검증 전에 mapping 접근/수학 연산을 하지 않는다.

## 계산과 결과

- SI m/rad. q_delta=0은 저장된 표시 자세. canonical 우수 회전이며 native runtime 부호가 아니다. q_geometric=q_delta+pose_rad. 역변환은 뺄셈이다.
- 로컬 이동=R_parent^T*(origin-parent_origin)/1000. FK는 부모 이동 후 로컬축 회전과 표시자세 고정회전을 합성한다. 결과는 관절 원점과 링크 회전행렬만이다. TCP/링 전면을 출력하지 않는다.
- 모터/CAN ID/감속비/실물 영점/엔코더 스케일/한계/질량·관성/native angle 부호는 null 또는 NOT_RUN. 펌웨어·CAD·Isaac 연결 없음.
- CLI build는 새 출력 디렉터리만 사용한다. 단일 작성자 전제, 병렬 작성 미지원. 독립 run 디렉터리에 입력 스냅샷·결과·manifest를 저장하고 current는 atomic replace한다. manifest는 입력/producer/결과 SHA256 및 run ID를 묶는다. verify는 읽기 전용으로 current PASS/run ID/해시/현재 입력·producer 동일성을 확인한다. 과거 run fallback 없음.
- 실행 경계는 BUILDING을 먼저 기록하고 성공 flag를 마지막에 설정한다. try/finally에서 성공하지 않은 모든 일반 예외에 FAILED/run ID/reason을 남기고 원예외를 다시 던진다. 실패 상태 쓰기도 실패하면 nonzero로 끝나며 PASS로 수용하지 않는다. 저장장치 고장/강제종료/동시작성에 대한 terminal 기록 보장은 하지 않는다.

## 검증·검토 예산 (첫 검토 전 선언)

- L2 최대2회, L4 최대2회. 비작성자 검토만 수용한다. 외부계열 검토는 기존 중앙도구 차단으로 NOT_RUN 잔여위험이며 우회하지 않는다.
- 입력의 모든 소비 필드에 잘못된 구조/누락/타입 변형을 주입하고 **실제 build 후 FAILED**를 검사한다. 숫자 overflow/깊이/JSON 오류, 예기치 못한 RuntimeError, 결과 변조/입력 변경/producer 변경/실패 뒤 과거 PASS 거절을 시험한다.
- 표시/기하영점, round-trip, 독립 기하영점 좌표, 모든 축의 위치·회전 finite derivative(특히 J6), 잘못된 단위·영점·회전순서·J6부호 변형 검출을 실행한다.
- 020의 input/result-finalization·native indexed-geometry 두 EXHAUSTED 원장과 반례를 유지한다. 새 제출 후 **다음 추가 독립 실측·수용된 동일 class 재발 하나면 EXHAUSTED**이며 직렬 국소수리하지 않는다. 새 번호가 이력을 초기화하지 않는다. 기존 firmware first-fault 임계 NOT_REACHED도 유지한다.
- 링 형상·native 점 인덱스 증명은 미해결 백로그다. 제외는 폐쇄가 아니다. 이전 020 출력 REVIEW_BLOCKED를 유지한다. 기존 CAD6/펌웨어97 및020 동결 경로의 전후 해시를 확인한다.
- L4 PASS 후에만 새 결과를 OFFLINE_MATH_CANDIDATE로 인계한다. 실제 CAD runtime/실물/제어 수용과 구분한다. scoped local commit만, push 없음.
