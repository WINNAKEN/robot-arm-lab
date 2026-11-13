# 050 SDK/Lab 연결 경계

> 최종 처분: **BLOCK / EXHAUSTED, 아래 명령은 당시 절차 기록이며 재실행하지 않는다.** 050 L4 R1에서 실제 contact mapping의 생산·검증 누락과 두번째 실행의 허용 사유 미검사를 수용했다. physical-frame accepted4 / provenance accepted5 EXHAUSTED를 유지하고 같은 단위의 R2 수리출하·native2는 동결한다. 로컬 모듈 검색 반례와 exit 전파 수리는 host 대조를 통과했으며 실제 SDK 실패도 worker1/child1/최종명령1로 전달됐다. SDK bootstrap·GPU·SimulationApp 생성에는 도달했지만 확장 모듈 DLL/import 오류로 Lab context/모델/물리 step에는 미도달했다. 최종 범위와 원자료는 `outputs/isaac-boundary-v2/HANDOFF.md`를 따른다.

공개 명령은 모두 아래 PowerShell front door를 쓴다. Python 파일을 직접 실행하거나 프로젝트 모듈을 import하는 실행 방법은 지원하지 않는다. host/test/prepare/native/verify와 원격 export는 모두 `Python -I -B -c`의 고정 바이트 진입점이다. host consumer는 stdlib만 사용한다.

```powershell
& ./src/simulation/sdk_boundary/launch.ps1 -Role test
& ./src/simulation/sdk_boundary/launch.ps1 -Role prepare
& ./src/simulation/sdk_boundary/launch.ps1 -Role native -RunDir <새 run의 절대 경로>
& ./src/simulation/sdk_boundary/launch.ps1 -Role verify -RunDir <같은 run의 절대 경로>
```

native는 검증한 공식 SDK sitecustomize를 명시 실행하고 전용 prefix를 봉인 대조한 뒤 실제 SimulationApp/Lab PhysX를 연결한다. 원본 v2 모델의 완전한 frame·가정 물성 대조와 중력0/무명령10스텝/11관측을 검증한다. 이것은 중력 정착 성공이나 실물 영점 보정이 아니다. 정책학습·DirectRLEnv 등록·실물 보정/모터/CAN/플래시·구매·링검증은 하지 않는다.

실제 worker 코드→SystemExit→supervisor/SSH/front door의 종료코드를 보존한다. close 이전 terminal과 실제 child 종료가 모두 정상이며 원본과 모든 관측이 대조돼야 연결을 수용한다. incomplete/FAILED/nonzero/timeout은 성공으로 바꾸지 않는다.

050 native는 전역 원장 최대2회/각600초이며 실패도 소비한다. 두번째는 측정된 SDK/API 수집 오류의 최소 수정 확인만 가능하고 성공 반복은 없다. 이미 실행된 run을 다시 실행하지 않는다. 전송 오류면 기존 원자료만 회수한다. 최종 상태는 `outputs/isaac-boundary-v2/delivery.json`과 독립 검토 기록을 따른다. 기존047/048/049와 provenance5/frame3 EXHAUSTED 이력은 그대로 유지하며 이 파일의 존재는 실행/수용을 뜻하지 않는다.
