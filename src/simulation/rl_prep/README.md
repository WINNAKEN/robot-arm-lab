# 6축 부드러운 동작 프로그램 · 강화학습 준비 044

현재 **오프라인 준비본**이다. 실제 학습/정책 가중치/IsaacLab 등록·물리 연결/실물 제어는 NOT_RUN. `HOST_KINEMATIC_CONTRACT_TEST`는 목표 궤적을 그대로 따라가는 수학 모형이며 물리 시험이나 학습 성능을 의미하지 않는다.

## 지금 준비한 프로그램

`prepare.py build`는 새 run 폴더에 profile, 6축 A→B→표시0 reference JSON/CSV, 시뮬레이션 요청 예제, 정책 입출력 계약과 PPO 후보 설정을 저장한다. 좌표는 J1~J6 **CAD 표시 영점 기준 delta rad**다. CSV는 시간+위치6+속도6+가속도6+jerk6, 총25열이다. 원래 CAD 기하각 offset `[15,-50,70,15,25,-10]°`를 모터 영점으로 사용하지 않는다.

기본 경로는 quintic으로 시작·종료 속도/가속도0, 시간은120Hz 간격으로 늘려 v/a/jerk 제한을 만족시킨다. A는 `[5,-5,5,3,-3,3]°`, B는 그 반대, 마지막은 표시0이다. 명령범위±10°, v≤0.2rad/s, a≤0.5rad/s², jerk≤2rad/s³는 **시뮬레이션 제안값**이다. 실물 안전 한계나 확인된 기계 한계가 아니다. 매 구간 끝0.5초 정지형 경로이며 연속 이동 waypoint blending은 후속 과제다.

## 첫 강화학습 과제

관절 목표 도달: 관측41개, action6개. action[-1,1]은 축당 최대2° reference 증분이다. 결정당1.5초 이동+0.5초 hold =2초/240물리 간격, 최대16결정/32초. 보상은 목표 오차 감소와 정확도, 실제 속도·가속도·jerk·action 변화·시간 비용이다. 실제 전 구간의 충돌/범위/속도 위반이 성공보다 우선한다. 마지막61샘플(60간격/0.5초) 모두 오차≤0.5°·속도≤1°/s여야 성공이다. timeout과 종료를 구분한다.

`profile.py`가 원본043 delivery/실측 validation과 source bytes를 결속한다. **043은 DYNAMICS_FAILED: 오차3.75185°/속도7.79702°/s,0/28 통과**이며, 호스트 mock의 성공으로 바꾸지 않는다. 초기분포±4°/±8°/s는 이 실패 관측을 반올림한 가정이다. 질량총합4.15kg·균일박스 관성·COM·토크cap `[3,6,5,2,2,1]Nm`도 실물 미확인 가정이다. 마찰/백래시/감속기 효율/하중은 아직 식별하지 않았다.

## 실행 방법 (프로젝트 루트, Python 표준 라이브러리)

```powershell
py -B -m unittest src.simulation.rl_prep.test_prep -v
py -B src/simulation/rl_prep/prepare.py build
py -B src/simulation/rl_prep/prepare.py verify
py -B src/simulation/rl_prep/prepare.py smoke
py -B src/simulation/rl_prep/prepare.py check-training
```

`check-training`은 차단되면 exit2가 정상이다. 나머지 호스트 검사 정상 종료는0. `current.json`은 BUILDING→READY_PREPARATION_ONLY 또는FAILED이며 실패 시 이전 성공 run으로 대체하지 않는다. 과거 run은 보존한다. 동시 build 실행은 지원하지 않는다. `verify`는 현재 source/config/원본 입력과 산출물 hash를 다시 검사한다.

## 실제 학습으로 넘어갈 조건

1. 기존 중력·충돌 제어의 정착 실패를 별도 수정/검증한다. 이 준비본은 해당 실패를 수리하지 않는다.
2. 사용할 IsaacLab 환경을 확인/설치하고 설치된 IsaacSim RC와의 native 호환을 검증한다. 이번 원격 `python.bat` 모듈 조회에서는 numpy만 보였고 torch/gymnasium/isaaclab/rsl_rl은 보이지 않았다. 해당 Python 조회 범위이며 PC 전체 미설치 단정이 아니다.
3. `isaaclab_adapter.py`의 실제 State/동일시계120Hz trace backend를 연결하고 검증한다. 이 파일은 **계약과 선택적 Gym wrapper**이며 native DirectRLEnv/IsaacLab task 등록 완료본이 아니다. Gym wrapper 실행 자체도 NOT_RUN이다. 현재 native/training 게이트는 차단된다.
4. PPO 후보를 작은 환경에서 별도 수용하고 목표 도달·진동·jerk·충돌·성공률을 평가한다. num_envs1,128×128 네트워크 설정은 미학습 후보이며 실제 trainer API 설정 파일을 대체하지 않는다.
5. 측정한 질량/관성/감속비/마찰/백래시/지연을 반영한 뒤 domain randomization, TCP 경로, 그리퍼·하중으로 확대한다. 지금 가정으로 학습된 정책이 제작 후 자연스럽게 움직인다고 보장하지 않는다.

`policy_io.py`는 profile/model/제어 signature·41/6·SI좌표·weights hash를 검사한다. 현재 UNTRAINED/weights null이다. opaque weights를 읽어 hash만 검사하며 torch pickle 실행/정책 성능 승인/장치 전송을 하지 않는다. 시뮬레이션 reference 요청은 펌웨어/CAN으로 dispatch하지 않는다. 실물 보정·모터 운전·링 검증 보류 조건을 유지한다.

공식 참고(2026-10-28 확인): [IsaacLab task workflows](https://isaac-sim.github.io/IsaacLab/main/source/concepts/task_workflows.html), [RL 안내](https://isaac-sim.github.io/IsaacLab/main/source/concepts/reinforcement_learning.html), [IsaacSim6.2 compatibility](https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/compatibility.html). GA 매칭 표는 설치된 RC의 실제 호환 검증이 아니다.

독립 검토와 인계는 `outputs/rl-prep-v1/`에 기록한다. 외부 계열 bridge는 이전043의 hook 차단 후 이번 호출하지 않았고 동일계열 비작성자 검토의 한계가 남는다. 기존 물리 프레임/실행 의존 결속 accepted2, 다음 동종 수용1 EXHAUSTED와 이전 예산은 초기화하지 않는다.
