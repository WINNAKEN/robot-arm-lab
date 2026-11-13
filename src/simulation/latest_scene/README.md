# 069B 최신 팔·개폐 그리퍼 물리 시험 / native RTX 촬영

계획 정본은 `docs/design/069-latest-gripper-isaac.md`이다. `program.json`의 22초·120 Hz·2640스텝을 실제 Isaac Lab 단일 CPU context에서 실행하고, 8스텝마다 같은 물리 상태를 native Replicator RGBA PNG로 기록한다(0을 포함한 331장·15 fps). 설치·SSH·실행 예약·앱 수명·전송·독립 수용은 069A의 driver/sdk/validate가 소유한다. 이 모듈을 직접 실행하여 SDK를 시작하지 않는다.

`scene.run(ctx)`는 검증된 입력 바이트에서 sdk/validate/capture 모듈을 불러 `sdk.lifecycle(ctx, simulate)`를 호출한다. `simulate(ctx, app)`는 원 canonical 9가동 관절·11물리 body의 실제 경로와 배열 이름을 찾고, reset 이후 single-view binding과 runtime 질량·COM·full inertia를 확인한 뒤 targets/efforts만 보낸다. 초기화 이후 q/qd를 재설정하지 않는다. acceleration drive Kp64/Kd16, 원 URDF effort/velocity/position 한계, gravity OFF19초/ON3초는 모의 모델의 시험 조건이다. 물성·gain은 실물 승인값이 아니다.

중력은 모든 body의 gravity enabled 상태를 유지한 채 실제 simulation view의 전역 벡터를 0에서 -Z9.81로 바꾼다. native gravity query의 전체9/15열과 실제 이름 permutation을 남기고, 실제 pose·runtime mass/COM·canonical 후손 tree로 별도 계산한 9축 값과 1e-3 이내인지 명령 전에 검사한다. feedforward를 원 effort cap에서 뺀 drive cap을 적용하며 음수가 되면 명령을 보내기 전에 유효 부하 FAIL로 정지하고 원자료를 보존한다.

로컬 USD Cube 바닥·Camera·DomeLight를 사용한다. 원11개 AABB proxy의 self collision은 OFF다. 물체 집기·쥠힘·물리 기어 힘결합·충돌 없는 경로·실물 안전성을 검증한 것으로 해석하지 않는다. `tool0`는 canonical 빈 frame이다.

촬영 전 STOPPED timeline에서 warmup을 정확히1회 수행한다. 각 `delta_time=0`, `wait_for_render=True` 호출 전후 RGB/ReferenceTime/PostProcessDispatcher의 Python wrapper identity(`id_kind=PYTHON_WRAPPER`)와 실제 OG node 경로·type·compute_count를 기록한다. wrapper identity는 유지한 Python 객체의 식별자이며 native graph node ID를 관측한 값이 아니다. 새 native 렌더 세대의 근거는 실제 OG node의 compute_count다. 세 count 엄격 증가, scheduled rational time 도달, 같은 render product의 reference time 일치, native engine clock·Lab step·q/qd·11 body pose 불변이 모두 필요하다. render timeout을 재호출로 숨기거나 software/CAD replay로 대체하지 않는다. PNG마다 raw state·target·phase·시간·SHA sidecar를 쓴다. renderer scheduling 실패 로그는 driver에서도 거절한다.

호스트 검증: `test_scene.py`는 SDK import 없이 프로그램/한계·9열 permutation·중력9/15열·별도 gravity 합·원 effort cap·settle·freshness/묵은 RGB/렌더 실패 로그의 고정 이름·개수 대조를 수행한다. 예: 기존 Python으로 `python -I -B src/simulation/latest_scene/test_scene.py`. HOST_PASS는 실제 physics/RTX 실행이나 독립 L4 PASS를 뜻하지 않는다. native 실행은 A의 import 수용과 A/B 독립 L4 이후 driver의 1회 예약을 통해서만 수행한다.

산출: output/report.partial.json(진행 원본), report.json(collector 완료), scene.usda, physics-binding.json, frames/frame-NNNN.png 및 동일 이름 JSON. 중단·증거 오류는 원자료와 firstfault를 보존한다. MP4 인코딩·decode·대표 프레임 육안 확인·Drive 업로드는 상위 orchestration의 별도 완료 조건이다.
