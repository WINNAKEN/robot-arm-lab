> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 085 — 084 시험 자료 형식 수리와 실제 재검증 제안

상태: 사용자 새45분 명시 승인. 첫 시계 2026-10-30 11:41:04 UTC(한국20:41:04), 종료12:26:04 UTC(한국21:26:04). 새 prepare/launch는900초 여유로12:11:04 UTC 이전만 허용한다. 084의 시작/종료 시각과 미완료 기록을 변경하지 않는다.

## 그대로 유지할 경계

084의 15항 전체 계산·원 journal 전체 검증·compact audit·FAILED recovery manifest 계약을 유지한다. 실제 shared_metatype.fixed_base와 canonical Base를 읽고, 15항은 실제 기저의 pre/post 속도·COM·clock을 사용한다. 행렬 절단·기저 가속도 0 대체·허용 기준 완화·사후 fit은 금지한다. 원 제어·게인·토크 한도·정착 0.5도/1도초/1초·영상·중력·바닥 기준을 유지한다. 질량/관성은 가정이며 큰 모터로 바뀐 최종 모델을 검증한 것으로 표시하지 않는다. 링 보류·포그 숨김·자기충돌 OFF·바닥 ON을 유지한다.

## 수정 후보와 검증

1. 현재 `host_repair.py`는 옛 `audit.events` 전체 목록을 journal로 쓰는 fixture다. 새 코드가 요구하는 `audit.journal`과 `fault_count`가 없어 KeyError가 발생했다. 재생성 소유자인 `run-host.py`에서 fixture를 새 계약으로 변환한다. 원 이벤트 목록을 별도로 보존하고 반례도 원 이벤트에 적용한 뒤 journal/해시/건수/bounded 초기 이벤트를 작성한다. 새 root validator에서 필수 필드를 생략 허용하지 않는다.
2. 기존 15개 초기화/오류 경로 반례를 모두 유지한다. 원 journal 변조, 요약 해시·건수 변조, 누락/역순/clock/q/state 반례를 분리해 기록한다. 6240단계 전체 journal과 64KiB 미만 audit 대조를 유지하고 필요 시 실패 복구 저장의 이중 오류 경로를 보완한다.
3. 전체 HOST를 실행하고 실제 합계와 원 출력을 저장한다. 실패가 남으면 최종 PASS/소스 동결로 승격하지 않는다. 소스 해시 동결 후 비작성자 L4에서 API·SSOT·오류·순서·범위를 공격적으로 재검토한다. 같은 계열 폴백이면 편향 잔여를 명시한다.
4. 검토 통과 후 fresh import 1회 → render_smoke 정지 1회 → 원 물리 정지 기준 PASS일 때만 motion 1회. 각 native 600초, 재시도 없음. 각 prepare/launch는 잔여 900초 이상일 때만 허용한다. 새 45분 종료 조건은 SDK·검토·영상·인계를 모두 포함한다.
5. 정상 봉인 자료 또는 실패 회수 해시가 결속된 영상만 생성한다. 전체 decode·첫/중/끝 확인 후 기존 Drive 폴더에 영상만 저장하고 메타데이터를 재조회한다. 실패 회수 영상은 성공 영상과 구분하며 report/terminal을 소급 생성하지 않는다. 신규 영상이 없으면 NOT_RUN을 유지한다.

## 소유와 예산

새 단위로 실행 설정을 분리해 084 원 실패·시간 기록·출력 해시를 보존한다. 소유는 복제한 `src/simulation/floating_balance_run/` 및 `outputs/isaac-floating-balance-run-v1/`, 085 계획·결과·최소 인계다. 원본 floating_balance_trial과084 output은 변경하지 않는다. experiment는 floating_balance_085, 원격 root는 기존 config의 /084/runs를 /085/runs로 바꾼 독립 경로, 종료는12:26:04UTC로 결속한다. CAD/URDF/BOM/펌웨어/다른 프로젝트를 수정하지 않는다. L2 최대 2회·L4 최대 2회이며 승인 전에는 검토를 소비하지 않는다. 실물 CAN·보정·모터 운전·플래시·구매·설치·재부팅·학습은 실행하지 않는다. 정확한 축별 큰 모터 사양은 후속 모델 개정 입력으로 남긴다.
