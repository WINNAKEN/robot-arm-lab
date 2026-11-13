# 047 중력 정착 수정 시험

**종결: BLOCK / 결속 검증 접근 EXHAUSTED. 두 실제 시험 모두 정착 실패이며 실행예산2/2 종료. 아래 실행 예시는 보존용이고 추가 실행·출하용이 아니다.** L4 R1의 재시험 자격/누락manifest core 실행 결함을 미폐쇄로 남긴다. 마지막 재시험 guard 양성 호스트 대조도 실패했으며 이후 수리를 중단했다. 자세한 처분은 `outputs/isaac-settling-v1/HANDOFF.md`와 `delivery.json`을 따른다.

신규 시뮬레이션 실험이다. 기존043 실패·044 UNTRAINED 준비본·CAD·실물 승인 상태를 바꾸지 않는다. 질량/관성/마찰/토크는 가정이며 링은 보류다.

실행1 `solver`: articulation position64/velocity16 iteration, 기존 K64I/D16I. 실패 시에만 실행2 `solver_pd`: 같은solver+K256I/D32I. 두 설정 모두 총 effort `[3,6,5,2,2,1]Nm`, 중력ff와residualPD cap·원래56.5초 recipe·120Hz·28지점오차≤0.5°/속도≤1°/s를 유지한다. 단일 실행600초, 총2회. 성공 재실행은 하지 않는다. solver 값은 authored USD/static readback이며 별도의 solver 내부 반복 횟수 계측은 아니다. `fresh_unmodified_solver_defaults`는 새 실험 stage의 설정 전 조회이고 과거043 실행의 실제값을 재측정한 것이 아니다.

```powershell
py -B -m unittest src.simulation.settling_recovery.test_recovery -v
pwsh -NoProfile -File src/simulation/settling_recovery/driver.ps1 -Variant solver
```

`pins.json`의 모든 재사용 project helper SHA를 import 전 확인한다. 원격bundle도 job/hash/PID/nativeexit·원자료를 대조한다. 호스트 준비는 실행이 아니다. 합격 전 실제결과를 `outputs/isaac-settling-v1/`에서 확인한다. 기존043 sample 전체에서 첫 tracking실패 뒤에도 모든6781 frame 검사를 이어가며, 잘못된frame·시계는INVALID_EVIDENCE, 유효하지만 정착실패인 결과는DYNAMICS_FAILED로 구분한다. 합격 기준을 완화해 실패를 닫지 않는다.

IsaacLab 설치/연결은 후속048이다. 새 실물/CAN/플래시/학습은 실행하지 않는다. 상세예산·검토·외부계열 fallback한계는 계획047과output delivery/HANDOFF에 보존한다.

L4 R1 지적 후 재시험 gate를 보수적으로 좁혔다. PD 재시험은 실제 첫 원자료를 재검증한 뒤 완전한 정착 실패와 접촉/ff 문제 없음이 확인될 때만 허용한다. 시작/API/증거 실패는 자동 재실행하지 않는다. 실제 두 번째 시험은 수정 전에도 정착0/28·다른 동역학실패없음으로 이 자격을 충족했다.
