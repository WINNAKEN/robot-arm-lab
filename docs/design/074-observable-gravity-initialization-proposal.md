> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 074 제안 — 중력 제어 이전의 초기화 진행을 분리

상태: **PROPOSED / 소스 수정·SDK 추가 실행 NOT_RUN**. 073 실패를 소급 통과시키거나 원장·횟수를 초기화하지 않는다. 새 실행은 073의 남은 motion 슬롯으로 우회하지 않는다.

## 확인한 문제

073 최신 모델 import는 PASS였다. 첫 smoke는 임시 NodeType 객체 주소를 타입 이름으로 사용한 영상 검증 오류로 실패했다. B-only API 수리와 독립 검토 뒤 두 번째 smoke는 actual0/policy0/REAPED로 241행·실제 RTX 21장을 생성했다. 그러나 전체 수용은 다음 이유로 FAILED다.

- 실제 `/World/Robot`은 Xform이지만 그 상위 `/World`는 typeName이 빈 defined nonphysical prim이다. 현재 strict static oracle는 Xform/Scope만 수용한다. 원 관측의 identity matrix·무질량·시간 샘플0은 보존한다.
- 첫 제어 행에서 엔진 시간은 이미 0.033333333초, Lab step0이다. J2는 q=0.012562919rad, qd=0.525834382rad/s다. 첫 FF 명령보다 `sim.reset()`의 물리 진행이 먼저다.
- 2초 끝 J2 오차는 0.010523543rad(약0.603도), 속도0.017964980rad/s(약1.029도/초)로 기존0.5도·1도/초를 넘었다.
- 초기 구간의 속도 기준 위반5건은 J2 두 건, J5·J6·KG1_slide_A 각 한 건이다. 실제 LINK 자세와 원 AABB를 대조한 그리퍼 바닥 여유는 첫 행11.282mm, step3에서2.656mm, 최소 약−0.000146mm다. native contact-force는 수집하지 않았으므로 충격의 전체 원인을 확정하지 않는다.

정본은 `outputs/isaac-workspace-v1/`의 원 run 두 개, `capture-diagnostic-verification.json`, `floor-proxy-diagnostic.json`이다. 정지 영상2.1초는 FAIL 자료다. 52초 큰 동작은 미실행이다.

## 근거와 불확실성

실제 실행의 SHA와 일치하는 `outputs/isaac-physics-v1/evidence/sdk-source/lab_physx_manager.py` 1017·1049행은 뷰 생성 중 양의 physics dt를 두 번 진행한다. 580~585행의 play/app.update는 추가 진행 후보지만 나머지 시간을 해당 호출로 확정할 이벤트 기록이 없다. 기본 SDK warm_start 콜백은 꺼져 있다.

Lab PRE/POST_PHYSICS_STEP 콜백은 `_view_created`가 true이기 전에는 버려진다(753~756행). 따라서 해당 콜백만 추가하면 초기 누락이 남는다. `set_dof_efforts`는 tensor backend 전용이므로 USD gain/cap 설정만으로 reset 이전 중력 FF가 적용됐다고 할 수 없다.

## 한정 수정안

1. `/World`를 source-owned `UsdGeom.Xform`으로 명시한다. identity·nonphysical·time-invariant 조건을 약화하지 않고 실제 선언과 readback으로 기존 strict oracle를 만족시킨다.
2. 프로젝트 초기화 어댑터와 설치 source SHA 경계를 별도로 둔다. SDK 설치 파일은 수정하지 않는다. 자동 app physics 진행은 `/app/player/playSimulations=False` 상태에서 막는다.
3. 뷰 초기화의 **0시간 진행** 지원을 실제 API와 검증으로 확인한다. 엔진 시간·native step·q/qd가 바뀌거나 지원하지 않으면 `INIT_BOUNDARY_UNSUPPORTED`로 실패한다. 양의 dt fallback을 숨겨 넣지 않는다.
4. Lab의 늦은 callback 대신 raw PhysX pre/post 관측으로 초기화부터 모든 양의 dt를 기록한다. tensor view가 없는 동안의 조회 가능 여부를 그대로 표시한다. 양의 단계에서 상태가 누락되면 `INIT_OBSERVATION_GAP`으로 실패하며 0이나 계획값을 채우지 않는다.
5. 실제 뷰가 준비된 직후 실제 q/qd·질량/COM/관성·중력 FF·잔여 cap·목표를 설정하고 readback한다. 그 후 첫 양의 dt를 진행한다. q/qd reset·teleport·cap/gain/속도 기준 완화는 하지 않는다.
6. 원 gravity−9.81, Kp64/Kd16, cap/속도, 2초 정지 기준과 바닥5mm 기준을 유지한다. 초기화 전 구간까지 통과해야 기존52초 경로를 허가한다. 실패하면 큰 동작은 미실행으로 끝낸다.

0시간 warmup과 모든 초기 상태의 조회가 실제 SDK에서 가능한지는 아직 미확인이다. 이 안은 성공을 보장하지 않는다. API가 지원하지 않으면 새 초기화 방식의 검토가 필요하며, 실패를 기준 완화로 덮지 않는다.

## 실행 제안과 검증

새 유한 단위 M45분을 제안한다. 계획L2·소스L4 각각 최대2회, 실제 import1·init/smoke1·motion1회이며 각600초와 전체45분 중 먼저 도달한 한도를 지킨다. 실패도 소비하고 남은 시간이600초 미만이면 native 실행을 시작하지 않는다. 이 예산은 아직 시작하지 않았다.

HOST는 실제 양의 초기화 단계 누락, 거짓 Lab0, dt0 중 시간/상태 변화, 조회 불가 상태를 0으로 채움, unsupported fallback, World 물리/시간 샘플 오염, 원 cap 변경을 재봉인 음성으로 거절한다. 비작성자 소스 검토 뒤 actual clock·native event·상태·FF·frame proof를 대조한다. 큰 동작은 실제 J1/J6≥100도 p2p, J2 초기 대비≥30도, J3≥40도 p2p, TCP 직경≥0.30m를 만족해야 한다. 실패 영상도 상태를 명시해 보존한다.

실물 보정·모터/CAN·플래시·설치·재부팅·구매·강화학습 실행은 계속 제외한다. 질량·관성 가정과 링 검증 보류도 유지한다. 점군 색의 가시성 보완은 물리 초기화가 통과한 뒤 별도 시각 수정으로 다룬다.
