> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 084 — 15항 일반화 좌표의 동역학 관측 제안

상태: 제안만 작성. 아직 source 변경·새 SDK 실행·예산 시작은 하지 않았다.

083 정지 시험은 로봇 물리 조건과 비영 COM full6D 기준물 대조를 통과했다. 하지만 실제 질량행렬은 모든 20개 표본에서 `(1,15,15)`, C는 `(1,15)`였다. 기존 9×9 전용 검증기는 의도대로 UNSUPPORTED를 반환했다. 이를 로봇 PD·포화 또는 정착 원인의 확증으로 읽으면 안 된다.

설치된 SDK 원본의 mass_matrix_shape 계약은 floating base에서 관절 D에 기저 6개를 더한 형상이며, C/G는 root-wrench 6개 다음에 관절 항이 온다. get_root_velocities는 세계 좌표의 기저 COM 선속도와 각속도를 반환한다. 따라서 15×15는 이 계약에 부합하지만, 실제 shared_metatype.fixed_base 플래그와 root 상태는 이번 관측에 포함하지 않았다. API 문서로 실제 flag 계측을 대신하지 않는다.

후속 변경 후보는 다음과 같다.

1. 먼저 083의 종료·저장 경계를 수리한다. 52초/521프레임 이후에도 최종 report/terminal이 만들어지지 않고 600초 watchdog이 작동했다. 회수된 init-boundary JSON은 VIEW_READY, 중간 tmp가 남아 있어 초기화 audit의 최종 직렬화 경로를 조사하되 이를 유일 원인으로 단정하지 않는다. 전체 단계 자료는 원 journal에 보존하고 요약 audit의 크기·쓰기 시간을 제한한다. 실패·시간 초과 때도 부모가 실패 상태의 회수 manifest를 남기는 새 계약을 검토하며, 과거 실행에 terminal/report를 소급 생성하지 않는다. 원 600초 제한은 늘리지 않는다.
2. 실제 native fixed_base flag·matrix shape·기저/관절 항 순서를 기록하고 검사한다. 15×15를 9×9로 자르거나 기저 가속도를 0으로 만들지 않는다.
2. 기존 원 step의 전후 root COM 6D 속도와 transform·COM을 같은 engine/Lab clock에서 읽는다. 세계 좌표·COM 기준·선속도/각속도 순서와 실제 root body를 결속한다.
3. 같은 pre-step M15/C15/G15와 관절 전후 속도를 보존하고, 완전한 15항 단계평균 가속도로 역동역학 추정을 계산한다. 기저 성분의 좌표·기준점이 일치함을 독립 기준물로 검증하기 전에는 계산 성공을 승인하지 않는다.
4. 잘못된 기저 순서·COM/원점 혼합·zero-padding·누락된 교차항·다른 clock·부분 저장 실패를 HOST 음성대조로 차단한다. 비작성자 검토 후에만 새 native를 실행한다.
5. 관절 residual은 감쇠·구속·접촉·외부력 기여를 구분하기 전까지 단독 PD 센서가 아니다. 실제 USD 설정에는 각속도 감쇠 약0.05가 있으나 설정값을 실제 감쇠 토크나 정착 실패 원인으로 단정하지 않는다.

기존 경로·게인·토크 cap·정착 0.5도/1도초/1초·속도·중력·바닥·FK 기준은 유지한다. 기저를 강제로 fixed로 바꾸거나 원 모델/관성을 고쳐 행렬 형상을 맞추지 않는다. 083 이하 원자료와 실패·소진 이력을 보존한다. 실물 보정·모터/CAN 운전·재부팅·설치·구매·학습은 제외한다. 실행한다면 별도 사용자 승인과 새 45분·목적별 1회·600초/900초 여유 한도를 먼저 선언한다.

근거: `outputs/isaac-force-balance-run-v1/smoke-layout-diagnostics.json`, 봉인된 정지 report, 설치 SDK 원본 `outputs/isaac-physics-v1/evidence/sdk-source/articulation.py`의 mass_matrix_shape/get_dof_coriolis_and_centrifugal_compensation_forces 및 현재 input/ref/torque_api.py의 get_root_velocities. 현재 flag·기저 속도는 NOT_MEASURED이다.
