> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 040 — 최신 전체 CAD 기반 시뮬레이션용 URDF 초안

2026-10-27 사용자 명시 요청: 최신 CAD URDF 초안, 질량/관성 미정은 가정으로 표시, Isaac Sim 가져오기 준비. 실물보정·모터운전/플래시·CAN·학습실행·설치·구매는 제외한다. CAD/펌웨어/기존검증/형상은 무수정, 링 형상 검증은 계속 보류. L2 최대2/L4 최대2, 비작성자 검토. 기존020/023startup·SB 충분다음1·025serialization·firmware/PA/terminal 소진이력·임계 및 외부계열NOT_RUN은 보존한다.

## 실제 입력과 범위

최신 전체 조립은 `models/armold-mks-product-v2/armold-type-mks-product-v2.solidcraft`, hash c784ee45bdbbba0b62eaa1218ebaba6b276d8f259c31baed8110174b96f84bc1. 원본7component/7world-root identity occurrence, groundedBase,6revolute 표시0. J2 분할품·사이클로이드 시제품은 별도 부분모델이며 이번 전체기구/물성에 확정 적용하지 않는다.

읽기전용 preflight: 설치CLI 실제0.23.0(이전025의0.20.0과다름)로 원본을변경하지않고 `.dev/urdf-draft-evidence/preflight/v2-current.3mf`로 새export(exit0). 31namedmesh/31identity build item/mm/198280triangles를관측했다. 실제exe/native/export hash와export JSON을보존한다. 기존nativehash는025검증본과같지만새CLI를025solver수용으로간주하지않는다. 기존021math source와kinematics를025의고정hash로읽어기하대조에만재사용한다.

## 산출물 / 소유

- 코드 `src/simulation/urdf_draft/`의 명시적입력변환·검사·시험. 새패키지 `models/robot-arm-urdf-v1/`: URDF,31body STL, assumptions.json, provenance/manifest, preview, README·Isaac import 설정안내.
- 증거 `.dev/urdf-draft-evidence/`, 이계획과최소인계/구조문서. 최신CAD모델·원본파라미터·core·펌웨어 무수정. 패키지재생성은명시적으로실행하며기존파일을자동채택하지않는다.
- CLI/3mf/native 구조밖transform·누락/중복body·단위/links/joint/parent불일치는거절한다. XML mesh단위mm→m 한 번만. namedmesh 모두 bodies.json과1:1대조한다. body를link별로분리하고세계vertices를해당표시linkframe의역변환으로옮겨STL(m) 저장한다. material역할별CAD색유지, URDF mesh scale=1. 3mftransform없는현재export만지원하며임의component형식은추측하지않는다.

## 관절/좌표

7physical links(Base,Link1..6),6revolute J1..6. **URDF q=0은CAD현재표시자세**, q단위rad=canonical core delta이며양은오른손. 기하각=q_urdf+pose_rad; 표시각[15,-50,70,15,25,-10]deg를별도기록한다. 물리영점으로해석하지않는다.

관절origin.xyz=R_parent_display^T*(O_child-O_parent), origin.rotation=R_parent_display^T*R_child_display, axis=R_child_display^T*axis_world. 현재axis들은canonical parent-zero축과같음을확인한다. 021 FK의 Rot(axis,delta)*fixed와 URDF fixed*Rot(localaxis,delta)의동등성을실제숫자로대조한다. native양부호+1은025당시nativehash/툴/27자세에한정하며모터부호로연결하지않는다.

## 가정 물성과 충돌

전부SIMULATION_ASSUMPTION/physical_verified=false로설정한다. 링크질량kg [1.20,0.65,0.70,0.65,0.40,0.35,0.20]는스타터가정. 외형solid체적×PLA밀도로실제질량을추정하지않는다. COM=link-local AABB center 가정, inertia=그질량의균일직육면체 Ixx=m*(sy²+sz²)/12 등근사. SPD/삼각부등식·SI단위를검사하되실제관성수용은아니다.

관절범위±170deg는native예시값이며기계한계아님. 속도0.5rad/s,effortNm[3,6,5,2,2,1],damping0.05/friction0은초기simulation가정이며MKS정격/하중성능을뜻하지않는다. 모터CAN ID/encoder scale/실물부호/실물영점/실측감속비는null/unapproved. 제작중27:1을모든축에확정대입하지않는다.

collision은각link-local AABB box1개 proxy(과대충돌가능), visualmesh와분리한다. 최초Isaac가져오기는fixed-base/self-collision off 권장초기설정으로안내하며self-collision/접촉검증은미완료다. 그리퍼없음. 말단기준은Link6, 형상상tool앞면+X32mm 후보를별도설정에기록하되실물TCP아님. 빈massless tool link를기본패키지에추가하지않는다.

## 검증과 상태 경계

stdlib entry에서입력/기존core/Pillow 등외부의존성읽기전에이번 build상태BUILDING을기록, writable일반실패는FAILED/예외재전파. 명시적out의기존파일은자동reuse하지않고새출력만생성,실패시부분패키지/오래된PASS를가져오기완료로표시하지않는다. 가정config도검증한다. 저장소불가/강제종료는보장밖이다.

검증: URDF XML tree/7links/6joints/parentchain·모든meshURI/31body·m/rad/양의정상inertia/assumption완전성 검사. URDF를 다시 읽어 독립FK로 표시0·기하0·각축±30deg·mixed2를021FK와 대조하고 visualvertices의 세계 복원을 fresh3mf와 비교한다. STL float32 오차를 기록하고 원본 정밀도와 혼동하지 않는다. 잘못된 단위/axis/parent/mass/meshpath 입력이 검사에서 실패하는지 원본 양성 통과 후 확인한다. 링 치형·접촉·간섭 수용은 아니다.

최종 preview는 실제 생성 mesh를 local→world로 변환해 표시자세로 렌더링하여 확인한다. Isaac Sim/API는 이번에 실행·설치하지 않는다. URDF_IMPORT_NOT_RUN/RL_NOT_RUN을 명시한다. GUI가져오기→USD생성→7links/6joints/단위·0자세·축·물성재확인→actuator/과제정의가 후속이다. NVIDIA 공식 URDF/IsaacLab 가져오기 문서 URL과 확인일 기록(버전별 옵션 차이는 설치버전 확인 후 적용).

L2→구현/필요시험→독립L4 원자료/별도FK/가정/원본보존 판정. 원본·입력·tool해시전후대조,실제Isaacimport나학습성공으로확대하지않는다. handoff/backlog/lessons·로컬소유범위commit, push없음.
