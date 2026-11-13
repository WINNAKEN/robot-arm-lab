# 042 — 6축 일반 동작 준비와 실제 PhysX 관측

CAD v2의 표시 자세를 q=0으로 하는 유한 시뮬레이션 전용 코드다. 실제 모터 영점·보정·CAN·플래시·설치·구매·강화학습 실행을 포함하지 않는다. 질량·COM·관성·토크·관절 한계는 가정이며 링 형상 검증은 보류다. 실제 runtime 수용은 해당 run의 `validation.json`과 별도 독립 검토로 판단한다. 호스트 합성 시험 통과만으로 runtime 완료를 표시하지 않는다.

`program.json`의 정본 좌표는 J1..J6 순서의 CAD 표시 자세 대비 delta rad다. `core.py`가 120Hz·56.5초의 quintic 위치/해석적 속도 목표를 만든다. 초기0 유지 → 각 축 +5°/0/−5°/0 → 작은 동시 동작 A/B → 최종0의 28 checkpoint이며 무한 반복하지 않는다. 가정 속도 상한은 0.5rad/s, force drive cap은 `[3,6,5,2,2,1]Nm`다. 가정 gain은 원본 관측의 COM·주축·평행축으로 구한 downstream Ieff에서 K=64Ieff, D=16Ieff를 계산한다.

## 파일과 실행 경계

- `core.py`, `program.json`: Isaac 의존성 없는 recipe·보간·가정 gain 계산.
- `runtime.py prepare`: 원본041 USD와 현재 입력을 새 GUID bundle로 보존한다.
- `runtime.py supervise/worker`: 기존 `isaacpc` 설치만 사용하며 실제 자기 자식 PID·exit·로그를 기록한다. 생성된 작업 사본의 PhysX CPU, 중력0, collider7개 비활성, 고정 Base에서 drive 목표를 보낸다.
- `verify.py`: 시뮬레이터를 실행하지 않는 원자료 소비자다. 명시한 `--root`의 현재 source와 원래 `prepared.json`을 대조한다. 결과는 기본적으로 `<run-dir>/validation.json`에 저장한다.
- `driver.ps1`: 준비·전송·명시된 유한 원격 실행·회수·검증을 연결한다. 계획042의 author max3/각600초 예산과 기존 Kit 프로세스 검사 경계를 지킨다. 승인된 실행 예산 밖 자동 재시도는 없다.
- `test_motion.py`: 호스트 수학·실패 경계 시험. 실제 Isaac dynamics 수용과 구분한다.

호스트 시험:

```powershell
py -B -m unittest discover -s src/simulation/motion -p test_motion.py -v
```

이미 회수한 원자료만 재검증:

```powershell
py -B src/simulation/motion/verify.py --run-dir outputs/isaac-motion-v1/runs/<GUID>/retrieved/<GUID> --root C:/projects/robot-arm-lab
```

준비 bundle만 만들려면 `pwsh -File src/simulation/motion/driver.ps1 -PrepareOnly`를 쓴다. `-PrepareOnly` 없이 실행하면 실제 원격 실행을 예약하므로 계획042와 남은 예산을 먼저 확인한다. 위 재검증 명령은 runtime을 새로 실행하지 않는다.

## 관측과 수용

timeline play/update는 초기화에만 사용한다. pause/update로 paused 상태를 확정한 뒤 실제 physics baseline을 잡는다. 루프는 `SimulationManager.step(1)`만 물리 진행을 소유하며 `app.update()`를 섞지 않는다. 강제 tensor backend에서 q/qd와 같은 단계의7 LINK 원점 pose를 읽고, 조회 전후 step 불변을 검사한다. schedule time·실제 physics time·POST_STEP callback dt/count를 별도 기록한다. wall-clock 실시간 보장은 아니다.

`static.json`에는 실제 source USD/root·단위·joint 양쪽 frame·collider local basis(크기 포함)·post-init runtime mass/COM/full inertia·실제 drive gain/cap/type을 기록한다. LINK pose는 월드 body-prim 원점이다. runtime COM/주축 quaternion은 LINK local이며 wxyz다. full inertia는 COM 기준 LINK축 표현이고 원 API의 flat9는 column-major다. USD 주관성 tensor를 회전해 대조하며 quaternion의 ±부호는 회전행렬로 동등하게 처리한다.

`samples.ndjson`의 6781개 기록 전체에서 실제 q 기반 FK↔실제 LINK pose, fixed/revolute 양쪽 anchor·회전 closure와 signed axis를 검사한다. target↔actual tracking은 별도 checkpoint 판정이다. q≠0 closure는 `Rframe0 Rot(axis,qactual)=Rframe1`이다. 정착 endpoint 오차≤0.5°, 속도≤1°/s, LINK/anchor≤1mm, 회전행렬/축≤1e−3를 요구한다. 모든 실제 physics 증분은 1회 및1/120초±1e−6초다. engine double 시계는 `index/120`±1e−6초, callback 누적은 `index*float32(1/120)`±1e−9초, 각 callback 증분은 `float32(1/120)`±1e−9초로 따로 검사한다. 설치6.2의 POST_STEP dt가 float32이므로 6780회 뒤 두 표현에는 약2.947µs 차이가 생긴다. 이것을 실제 물리 시간 지연으로 판정하거나 누적 수용치를 넓히지 않는다. 두 counter는 매 단계 정확히1 증가해야 한다. 최종0/저속은 STOP/reset 전 기록이어야 한다.

질량1e−5kg·COM1e−5m·inertia tensor1e−7kg m²는 source float32 보존 허용이다. 실제 drive readback은 의도한 SI 값에 abs1e−7+rel1e−5 허용을 적용한다. 단위·축·collider disabled·관측 inventory는 별도 정확 검사다. `summary.json`·실제 supervisor/native PID/exit0·원본 준비 앵커·전체 source/input/output 해시가 함께 맞아야 `ACTUAL_PHYSX_GENERAL_MOTION_VERIFIED`가 된다. 종료는 CLOSED/APP_CLOSED 또는 공식 fast shutdown의 DATA_CAPTURED/CLOSING_APP 두 경로만 받는다. 후자는 해시에 결속된 runtime의 `OFFICIAL_FAST_SHUTDOWN_EXPLICIT_EXIT` 표시와 같은 worker PID·실제 exit0를 반드시 요구하며, 원자료를 CLOSED로 고쳐 쓰지 않는다. 보고서의 `completion_evidence`로 두 경로를 구분한다. 종료 후 반환하지 않는 공식 fast shutdown에서 후속 파일 쓰기에 의존하지 않는다. 일반 CLOSED 경로는 capture≤closed≤실제 exit 순서도 검사한다. 두 경로 모두600초 기한을 유지한다. 파일 누락·입력 변경·FAILED·timeout124·일반 exit0만 있는 미완료·일부 checkpoint로는 수용하지 않는다.

`compare_samples()`의 `HOST_DATA_CHECKS_ONLY`는 수학 소비 경계만 통과했다는 뜻이다. 일관되게 구성한 합성 trace 자체로 실제 물리 실행을 증명할 수 없으므로 최종 `verify_run()`의 실행/해시 결속과 독립 검토를 생략하지 않는다. telemetry replay를 만들더라도 실제 관측 재생으로 표시하고 Isaac 렌더나 RL 학습 결과로 표현하지 않는다.

## 3D 재생과 짧은 영상

검증된 원자료로 로컬 WebGL 재생 화면과 12초 MP4를 만든다. 실제 기록의 LINK 위치·자세만 사용하며 Isaac 화면 직접 녹화와 구분한다. 영상은 전체56.5초를 약4.7배속으로 재생한다.

```powershell
py -B -X utf8 src/simulation/motion/replay.py --run-dir outputs/isaac-motion-v1/runs/<GUID>/retrieved/<GUID> --video
```

기본 출력은 `outputs/isaac-motion-v1/viewer/actual-telemetry-replay.mp4`와 `index.html`이다. HTML은 같은 디렉터리의 `geometry.bin`·`telemetry.json`을 함께 제공하는 로컬 HTTP 서버에서 연다. 기존 ffmpeg·numpy·Pillow를 사용하며 설치는 하지 않는다. `--allow-invalid`는 명확한 실패 자료 진단용이고 전체 수용을 뜻하지 않는다. 영상/원자료/STL의 결속은 `replay-manifest.json`에 저장한다.
