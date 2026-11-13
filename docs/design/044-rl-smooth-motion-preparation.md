> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 044 — 관절 동작 프로그램과 강화학습 준비

2026-10-28 사용자: 완성 후 자연스럽게 움직이도록 강화학습을 준비하고, 현재 대략값 기준 프로그램도 추가 준비. 현재043의 중력·충돌 actual result는 DYNAMICS_FAILED(정착오차3.75185°/속도7.79702°/s,0/28)다. 이를 수리·재분류하거나 새 학습으로 가리지 않는다.

## 범위와 경계

이번은 오프라인 코드/학습 준비다. Isaac/IsaacLab 새 물리 실행·정책 학습·설치·다운로드·GPU 장시간 작업·실물/CAN/플래시/보정/구매 없음. 질량/관성/기계한계/토크/마찰 가정과 링 보류 유지. CAD/041~043/펌웨어는 읽기전용. 현재 원격 기존 python.bat에서 find_spec: numpy=True, torch/gymnasium/isaaclab/rsl_rl/skrl/SB3=False, 확인한 일반IsaacLab root 없음. 이는 해당 Python 모듈 조회 범위 사실이며 전 PC 미설치 단정은 아니다. python 인자 quoting실패1건과 raw Python(noPYTHONPATH) 조회는 구분하고 성공한python.bat 결과만 환경 사실로 사용한다.

공식6.2 compatibility표는 IsaacLab v3.0.0-GA를 기재하지만 설치된 것은6.2 RC다. native Lab 호환/연결은 NOT_RUN이다. 준비물은 library-agnostic MDP core와 선택적 Gymnasium wrapper/IsaacLab 연결 계약, PPO 후보 설정이다. 설치되지 않은 native 환경을 연동 완료로 표현하지 않는다. 기존 physical controller가 기준을 통과하고 native simulator bridge가 검증되기 전에는 학습 readiness가 BLOCKED여야 한다.

소유 `src/simulation/rl_prep/`, `outputs/rl-prep-v1/`, 이 계획. M급 단일준비파이프라인10파일: profile.py, trajectory.py, task.py, isaaclab_adapter.py, policy_io.py, prepare.py, task_config.json, test_prep.py, README.md +계획. 새 working agent 생성/병렬 구현 없음. AGENTS→DEV_PRINCIPLES가 요구하는 기존 비작성자 L2/L4로 검토, 각각max2. 외부 bridge는043에서hook에차단됐으며 이번재호출/우회없음, 동일계열검토 잔여명시. 보호.dev쓰기를우회하지않고도메인결과에인계. 기존 frame/provenance accepted2/다음추가1 EXHAUSTED 및 모든 옛 이력/예산 유지.

## 프로필과 실제 값 구분

043 delivery/validation/tracking진단/040assumptions를 승인 SHA로 고정해 읽는다. 기존 CAD 표시 delta rad/J1..J6, USD hash, 가정mass/COM/inertia와effort cap[3,6,5,2,2,1]Nm·원래가정속도.5rad/s를 보존한다. 관측된 실패오차/속도는 reference 추종 PASS나 물성 보정값이 아니다. 초기분포 후보는 관측 margin을 반올림해 ±4°/±8°/s로 두되 **가정·미검증 학습분포**로 구분한다. 새 reference 명령 제한도제안값: qcmd±10°/증분≤2°/v≤.2rad/s/a≤.5rad/s²/jerk≤2rad/s³. 실물 안전한계라고 표현하지 않는다. 원래.5°/1°/s 성공기준은 유지한다.

## 부드러운 기본 프로그램

6축 rest-to-rest quintic reference를120Hz로 만든다. duration은각축변위에 대해 `T≥1.875|dq|/vmax`, `T≥sqrt((10/sqrt(3))|dq|/amax)`, `T≥cbrt(60|dq|/jmax)`를 모두 만족하도록 dt 정수배로 늘린다. 위치/속도/가속도/jerk를 해석적으로 출력, 시작·끝 v/a=0, 추가0.5s hold. A/B/표시0으로 가는 reference JSON/CSV와 실제 SDK로 보내지 않는 simulation-only 요청 구조를 준비한다. 새 reference 생성은 actual 실행이나 trained policy가 아니다.

## MDP와 자연스러움

1차학습은 TCP/그리퍼가 없는 **관절 목표 도달**이다. 정책은6개의정규화 action[-1,1]로현재 reference q에축별최대2° 증분을 선택한다. 각결정은고정2초(1.5초 quintic+0.5초 hold/240physics ticks), 중간에 action을바꾸지않아 jerk clamp모순·불연속 reference재시작을피한다. 1차는정지형부드러운동작이며 연속 waypoint blend/실물sim2real 성능은미검증이다. PPO discount는이 고정 decision 시간에대응한다.

Observation41: q6,qd6,estimatedqdd6,goalerror6,qcmd6,previousaction6,gravitydir3,episodeprogress1,unexpectedcontact1. SI canonical좌표와정규화scale·clipping을계약에명시하고 실제 reward/평가에는unclipped값을사용한다. 16decision(32sim seconds)유한episode, seeded reset. 목표±5°, 초기분포후보가정. native backend는동일CAD/제어프로필·gravity/collision·actual joint/contact/time 관측 계약이필요하다.

보상은목표오차감소/정확도, 실제 qd/qdd/jerk 비용, action변화비용·시간비용, 충돌/한계패널티. actual history에서 최종연속0.5초 동안모든축goalerror≤0.5°·qd≤1°/s·contact0일때만 success. fault(충돌/actualq±15°학습범위/actualqd원래.5rad/s) 우선, goal보상으로 덮지않는다. timeout truncated와fault/success terminated구분. stale/nonfinite/누락·길이/시간잘못된 backend trace는예외/새reset필수, reward0/성공으로바꾸지않는다.

Host mock은analyticalreference를그대로따르는 **HOST_KINEMATIC_CONTRACT_TEST**이며 실제Isaac/학습/정책성공증거가아니다. 이 mock으로reset→action→reference→actual-like trace shape→reward→termination과seed를검증하고명확히label한다. 원043 replay는별도기존실패를그대로재평가해 학습gate가거짓PASS를주지않는지확인한다.

## 학습·정책·배포 게이트

준비CLI는build/smoke/check-training만 제공한다. 실제PPO launcher/optimizer/weights를시작하지않는다. 후보PPO 설정(예: actor/critic128×128, lr3e−4,clip.2,gamma.97,GAE.95,rollout32/minibatch4/epochs5,numenvs1)은 profile/가정으로라벨하고native학습수용아님. 버전별실제IsaacLab/RSL API 연결은설치/bridge검증후별도다.

Gym wrapper를training=True로만들려면원본baseline동작PASS·정착수치·model/control fingerprint·조건일치와native backend 검증이모두필요하다. 사용자가편집한profile의 ready=True만으로043실패를우회할수없다. 현재원본은고정DYNFAIL이므로항상BLOCKED. mock backend는training gate에서거절. 정책manifest는CAD/제어/profilehash·41/6차원·단위·sim-only/physicalfalse와weights hash를검증하며준비단계는UNTRAINED/weightsnull로내보낸다. torch pickle나임의코드실행/장치권한부여없음. 실물 CAN/모터부호/감속비/영점미승인그대로.

## 수용과 전달

meaningful host checks: quintic극값/유한차분/knots/제로변위/시간단위·범위, strict수치/schema, actionclip과qcmd bounds, seed/41dim, reward목표/정지악용·jerk비용·fault우선·0.5s success hold, timeout구분/stale trace·state reset, 원043DYNFAIL gate/profile변조/mock훈련거절, policy manifest권한/hash변형. build는입력/코드/confighash결속·BUILDING→READY_PREPARATION_ONLY 또는FAILED, 새GUID/write-once/재검증. 호스트smoke·reference export·학습차단을모두검증하고 source 유지/로컬commit한다. 기존학습/실물성능수용으로확대하지않는다.

공식근거: https://isaac-sim.github.io/IsaacLab/main/source/concepts/task_workflows.html · https://isaac-sim.github.io/IsaacLab/main/source/concepts/reinforcement_learning.html · https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/compatibility.html . 열람2026-10-28,main문서는가변이라native실행검증대체아님.
