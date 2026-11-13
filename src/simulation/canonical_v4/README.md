# 053 canonical evidence kernel

현재 후보이며 실제 연결 성공은 delivery/독립 검토로 확인한다. 검증 권위는 stdlib kernel 한곳에 있고 SDK operators는 measured data만 반환한다. kernel snapshot의 코드/설정/입력은 불변이며 supervisor는 프로젝트 코드를 재읽거나 실행하지 않는다. 모든 provider path는 canonical 절대경로로 검사한다. 관성 기대값은 고정 source oracle에서만 계산하고 contact matrix는 active scalar force×world normal 합으로 재구성한다.

```powershell
& ./src/simulation/canonical_v4/launch.ps1 -Role test
& ./src/simulation/canonical_v4/launch.ps1 -Role prepare -Stage sdk_preflight
& ./src/simulation/canonical_v4/launch.ps1 -Role run -RunDir <SDK 진단 run 절대경로>
& ./src/simulation/canonical_v4/launch.ps1 -Role prepare -Stage robot_connection
& ./src/simulation/canonical_v4/launch.ps1 -Role run -RunDir <로봇 연결 run 절대경로>
& ./src/simulation/canonical_v4/launch.ps1 -Role verify -RunDir <해당 run 절대경로>
```

SDK NumPy2.3.1/SciPy1.17 우선·SimulationApp 후048 prefix-last·SDK Warp1.17을 사용한다. 각 stage 최대1회이며 실패도 소비하고052 원장의 같은 stage 예약도 누적한다. SDK 진단의 실제 정상자료/같은 input signature가 있어야 robot 단계가 가능하다. 전송 실패 때 반복하지 않는다.

실물 보정/모터/CAN/플래시/구매/학습/링검증/재부팅/재설치는 없다. 질량·관성은 가정, 중력0/무명령10step 연결 시험이다. 이전정착실패와052·기존source동결/EXHAUSTED이력은 변경하지 않는다. 최종정본은 outputs/isaac-canonical-v4/HANDOFF.md와delivery.json이다.
