> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 084 — 재개 시점 상태 보존

관측 시각: 2026-10-30 10:05:20 UTC / 한국시간 19:05:20.
계획 084의 기존 구간은 07:46:03~08:31:03 UTC였으며 재개 시점에 이미 만료되어 있다. 종료 시각을 소급 변경하지 않고 새 SDK prepare/launch를 실행하지 않았다.

## 구현과 시험 상태

- 15항 전체 행렬과 실제 기저 속도·COM·clock 대조, compact audit + 전체 journal 해시/건수 결속, 부모 실패 recovery manifest 구분을 구현 중이다.
- 새 HOST 대조 21개와 기존 동역학 HOST 34개는 기록상 PASS다. 전체 회귀는 `host_repair.py`의 구형 시험 자료가 새 `audit.journal` 필드를 제공하지 않아 `KeyError: journal`로 중단됐다. 전체 PASS로 취급하지 않는다.
- 원인은 현재 시험 자료 생성기의 기록 형식 불일치로 파악했다. 실제 SDK 초기화가 정상이라는 증거는 아니다. 새 validator에서 필수 필드를 생략 허용하는 방향으로 수정하지 않는다.
- L2 R1 PASS 기록 있음. 최종 전체 HOST 동결 및 L4는 아직 미완료다. 084 native import / render_smoke / motion 모두 NOT_RUN, 새 영상·Drive 업로드 NOT_RUN.
- 083 원래 실패, 원장, 원자료, 영상은 보존한다. 기존 정착 실패나 PD 토크·포화 UNKNOWN 상태를 닫지 않는다.

## 다음 수정 후보

`outputs/isaac-floating-balance-v1/run-host.py`는 기존 `host_repair.py`를 이전 시험 폴더에서 매번 재생성한다. 따라서 생성 단계에서 원 이벤트 목록 전체를 별도로 유지하고, 그 목록으로 원 journal을 쓴 뒤 새 bounded audit·해시·건수 형식을 만드는 시험 자료 어댑터가 필요하다. 반례별 원 이벤트 변조는 그대로 원 journal에 전달해 순서·clock·q·상태 유효성 반례를 보존한다. validator의 새 원자료 계약은 유지한다.

새 실행 단위가 승인되면 위 시험 자료 생성 수리 → 전체 HOST → 소스 동결 → 비작성자 L4 → import → 원 기준 정지 → 정지 PASS일 때 큰 동작 → 영상 검증·저장 순서로 진행한다. 실제 부품 보정·모터 운전·기준 완화는 계속 제외한다.

모터 변경/도착 전 통신 준비 대조는 `084-motor-change-and-can-readiness.md`에 저장했다. 최종 큰 모터 사양은 아직 현재 시뮬레이션에 확인된 값으로 반영되지 않았음을 명시한다.
