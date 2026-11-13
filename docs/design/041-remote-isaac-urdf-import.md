> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 041 — 원격 Isaac Sim 가져오기와 CAD 축·표시 0 검증

2026-10-27 사용자 지시: 다른 연결 노트북의 Isaac 환경 확인 → 기존 URDF 가져오기 → 관절축·0도 자세를 CAD와 대조. 질량·관성은 가정으로 유지하고 실물 보정·모터 운전 제외, 링 보류. 이번 새 단위 L2 최대2/L4 최대2. 종결된040 예산/판정·원본 및 기존 startup/SB/025/firmware/PA/terminal 소진/임계·039 실시간 BLOCK을 다시 열지 않는다.

## 현재 확인과 권한

기존 SSH 별칭 `isaacpc`로 실제 키 인증 exit0·remote user robot-user을 확인했다. 대상 `C:/isaacsim`, 버전6.2.0-rc.14+release.52805.02189a84.gl, RTX3500Ada Laptop 12282MiB/driver596.71, 여유324.3GB. 현재 Kit 프로세스 없음. 과거 기억을 접속 단서로만 쓰고 현재 설치 파일/API를 읽었다. 설치 importer3.11.12는 동기 `URDFImporter(URDFImporterConfig(...)).import_urdf()->str`이다. 공식 문서 확인일2026-10-27.

현재 공식 요구사양표의 VRAM16GB보다 작으므로 전체 환경 적합/대규모 RL 성능을 인증하지 않는다. 작은 단일 자산의 실제 import 성공 여부를 따로 측정하며 환경 실패를 관절 불일치로 판정하지 않는다. 드라이버/앱/확장 설치·업그레이드·SSH/방화벽/네트워크 설정 수정 없음.

## 소유와 입력

- 새 코드 `src/simulation/isaac_import/`, 증거 `.dev/isaac-import-evidence/`, 결과 `outputs/isaac-import-v1/`, 이 계획과 최소 인계 문서.
- 원격 새 경로 `C:/isaacsim_remote/robot-arm-lab/041/runs/<runid>/`에 패키지/스크립트/로그/USD/상태를 분리한다. 기존 app/streaming task·다른 장면·사용자 파일은 보존한다. background helper를 쓰면 Hidden, PID/소유 경로 기록, 자기 작업만 종료 가능하다.
- 기존040 최종 `models/robot-arm-urdf-v1/`(manifest d82f530e…b4c)·URDF/STL/가정/provenance, 고정 v2 native c784ee45…f84bc1·021 core/kin이 읽기 전용 정본이다. MP7 v3 외형·원본CAD·펌웨어를 고치지 않는다. v3 완성은 이번 v2 패키지의 자동 교체 근거가 아니다.
- 로컬/전송/원격 입력 해시를 대조한다. source/manifest/remote script 해시·설치 version/API/config·actual stdout/stderr/exit·출력 USD와 dependency 목록을 보존한다. 원격 출력 성공 문자열만 수용하지 않는다.

## 실행 경계

별도 standalone headless `SimulationApp`를 설치 runtime으로 시작한 뒤 importer를 활성화한다. 기존 Kit/다른 세션이 생겼으면 무작정 kill/restart하지 않는다. 새 작업의 중앙 상태를 입력/runtime 의존성보다 먼저 BUILDING, 일반 오류는 FAILED/예외+nonzero로 기록한다. 불가 저장소/강제종료는 보장 밖이며 외부 launcher의 PID/exit/로그 상태로 불완료를 식별한다. stale 결과/예전 USD를 새 성공으로 재사용하지 않는다.

지원되는 config를 실제 설치 소스대로 사용한다: merge_mesh=False, merge_fixed_joints=False, collision_from_visuals=False, allow_self_collision=False, fix_base=True, link_density=None, joint drive/target/stiffness/damping override=None. run_asset_transformer=False·run_multi_physics_conversion=False로 raw native USD를 보존하여 이번 좌표 검증에 불필요한 재구성/다중물리 변환을 제외한다. 이 선택은 실행된 import 경로/결과에 명시한다. 기본 또는 source DriveAPI가 없다고 단정하지 않는다.

timeline은 STOPPED를 확인하고 play/physics step/관절 목표 또는 실제 장치를 호출하지 않는다. 실제 URDF importer가 디스크에 저장한 반환 USD를 다시 열어 active stage로 확인한다. plugin 저장/로드·정적 frame 측정의 update는 허용하지만 동역학이나 실제 관절 움직임 검증으로 세지 않는다. 선택적 미리보기는 실제 USD 데이터 또는 실제 renderer인지 구분한다.

설치 python.bat는 `kit/python/kit.exe`가 없으면 python.exe를 복사하는 분기가 있다. 실행 전에 해당 파일 존재를 확인하고, 없으면 설치 트리를 바꾸지 않도록 child process에만 공식 PYTHONEXE override로 기존 python.exe를 지정한다. 공유 환경/설치 파일 변경 또는 이를 설치 승인으로 확대하지 않는다.

작성자 실제 import 최대2시도(최초+관측된 실행환경/API 문제의 수리1회), 각 시작/실행 기한600초. 무조건 반복/설치/허용오차 완화로 PASS 만들지 않는다. 최초 실패 raw/PID/종료/불완료를 보존한다. 독립 검토는 저장된 실제 USD의 별도 읽기 검사에 최대1회 runtime 세션을 사용할 수 있고 import·제품 재생성은 하지 않는다.

## 정적 가져오기 수용 기준

정본 기대값은 원래 URDF·고정021 FK에서 로컬에 계산한다. 원격 importer/extractor에는 이 기대값을 주입하지 않는다. extractor는 실제 저장 USD의 attributes/transforms/mesh만 내보내고 판정은 별도로 수행한다. source 해시·실제 USD·raw 관측 없는 PASS 금지.

1. importer 성공, 출력 USD 파일 존재·의존성 해소, 실제 설치/실행 정보와 기록 상태 일치. 새출력 write-once, source와 output 경로 분리.
2. Base+Link1..6의7개 rigid links와 J1..6의6개 revolute가 실제 body0/body1 관계에 모호함 없이 대응한다. fixed-base용 world joint는 회전 DOF에서 제외한다.
3. metersPerUnit 및 독립 질량 metric kilogramsPerUnit의 authored/resolved 값·기본값 사용 여부, up-axis/root placement를 실제로 기록한다. OpenUSD 미작성 기본값은 MPU=0.01·kGPU=1로 다르므로 두 metric의 공식 resolver를 사용하고 수동으로 모두1을 대입하지 않는다. 이번 지원은 resolved metersPerUnit=1 및 kilogramsPerUnit=1·Z-up/identity로 제한하며 비교 전에 단위 gate를 적용한다. 다른 단위는 조용히 같은 SI 숫자로 비교하지 않고 명시적 미지원/실패로 기록한다. 일반 SI 변환은 질량에 kGPU, 위치에 MPU, 관성에 kGPU*MPU²가 필요하지만 이번에 임의 변환/보정을 추가하지 않는다. best-fit 정렬/링크별 임의 보정으로 차이를 숨기지 않는다.
4. actual world link transforms, joint body0/body1+localPos0/1+localRot0/1+axis enum에서 세계 anchor/부호 있는 회전축을 복원한다. 두 side anchor와 zero joint-frame closure를 검사하며 raw X/Y/Z enum만 URDF axis와 직접 대조하지 않는다. quaternion은 명시적 API 순서와 회전행렬로 변환한다.
5. URDF q0=CAD 표시 기하각[15,-50,70,15,25,-10]deg인 delta0이다. link/관절 세계 원점·회전·양의 축을 고정021/URDF와 대조한다. 사전 수용 한계: 위치 성분1e-5m, 회전행렬/정규화 축 성분1e-5. USD float 저장 경로용이며040의 정적1e-10과 다르고 실물 공차가 아니다. 부호를 abs(dot)로 없애지 않는다. 실제 visual mesh의 link별 world bounds도 source STL q0 bounds와1e-5m로 비교해 외형 배치를 확인한다.
6. mass/COM/관성은 여전히 SIMULATION_ASSUMPTION이다. 실제 USD MassAPI mass·COM·principalAxes/diagonalInertia를 읽고 링크 frame/world tensor로 복원해 입력 가정과 대조한다(질량1e-6kg, COM1e-5m, tensor1e-8kg m²). 대각 주축 재정렬은 허용하되 물리적 tensor 동일성을 검사하며 자동 density 재계산으로 채우지 않는다. 이 PASS는 물성 정확도 인증이 아니다.
7. 상충 값을 가진 copied 관측의 축 부호/원점/단위/0자세/질량 또는 관성 및 누락/중복 joint를 거절하는 검사와 실제 원본 전후 양성을 확인한다. kGPU=.001이고 raw mass/tensor 숫자는 원본과 같은 관측을 mass 비교보다 앞선 단위 gate에서 거절하며, 원래1m/1kg 양성과 짝을 이룬다. missing input/runtime 오류도 새 성공으로 게시하지 않는다. mutation/합성 증거와 actual USD 관측을 구분한다.

동역학 play·실제 articulation state readback·±5deg 구동·중력/접촉/충돌 안정성·gains/학습·CAN·실물 보정/모터는 NOT_RUN. 링 치형/형상 검증은 보류. 수용 명칭은 IMPORTED_USD_STATIC_FRAME_ALIGNMENT이며 실제 물리엔진 운동이나 모터 방향 수용이 아니다.

## 검토와 종료

L2 → 구현/실제 가져오기/필요 검사 → 비작성자 L4. 최종 reviewer는 실제 USD/source·raw 관측/계산·미정 물성·전송/실패/원본 보존을 독립 대조한다. L4의 별도 local/remote read 결과와 작성자 계산을 구분한다. 지적 합집합과 유한 예산/소진 판정을 보존하고 범위 밖 설치·새 반복은 하지 않는다. 완료 시 USD 묶음/실행 안내·정확한 실패/미수행을 전달하고 HANDOFF/SESSION/BACKLOG/LESSONS/구조를 갱신, 소유 범위 로컬 commit/push 없음.

공식 참고: https://docs.isaacsim.omniverse.nvidia.com/latest/importer_exporter/import_urdf.html · https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html . 설치 RC의 실제 config/source가 API 선택의 우선 근거다.
