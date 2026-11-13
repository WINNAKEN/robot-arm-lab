> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 083 — 승인된 힘·모멘트 관측 수리 검토 및 실제 실행

사용자는 083 제안의 새 45분 검토·실행을 명시 승인했다. 첫 시계 관측 2026-10-30 06:53:59 UTC부터 07:38:59 UTC까지 검토·실행·영상·인계·커밋을 포함한다. 새 prepare/launch는 900초 여유가 있어야 하며 07:23:59 UTC 이후 시작하지 않는다. L2 최대2, L4 최대2, native import/정지/render_smoke/큰동작 중 목적별 import1/render_smoke1/motion1, 각600초를 유지한다. 자동 재시도·새 예산은 없다.

082 최종 pending source16의 SHA를 확인해 `src/simulation/force_balance_run/`으로 복제하고 `outputs/isaac-force-balance-run-v1/`에 새 원장을 만든다. runtime 의미 변경 없이 namespace·실험ID·계획SHA·deadline만 바꾼다. 기준 source는 `source-freeze-final-pending.json`; 검토받은 R2 BLOCK source 및 마지막 수정 diff·HOST225를 함께 읽는다. 082 준비 import는 실행하거나 덮어쓰지 않는다. 081 이하 source/실패/원장/모델/CAD/URDF/펌웨어도 보존한다.

핵심 수리: Dynamics와 References의 close 직전 전체 packet을 JSON-safe 검사한다. NaN/Inf 원값·필드 구조를 NONFINITE_RAW로 보존하고 관측FAIL을 추가한다. getter/journal/partial 저장이 동시에 실패해도 메모리 partial과 오류가 남고 최종 report는 직렬화 가능해야 한다. finite 경로는 불변이다. 비작성자 검토는 실제 source·caller·HOST·packet 참조 수명·원본/수리 diff를 읽고 API/SSOT/오류/순서/범위의 5범주와 9개 MET/UNMET, class를 판정한다. 마지막 수리 검토 PASS 전 native를 금지한다. 동일계열 폴백 편향을 기록한다.

L2 통과 후 위 복제와 HOST225를 재검증·동결한다. L4 통과 후 fresh import→2초 정지→52초 큰 6축 동작을 각1회 진행한다. 정지의 원래 로봇 물리 조건이 통과해야 motion으로 진행한다. 비영 COM full6D 및 M/C/G 대조 실패는 독립 관측 상태로 보존하며 물리조건 성공으로 덮지 않는다. unsupported M layout은 절단·0대체하지 않는다. 힘·모멘트의 frame/pivot/부호/허용오차를 실제 결과에 맞춰 바꾸지 않는다.

robot command·게인64/16·cap·경로·속도·정착0.5도/1도초/1초 유지·바닥·중력·FK·그리퍼·영상 기준은 081/082와 같다. `M*qdd+C+G-FF`는 단계평균 유한차분 잔차 추정이며 로봇 단독 PD 센서가 아니다. 구속/감쇠/외부 기여를 식별하지 못하면 PD·포화·유일원인은 UNKNOWN이다. 기존 정착 실패15·provenance7/physical6/eligibility2·velocity-only EXHAUSTED와 reference 한정 성공은 보존한다. 질량·관성 가정, 자기충돌OFF/바닥ON, 링보류, 포그숨김 유지.

실제 봉인 PNG로 원속도/짧은 영상을 만들고 decode 및 첫/중간/끝 확인 후 기존 Drive 날짜 폴더에 영상만 저장·metadata를 재조회한다. JSON은 로컬 보존한다. 별도 SDK 설치·재부팅·실물 보정·모터/CAN 운전·플래시·구매·학습은 제외한다. 결과가 실패해도 봉인·exit/reap·부분관측·새 영상 여부를 정확히 기록한다. 종료 전 원본 source/HOST/native/영상/Drive/인계 hash를 검증하고 소유 경로만 커밋한다.
