> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 020 — CAD에서 제어·시뮬레이션으로 잇는 관절 기준

2026-10-23 사용자 계속 지시. 모델링은 사용자/Claude가 담당하며 원본 CAD와 완료된 펌웨어는 읽기만 한다. 계획019의 첫 구현 단위: 현재 저장소 v2 레이아웃을 **후보 스냅샷**으로 추출하고, 기구학/관절 기준을 장치 없이 검증한다. 제작 확정·6축 실물 운전·Isaac 설치/월드 실행 승인이 아니다.

## 범위와 검토

- 작성자 root, 비작성자 L2/L4 검토. 이 단위 예산을 첫 검토 전 L2최대2회/L4최대2회로 선언한다. 기존 펌웨어 first-fault 재발 기록은 변경·초기화하지 않는다. 외부계열 도구 차단 잔여 위험은 이전 scope 기록을 그대로 참조한다.
- 새 소스 `src/kinematics/`(표준 Python만), 생성물 `outputs/joint-control-v1/`, 근거 `.dev/joint-contract-evidence/`, 본 계획과 세션 문서만 수정한다. 기존 CAD 생성기/모델·펌웨어는 수정/실행하지 않는다. 외부 Python을 실행하지 않는다.
- JSON/Markdown 관절표, SI 단위 FK 코어·회귀시험, 입력 SHA256/검증 결과를 만든다. 소스 입력이 틀리거나 불일치하면 실패한다. 생성 시작 전에 current.json을 새 run_id/BUILDING으로 원자 교체하고, 실패 시 같은 run_id/FAILED로 교체한다. 성공 파일은 runs/run_id/ 아래 새 묶음에 저장하고 파일 해시를 담은 manifest를 쓴 뒤에만 current.json을 PASS/run_id/manifest 해시로 교체한다. 기존 성공 묶음은 역사 스냅샷으로 남긴다.
- 현재 수용 여부는 별도 verify 명령만 판정한다. current의 PASS/run_id, 같은 묶음의 manifest/run_id/해시, 현재 원본 파일의 해시, 모든 묶음 파일 해시를 다시 확인하고 하나라도 틀리면 거절한다. BUILDING/FAILED는 이전 성공 묶음으로 폴백하지 않는다. status 쓰기 자체가 실패하면 CLI는 실패하며 실행 성공으로 간주하지 않는다. 사람이 읽는 표에도 역사 스냅샷임과 verify 필요를 표시한다. 정상 생성 뒤 실패한 재생성, 입력 변경, 묶음 훼손, 잘못된 run_id를 실제 임시 폴더 시험으로 검증한다.

## 입력과 의미

v1 `kinematics.json`·`parameters.json`, v2 `parameters.json`·`build-commands.json`·native `.solidcraft`, v2 검사기록을 해시로 고정한다. native ZIP의 유일한 document.json은 크기 상한5MiB 안에서 읽으며 경로 추출/외부 코드 실행 없이 파싱한다. 실제 assembly.joints/occurrences/components도 대조한다. CAD를 다시 열거나 수정하지 않고, 저장된 joint.as_built 여섯 개의 부모/자식·원점·세계축·revolute·표시0이 기구학 기록과 일치하는지 검사한다. 입력의 숫자는 bool 제외 finite, 회전은 SO(3), 축 단위벡터, 체인은 Base→Link1…Link6, 개수6·식별자 유일·mm 단위와 길이/표시각의 교차 일치를 검사한다. 이전 검사 PASS를 새 물리 승인으로 사용하지 않는다. 최신 스냅샷 추출이지 사용자 제작 확정본 채택이 아니다.

각 관절의 부모 지역 오프셋은 부모 표시자세 R의 전치로 세계 원점 차를 변환해 m로 저장한다. `R_fixed = R_parent_display^T * R_child_display`, 부모 지역 축은 `R_parent_display^T * axis_world`로 얻는다. 저장된 지역 축과 대조한다. FK는 `p_child=p_parent+R_parent*t`, `R_child=R_parent*Rot(axis_local,q_delta)*R_fixed`로 계산한다. q_delta는 **새로 정의한 canonical 오른손 표시자세 증분각**이며 native CAD의 angle 값과 동일하다고 주장하지 않는다. 위치/축/링크회전을 모두 반환하며 비유한/잘못된 길이의 q는 거절한다.

`q_geometric = q_delta + display_pose_rad`. 따라서 canonical delta0은 표시 자세 `[15,-50,70,15,25,-10]`도, geometric0은 delta의 그 반대 값이다. 실제 native의 정적 angle/values0과 표시 자세의 연관만 확인한다. 여섯 joint의 flip=true는 기록하되, **native angle→canonical delta 부호/스케일은 null/NOT_RUN**이다. static0만으로 양의 native runtime 회전을 추정하지 않는다. ±170도는 CAD 예시값으로만 기록하며 실물 관절 제한으로 쓰거나 FK의 수용 범위로 강제하지 않는다. 양의 canonical 회전은 추출한 축의 오른손 규칙이며 모터 양의 방향은 별도 미측정이다.

CAN ID·감속비·모터 부호·모터/관절 영점·엔코더 스케일·실제 가동범위·속도/가속/토크·질량/관성은 null/미확정으로 둔다. 모터→관절 변환은 이 항목이 모두 검증될 때만 허용하는 계약이며 이번에는 실행 전송/구동 함수를 만들지 않는다. J3 외장 출력면 부호는 패키징 정보일 뿐 모터 부호가 아니다. 그리퍼는 현 모델에 없어 별도 미구현 항목이다.

J6 원점은 TCP로 이름 붙이지 않는다. v2 링 전면의 지역X 좌표 `depth/2+flange_t+ring_t`만 형상 기준점으로 계산하고, 실제 TCP와 그리퍼 변환은 미정으로 남긴다. SI와 CAD mm/화면 deg 경계를 명시한다.

## 검증과 후속 수용

- canonical delta0 FK가 저장된 모든 원점/세계축/R_child와 일치한다. 이를 native 양의 회전 부호 검증으로 표시하지 않는다.
- geometric0의 원점이 길이 매개변수의 직렬 해석값과 일치한다. 각 축 ±작은 각의 끝점 변화와 세계축×레버암의 유한차분을 대조하고, 혼합 자세에서 회전 직교·거리 불변을 검사한다. **모든 축(특히 J6)의 링크 회전 행렬 각 열의 도함수도 세계축×그 열과 대조**한다. J6 형상 기준점은 축 위에 있어 위치 도함수0이므로 방향 검사를 생략하지 않는다. 이 검사는 충돌/작업공간 안전 검사가 아니다.
- 잘못된 체인/축/회전/단위/숫자/중복/불일치 입력과 비유한 q를 거절한다. canonical0/기구학0 혼동·mm→m 누락·지역 회전을 세계 회전처럼 왼쪽에 적용하는 잘못된 프레임 순서·J6만 부호 반전의 네 행동 변형은 정상 코어 시험이 PASS인 상태에서 실행 실패해야 한다. 이 스냅샷에서 동축인 Rot/R_fixed의 교환을 비동등 변형으로 세지 않는다.
- 비작성자가 실제 입력/생성기/소비 FK/표/실행 결과와 해시를 대조하고 직접 재실행한다. 전체 입력 전후 해시 불변, 완료된 펌웨어 파일 불변을 확인한다.
- Isaac 준비 상태는 `KINEMATICS_ONLY / NOT_PHYSICS_READY`로 기록한다. 질량·관성·충돌 형상·실물 제한/구동 특성·TCP·그리퍼·실행 환경이 없으므로 월드/RL 완료로 표시하지 않는다. 다음 단위에서 이 입력을 채운 뒤 공식 자료와 로컬 환경에 맞춰 내보내기 형식을 정한다.
