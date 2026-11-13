# 041 원격 Isaac 가져오기·정적 frame 검사

실제 검증 대상은 040의 v2 URDF이며, 원격 SSH `isaacpc`에 설치된 Isaac6.2.0-rc.14를 사용했다. 질량·COM·관성·충돌·한계는 가정이고 실물/CAN/모터/학습과 연결하지 않는다. 기존040 입력/CAD/core/펌웨어는 수정하지 않는다.

입력 패키지 해시→새 run bundle→전송 해시→기존 runtime의 실제 URDF import→저장 USD를 active stage로 다시 열기→실제 USD attributes/mesh points 관측→로컬 CAD 대조 순서다. 원격 importer에는 기대 좌표를 주입하지 않는다. `remote_config.json`이 승인된 별도 노트북/작업 경로를 명시한다.

재검사(시뮬레이터를 새로 실행하지 않음):

```powershell
py -X utf8 src/simulation/isaac_import/verify_import.py --run-copy outputs/isaac-import-v1/runs/1c559d361bc24e50b90efa1d15518b28/retrieved/1c559d361bc24e50b90efa1d15518b28 --remote-run-dir C:/isaacsim_remote/robot-arm-lab/041/runs/1c559d361bc24e50b90efa1d15518b28 --report .dev/isaac-import-evidence/validation-author.json
```

`prepare.py`는 로컬 bundle만 만들고 `launch_remote.ps1`만 실제 실행한다. **이번 author 실행 예산2/2는 종결**했다. 새 실제 실행을 자동 재시도하지 않는다. 첫 예약은 Windows SSH의 background Start-Process AccessDenied로 Kit 시작 전 실패했다. 두 번째는 SSH foreground + `supervise.py`가 CREATE_NO_WINDOW로 자기 child만 실행하고600초 기한/실제 exit를 기록했다. 설치/보안 설정은 바꾸지 않았고 python.bat의 조건부exe복사는 child PYTHONEXE로 기존exe를 선택해 피했다.

## 완료 상태의 소유권

현재 Isaac의 `SimulationApp.close()` 기본 fast_shutdown=True는 프로세스를 즉시 종료한다. 따라서 실제 성공 시 remote raw `status.json`은 BUILDING/CLOSING_APP에서 멈췄다. 원자료를 EXTRACTED로 고쳐 쓰지 않는다. 최종 권위는 로컬 `verify_import.py`가 쓰는 `.dev/isaac-import-evidence/current.json`이다.

일반 exit0만으로 성공을 인정하지 않는다. 같은 attempt의 실제 process exit0, CLOSING_APP 이후까지 저장된 snapshot 해시, USD 경로/해시, runtime/PID, timeline 전후 STOPPED를 모두 결속하고 실제 저장 USD 대조까지 통과해야 완료다. 이전 phase·FAILED·다른 run·바뀐 snapshot·nonzero는 거절한다. app 생성 후 오류가 생겨 close()가 exit0으로 가려도, 중앙 consumer가 FAILED로 끝내는 host mock의 실제 producer→consumer 시험을 포함했다. 이 host mock은 실제 Isaac 재실행이 아니다.

## 검증 범위

resolved MPU=1/kgPU=1/Z-up/identity root만 지원한다. 미작성 기본값 MPU=.01/kgPU=1은 각각 공식 resolver로 관측한다. 7rigid links/6revolute 및 non-rigid default-root→Base fixed joint를 확인한다. 실제 body/local joint frames로 부호 있는 세계 축과 양쪽 anchor·zero closure를 복원하며 quaternion 부호나 주축 정렬을 숫자 성분으로 오판하지 않는다.

fixed joint도 두 world anchor/rotation의 zero closure를 검사한다. 공통 anchor gauge 변경처럼 의미가 같은 fixed frame 표현은 허용한다. 실제 runtime에 기록된 package/scripts/importer identity는 원래 준비 job·전송 파일·현재 source·설치 preflight와 교차 대조한다. job 자체도 실행 전 `prepared.json` digest에 결속하고040 FK/STL helper는 승인 패키지 provenance 해시에 결속한다.

좌표·visual point bounds1e-5m, 회전/축1e-5, 질량1e-6kg·COM1e-5m·관성tensor1e-8kg m² 허용값은 import 수치 변환용이다. 기계 정밀도나 실측 물성 인증이 아니다. timeline play·±5deg 구동·동역학/접촉·RL·실물 보정/모터 운전 NOT_RUN, 링 보류. 독립 최종 상태는 `.dev/isaac-import-evidence/disposition.md` 참조.
