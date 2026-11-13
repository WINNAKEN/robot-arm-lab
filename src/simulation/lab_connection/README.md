# 048 IsaacLab 최소 runtime 설치 · 정적 모델 연결

> 최종 처분: **BLOCK / EXHAUSTED, 이 진입점으로 module/native를 실행하지 않는다.** L4 R1의 재봉인된 프레임 변조 수용과 `setup/__init__.py` 선실행 반례를 수용했다. physical-frame accepted3, provenance accepted4의 소진 이력과 두 미폐쇄 지적을 유지한다. 아래 명령은 당시 설계 기록이며 운영 절차가 아니다. 제한된 target-prefix 설치 사실만 별도로 수용했으며, 안전한 연결 작업은 별도 검토된 049 격리 커널에서 이어간다.

047 두 수치 시험은0/28로 실패했고, 기존 per-item manifest 시작 검증 방식은 provenance accepted3/EXHAUSTED로 종결했다. 여기서는 그 worker를 재사용하지 않는다. Host가 고정한 setup/job SHA를 격리Python 표준 라이브러리 root에서 먼저 검사하고, 고정된 전체 payload 집합과 바이트 검증을 마친 뒤에만 프로젝트 코드를 실행한다. 설치prefix도 전체 파일 seal을 별도로 확인한다.

기존 IsaacSim6.2RC/bundledPython을 보존하며 새GUID의 packages/에만 `pip --target`으로 최소PhysX 연결용 라이브러리를 설치한다. 공식 aggregateLab3.0.0 wheel은SHA고정/`--no-deps`,선정runtime 의존성만별도로설치한다. 다른USD provider/새Sim/Newton/OV/teleop·드라이버·서비스·보안변경없음. 전체Lab extra/모든backend 설치가 아니다. 원격 설치는 사용자 이번 요청 범위이며 실제모터/보정/CAN/플래시/구매·PPO학습은포함하지않는다.

```powershell
py -B -m unittest src.simulation.lab_connection.test_connection -v
py -B src/simulation/lab_connection/setup.py prepare
py -B src/simulation/lab_connection/setup.py launch-install --run-dir <출력된 새run>
py -B src/simulation/lab_connection/setup.py launch-modules --run-dir <같은run>
py -B src/simulation/lab_connection/setup.py launch-native --run-dir <같은run>
```

module/GPU 단계는 실제TorchCUDA13 tensor연산·moduleversion/provider를 확인한다. native 단계는 실제LabSimulationContext/PhysX manager와7LINK/6관절/양쪽joint localframe·COM/관성·7collider·CAD표시0·SI/Z-up을 원래USD와 대조한다. 현재047이실패이므로 **gravity0, reset/step/목표전송없음인정적연결만**이다. Lab DirectRLEnv 등록/044Gym backend 연결/중력 동작 통과나 학습 완료로 표현하지 않는다.

전송이끊기면단계를재실행하지않고이미기록된reports를회수해verify 역할로판정한다. 최종단계별수용은출력 current/delivery와검토서에서확인한다. prefix/모듈/GPU가통과해도native정적연결실패라면전체연결완료로표시하지않는다. 물성은계속가정이고실물authorityfalse/weightsnull/링보류다.

연구용release/3.0.0 source commit과실제설치aggregatewheel은서로다른버전표면으로보존한다. 설치·native 결과는실제모듈/provider/원자료/PID/childexit에따르며공식GA compatibility표가설치RC실행을보장하지않는다. 보호.dev/기존예산/047미폐쇄지적과EXHAUSTED이력은바꾸지않는다.
