> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 073 — 중력 부하·큰 궤적·반투명 작업영역 시험

사용자 요청: “중력으로 인한 저항을 감안하면서 동작을 큼직큼직하게 돌면서 작업가능반경을 반투명으로 구름모양처럼 보여주면서 거길 움직이는 모습을 테스트”. 이는 새 큰 동작/작업영역 실험이며 071의 실패한 작은 동작을 성공으로 재분류하거나 옛 원장을 초기화하지 않는다. 071 import PASS·simulation 초기 설정 실패와 072 PhysX schema 수리 HOST/L4 PASS를 읽기전용 입력으로 유지한다. 실물 보정·모터/CAN·플래시·설치·재부팅·구매·학습은 제외한다. 질량·관성·collision/drive/한계는 가정, 링 검증 보류다.

## 소유·분할·예산

새 소스 `src/simulation/workspace_trial/`, 산출 `outputs/isaac-workspace-v1/`, 원격 `C:/isaacsim_remote/robot-arm-lab/073/runs`. 기존 latest_scene·CAD·URDF16·BOM·firmware·기존 모든 실패/소진/임계는 무수정이다. 새목적은 gravity_workspace_cloud이며 새 프로그램·구름·관측을 시험한다. source는 기존12개(기존11+workspace.py)를 baseline byte와 함께 새 경로에 복사한 뒤 필요한 부분만 바꾼다.

073은 여러 생산 그룹을 가진 L범위이므로 단일45분 작업으로 취급하지 않고 유한 단위로 분할한다. A(root: driver/validate/config/test_host/launch,5파일 M45분), B(다른작성자: scene/capture/program/test_scene/README,5파일 M45분), C(별도작성자: workspace.py,1파일 S25분)를 L2 최종 PASS 후 병렬 시작하며 실제 시작·마감을 원장에 고정한다. 각 source 단위는 작성·기계시험·비작성자 L4를 자기 시간 안에서 끝낸다. 이후 D(실제SDK import/smoke/motion·영상/보관, M검수급45분)를 A/B/C PASS 뒤 별도로 시작한다. 15:17:54부터의 L1/L2 조사 시간을 source 구현 시작으로 소급하지 않으며, source나 D 단위 중간에 캡을 초기화하지 않는다. 전체 추가 상한은 **17:05:00 UTC**이며 모든 단위의 개별 캡보다 우선한다.

12번째 sdk.py는 원071의 최종 바이트를 그대로 복사하며 A의 domain 서명과 보호목록에 포함하고 수정하지 않는다. 새 native는 관련 A/B/C가 모두 PASS여야 시작한다. 공통 L2최대2, L4 A/B각최대2·C최대1, 전체 시간상한 우선. 기존 외부hook거절은 재시도하지 않고 같은계열 비작성자 fallback 한계를 기록한다. 사용자가 이번 새 실험에45분을 지정한 것은 아니며, 직전071의 명시 예산과 이 새 큰 동작·구름 실험을 혼동하지 않는다.

## 작업영역 데이터와 큰 경로

canonical URDF를 직접 파싱한 FK/질량원장/원effort로 결정론 seed7301, **8192개** 관절공간 샘플을 만든다. gripper opening=.04m 고정. cloud 후보는 TCP 좌표뿐 아니라 원 6축 q·전체9축 중력 generalized force·cap비율·nonBase collision8corner의 floor 최소여유를 남긴다. selfcollision proxy는 원래 OFF이며 전체 충돌없는 접근가능성은 인증하지 않는다.

정적 중력 부하/원cap ≤.8이고 nonBase 바닥 여유≥5mm인 실제 샘플만 파란 구름 후보로 삼는다. 25mm voxel마다 실제 첫 witness TCP를 표시하고 모든 voxel과 samplecount를 보존한다. 렌더 표시는 최대1600개의 결정론적 공간분산 선택으로 제한한다. centroid나 convex hull을 전부 가능한 공간이라고 칠하지 않는다. 구름은 **가정 물성·정적 부하·바닥 조건을 만족한 샘플 기반 TCP 점군**이며 그 안의 모든 점/자세/경로·쥠힘·실물 성능 보장이 아니다. SDK cloud는 PointInstancer+작은 sphere prototype, 낮은 opacity(.08 안팎), 물리API/충돌/질량 없음. 원 robot material은 보존하고 actual TCP marker/trail과 구분한다.

초기 q0의 정적 J2 부하는 약5.46Nm/6Nm=.91이다. 이를 숨기거나 torque cap을 키우지 않는다. 초기2초 hold 후 천천히 들어 올리는 이탈 구간만 cap비율≤.95를 허용하고, 이후 구간은≤.8로 제한한다. 예비 경로 degree는 q0 → [0,-35,20,0,0,0] → [-60,-35,20,-25,-15,-45] → [60,-35,20,25,15,45] → [60,-55,-25,-25,-20,-60] → [-60,-55,-25,25,15,60] → [0,-35,20,0,0,0]. 이동 시간[5,6,9,8,9,7]초와 각 끝1초 정착, 초기2초로 총52초다. 원 velocity .5rad/s와 joint limits를 전 경로에서 검사하고, 단지 waypoint만 검사하지 않는다. 샘플러의 전구간 검사 결과에 따라 같은 한계 안에서만 경로를 줄일 수 있으며 실제 실행 중 목표/게인/한계를 바꾸지 않는다.

전 이동을 quintic 보간하며 최소101점/구간+결정론 미세격자로 floor/중력cap·position/정확최대velocity를 사전 screening한다. 이는 연속경로 증명이 아니며 실제120Hz 모든 행에서도 torque/한계/floor/FK를 따로 검사한다. cloud에 속하지 않는 초기 이탈 구간과 이후 feasible 경로를 별도 표시한다. camera는 cloud+전 경로 body bounds를 실제 FOV로15%여유 있게 덮는다.

큼직한 동작의 수용은 선정 목표뿐 아니라 actual 관측에서도 J1 peak-to-peak≥100deg, J2 초기 대비 excursion≥30deg, J3 peak-to-peak≥40deg, J6 peak-to-peak≥100deg와 capture시점 actual TCP 최대점간거리≥.30m를 모두 요구한다. 경로 screening 때문에 이 하한을 만족할 수 없으면 실험설계를 FAILED로 끝내며 영이동/작은동작을 큰동작 성공으로 표시하지 않는다. 실행 중 경로 축소는 하지 않는다.

## 물리·관측·렌더

SimulationContext dt1/120, gravity[0,0,-9.81]를 시작부터 적용한다. reset 이전 USD 초기 자세는 원 q0, reset 이후 q/qd를 목표로 덮지 않는다. 전 단계9개 actual DOF 이름 매핑·11 LINK poses/COM/full inertia·native engine/Lab clock을 기록한다. native 중력 query 전체9/15열을 실제 이름으로 매핑하고 producer/root가 각각 actual pose·질량으로 계산한 참조와 대조한다. 원cap−abs(FF)만 남은 drive cap으로 적용, 음수면 유효 부하FAIL이며 cap확대/클리핑으로 성공을 만들지 않는다. acceleration Kp64/Kd16은 기존 가정으로 유지한다. 072의 actual Base PhysxArticulationAPI 선언·bool readback을 그대로 포함한다.

영상 **10fps/stride12**, 52초라면6240step/521frame. steps와 frame수는 프로그램에서 유도하며 옛22초/2640/331 하드코딩은 제거한다. 모든 행의 관절·clock·torque/readback·FK·TCP·gripper relation을 검사하고, 정착은 움직임 transient와 분리해 각 hold 끝에서 판정한다. 원 pose/vel 정착 한계는 유지한다. 데이터는 step NDJSON journal+작은 partial checkpoint로 저장해 매프레임 성장 전체보고서 O(n²) 복사를 피한다. final report/manifest와 frames sidecar는 원자료·SHA·정확한 행/프레임 집합을 봉인한다.

실제 RTX RGBA pixels만 사용한다. cloud는 실제 USD scene에 존재하고 물리 영향을 주지 않아야 한다. 초기 smoke에서 실제 annotator/node/RP 클래스·호출 API·dtype/shape·rgb/ref/dispatcher compute generation·rational scheduled/ref시간·render 전후 clock 불변을 확인한다. 누락API·staleframe·blank·soft renderer error는 실패다. wrapper id를 native id라고 부르지 않는다. 원 renderer 경로를 software replay로 대체하지 않는다. 첫/중간/끝 실제 PNG를 열어 cloud/robot/marker/바닥/FOV를 확인한 뒤 MP4를 만든다. 글자/HUD를 후처리로 넣으면 annotation임을 출처에 명시한다.

## 새 실험의 native 한도와 게이트

새073 원장은 experiment_id와 엄격한 경로로 기존069/071와 구분하며, 원 실패 이력을 readonly ref/문서로 연결한다. import1회, **physics/render smoke 최대2회**, **큰 동작 motion 최대2회**, 각600초와 전체45분을 함께 적용한다. smoke는 짧은 q0 fullgravity hold+native 카메라/physics 경계 확인이며 큰 경로를 실행하지 않는다. 두번째 smoke/motion은 첫 원본 실패·원 code/PID·회수·입력 지문을 보존하고 한정 integration/API 수리와 비작성자 재검토가 통과했을 때만 허용한다. 같은 성공을 반복하거나 유효 부하/추종FAIL 뒤 게인·cap을 바꿔 재실행하지 않는다. 새목적·횟수를 승인 없이 늘리지 않는다.

순서: source/host/L4 PASS → fresh import/static PASS → smoke의 실제 physics/render PASS → 큰 경로 motion. smoke의 q0 hold도 본시험과 같은 pose/velocity 정착기준과 모든원cap/clock/FK/render 조건을 통과해야 한다. 불완전 smoke나 소스공통물리입력이 다른 import를 이어 쓰지 않는다. 공통domain(A source/model/SDK/refs)와 B 실행 source를 구분하고, B-only integration 수리도 새 fulljob/sourceSHA로 봉인한다. 실패도 예약소비하며 단일 lock/keepawake/ownedPID 회수·actual/policy/shell 종료코드·firstfault를 보존한다. 부모600초와 SDK fast shutdown/watchdog의 범위를 혼동하지 않는다.

호스트는 고정 이름/개수의 정상·재봉인 음성으로 sampling FK/토크/floor/velocity·선정q·witnesscloud·금지physicsAPI·opacity/FOV·가변step·FF/name/clock·journal누락/중복·stale/renderer·원장중복/초과/단계선행조건을 검사한다. 원본 controls와 새 controls를 구분하며 메타라벨을 실제SDK수용으로 승격하지 않는다. 실제 simulation FAIL이지만 유효 native frame이 있으면 FAIL 영상으로 저장할 수 있다.

## 저장·종결

기존 ffmpeg/ffprobe로 fps/frame수/길이/full decode를 확인하고 Google Drive 기존 robot-arm-lab 영상/2026-10-30 폴더에 새 이름의 MP4+출처JSON을 업로드한다. 부모/이름/크기/MIME/URL을 재조회하고 remoteSHA 미노출은 로컬SHA와 구분한다. 영상이 없으면 없다고 기록한다. source/결과/동일계열 검토 한계·가정·원실패·사용 슬롯을 인계하고 scoped local commit한다. 실물 운전·성능 인증/강화학습 실행을 했다고 하지 않는다.
