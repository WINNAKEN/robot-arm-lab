> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 136 — v4 장착면·손가락/피니언 겹침 원인 대조

## 권한·책임·검토

2026-11-10 사용자 「다음진행해」는 완료135가 남긴 출력 부품 3쌍의 원인 대조를 이어가라는 지시다. 원본 모델만으로 공칭 배치·기구학과 실제133/05 기록을 비교한다. CAD·URDF·STL·출력 작업·원장·게인·cap·기존 동작 판정 기준·133/134/135 코드와 원자료는 수정하지 않는다. 신규 SSH/SDK·Drive·실물 CAN/RS485·포트·전원·플래시·설치·네트워크/시계·Git 작업은 없다. 현재 출력 작업과 v4 스냅샷의 동일성은 계속 미확인이다.

136은 완료135 도구의 수리나 예산 재개가 아닌, 장착면과 기어 기구학의 원인 분석 책임이다. 135 CONSUMED_SOURCE_PROVENANCE_WINDOW 1건 CLOSED, 134의 CLOSED 2건 및 원 예산/라운드/원시자료를 보존한다. 유사한 실제 새 인스턴스는 비작성자가 같은 계보와 연결해 판정하며 이름을 바꿔 소진/재발을 초기화하지 않는다.

신규 소유: `src/simulation/mp18_mating_analysis_136/{analyze.py,kinematics.py,test_analyze.py,test_kinematics.py}` 4개 + 이 계획 1개. 산출은 `outputs/mp18-mating-analysis-136/`의 새 전용 leaf만. 원코드·모델은 읽기만, 공유 HANDOFF/SESSION은 Root만 보존 덧붙임. 파일5·책임2그룹(장착면, 기어 결합)=M. 각 role 내부 cap2700초, 주검토자는 L2+L4 공유 누적2700초; 첫읽기/준비/실행/수리/출판 포함, 명시 동결 대기만 제외, 마감300초 확보. 사용자 명시 새45분 승인이라고 쓰지 않는다. L2/L4 각각 max2, 합 max4/no5, 분기별 여분을 다른 분기의 추가 라운드로 전환하지 않는다.

L1 Root → 비작성자 L2 → 별도작성자 L3/HOST → 비작성자 L4 → Root 정확 핀 확인·최종 로컬 CLI 1회·보고. 작성자 readonly 준비는 최대120초에서 동결하고 FINAL L2 PASS 전 제품 코드0. 기존 사용자가 승인한 동일계열 비작성자 폴백을 유지하며, 외부 계열 부재/공통 커널 위험을 잔여로 명시한다. 검수자는 제품 patch를 쓰지 않는다.

## 고정 근거와 사전 관측

- 135 최종 F2 `author/source-freeze-F2.json` SHA `7d3a1fdf10fccb90b576430363f8fdbfca67f718c4ae1841e1e5c4b34a32b61f`, 최종L4 `b7483f8f6e868fa564282cb325eca222332f64142ad9e480e0f5a9ec6565593a`/publication `86b5088f9ebcd53b4b439375fbaa80f31b8a87450c6a298ab4965f30c8e09bd5`.
- 135 Root 완료 `Root-final-result.json` SHA `a446343e444e5014dbbdb394b7efb2608e6016db8b071d44c8c93c64be2341dd`. Root-compare-r1/comparison.json SHA `cd6c408d9c353e907578e497469469370b3f0526eb45aa55824813eb90470227`; 그 artifact manifest로 cases/parts/mapping/source/input를 소비 전 검산한다. cases SHA `749138c05fbe372209a5e5d270d16495ddc5cd8425428ef81fe2678bc93e3dd9`.
- 대상은 printed part-pose 양성8건/유일 원부품쌍3개 정확 선택: TOOL_FLANGE↔KG1:BASE 6건, 57초 KG1:JAW_A/B↔KG1:PINION 2건. 원135 전체91/32905 및 미세불확실/제외/미판독을 임의 확대해 완료로 쓰지 않는다.
- 133 F6 SHA `3cf40c09cc20bac27195fc1963e997734f3dbc3e8e03b25bf737e0ecf97ace3f`, native-result SHA `c4345f4461601566d9398a7ab6101217f2bfa0e1f851b8bfb33352687a92b4e2`, actual05 run `850124eb93cc4cc4945ee02c3aa1ed0d`, job `816522a14e506263a7a7517ce76ad7deb23402ffc6bddd6c23513f306725a6ae`. raw `retrieved/motion.ndjson`는 native files_sha256와 SHA/bytes·row11161·step0..11160·time=step/120·동일시계/owner/q/target census로 결속한다. 현재 L1이 원378핀 모두 일치를 재검산했다.
- canonical URDF `models/robot-arm-urdf-v4/robot_arm.urdf` SHA `d55f0cbdffb8f82094b8797b187f02a3a5fd77a4a4f4272c975f21945b53135f`. numeric-ledger/asset-ledger/provenance/visual 원메시 및 135의 원part partition을 사용한다. 기존 검증된135 helper를 핀한 immutable bytes에서 읽기 전용 재사용 가능하나 원135 CLI/출력은 호출하지 않는다.
- 원CAD geometry snapshot reference는 **u=0mm(닫힌 원부품)** 이고, URDF zero는 slide origin ±20mm/피니언 origin Ry(-20/13.5)로 **벌림40mm**다. 원몸체 메시가 이미 body-local SI이므로 원CAD transform이나 zero opening을 중복 적용하지 않는다.
- URDF KG1_mount: Link6→KG1 xyz[.028,0,0]m, rpy[pi/2,0,pi/2]. slide_A/B axis[-1,0,0]/[1,0,0], B mimic=A. pinion axis[0,1,0], mimic multiplier -74.07407407407408 rad/m, offset0. 계산값은 반드시 XML/ledger에서 읽고 numeric-ledger 및 원CAD parameter m1.5/z18에서 r=13.5mm와 대조한다.
- L1 57초 actual q: slide_A=-.010016066953539848m, slide_B=-.010016286745667458m, pinion=.7777896523475647rad; targets=(-.0105,-.0105,.7777777777777779). 관측상 목표 추종과 실제 기어 결합은 별개일 가능성이 있지만 원인 결론은 아래 대조 이후다.
- 현 `src/cad/kmjh-gripper-v1/parameters.json` SHA `7c116e9f9bfeb49e4b45c5495f7b5f23ce6f3c7d60c1dc66680d604c98d42b8e`는 v4 generation provenance와 일치한다. 현 verify_gripper.py SHA `27c5362ab1554deea4ac9462b4f5b0f4898cfa2cb8b0bd17db4f3d9e6d8e3c64`는 generation의 `3ddd492a28cb9ef391c8274c15b5239f755b3c14ed553c8081337ee8fd242d49`와 다르다. 현 설계 의도를 읽을 수 있어도 과거 실행된 verifier라고 주장하지 않는다. 현재/과거 원장·검사 코드의 drift와 nominal mesh 불변을 분리한다. CAD 생성기·verify_gripper는 실행하지 않는다.

## 대조 방법

### 1. 프레임·시계·원부품 검증

URDF origin=T_parent_from_joint_zero, child frame=joint frame, axis=joint frame임을 적용한다. rpy는 Rz(yaw)Ry(pitch)Rx(roll), prismatic은 T0·Trans(axis*q), revolute는 T0·Rot(axis,q). SI m/rad에서 만들고 Boolean 직전에 mm로 한 번만 변환한다. wxyz 정규화는 계산에만, 원 q/pose는 그대로 보존한다. 전11161행의 유한성·step/time·q/targets/11body poses를 검사하고 원8개 표본을 row/part/actual pose/volume과 정확 결속한다. stale/누락/위상 branch 모호성은 UNKNOWN·오류로 남기고 명령/FK를 실제 pose로 대체하지 않는다.

135 원part loader/Manifold Mesh64의 유효·closed/winding/양volume/상태·원삼각형 volume 검산을 그대로 지킨다. 기준 geometry와 helper source를 실소비 전에 고정핀 검산하고 실제 캡처 bytes로 실행하며 전후 디스크 drift를 검사한다. 원고체/원메시 repair·tolerance weld·normal flip은 없다.

### 2. 플랜지–베이스 6표본

각 actual relative T_Link6_from_KG1와 URDF fixed mount 및 numeric-ledger mount를 대조한다. 병진 residual은 mm와 벡터, 회전 residual은 rad 및 각도, 원part 교차 부피를 모두 기록한다. 실제3D자세 재현, URDF 공칭 mount, numeric-ledger 공칭 mount를 같은 원부품으로 계산한다. 공칭에서도 겹치면 static snapshot intersection, 공칭0/actual양성이면 recorded relative pose 기여 후보로 분류한다. 값만 보고 원CAD 불량/물리 solver 원인/프린트 공차로 단정하지 않는다. 가능한 경우 실제 겹침 원부품의 공유 내부점/국소 범위를 기록하여 어디가 겹치는지 추적한다. nominal과actual 결과가 서로 다르지 않으면 수치오차·삼각형 수출과 원형상 여부를 별도로 남긴다. 6표본 불변성도 수치로 확인한다.

### 3. 손가락–피니언 57초 2표본과 전기록 결합

전11161행에서 epsilon_A=qPin-(m*qA+b), epsilon_B=qPin-(m*qB+b), jaw asymmetry, target coupling residual과 각각의 target tracking error를 계산한다. peak/time/구간별 통계를 내며 rad/deg 및 등가 rack변위 mm를 함께 낸다. 기존 gripper 목표 오차 허용과 이 결합오차를 혼동하지 않고 새 안전 통과 임계는 만들지 않는다. 원래 accepted133 결과를 소급 변경하지 않는다.

원3D actual bodies의 KG1→jaw/rotor 상대변환을 XML FK(q_logged)와 비교하여 trace/프레임 일치를 먼저 검증한다. rotor 각도는 origin을 제거한 뒤 joint axis의 signed angle을 q근처 branch로 복원하고 off-axis rotation/translation 잔차를 별도 기록한다. axis/부호/단위/zero offset 검증 없이 Euler 한 성분을 q로 쓰지 않는다.

각 jaw/pinion에 같은 원part를 사용하여 최소 아래4경우를 계산한다: (a) actual body pose 재현, (b) URDF FK 실제 logged q 전체, (c) jaw 실제 q를 고정하고 pinion만 URDF mimic 식으로 결합시킨 반사실, (d) 같은 시점 logged targets의 공칭 FK. (c)는 실제 관측이 아닌 수치 진단이며 실제 동작·수리 성능·새 실행 PASS라고 표현하지 않는다. A와B 각각 실제 q 기준으로 결합하고 대칭을 강제해 관측을 숨기지 않는다. 필요 시 u=0·URDF q=0·해당u의 공칭 결합 및 작은 양/음 위상 대조로 원geometry/zero offset/치합의도를 분리한다. 위상 최적화로 양성 부피를 최소화한 뒤 무간섭이라 선언하지 않는다.

교차 부피는 mm³, 0<V<=.01은135와동일 SMALL_VOLUME_UNCERTAIN, invalid/부족관측은UNKNOWN. 각 가설의 근거/반증/미확정을 표로 보고한다. 원CAD 현재 place(u)식 th=-u/r와 XML body-frame FK의 공칭 대응은 parameter/provenance가 유효한 범위에서 대조하며 과거 verifier 해시 불일치를 감춘 의도 확정은 금지한다.

## 실행 경계·검증·산출

CLI는 고정136 lexical output root + 제한된 fresh leaf slug만 허용한다. 존재 ancestor의 NTFS reparse/symlink와 alias/escape를 처음·출판 직전에 거절한다. fresh exclusive leaf·완료 JSON 마지막·전후 input/source 검산. 135에서 입증/수리한 실제 실행 source provenance와134 output-root authority 교훈을 재도입하지 않는다. 자신의 source4+plan 및 실제 소비 dependency/source bundle을 불변 bytes로 묶고 그 bytes로 실행한 해시만 남긴다. 테스트는 원본 파일이 아닌 소유 clone만 변경한다.

HOST는 analytic RPY/임의축 회전·prismatic부호/zero/단위·signed angle branch·coupled 기어/의도된 phase slip·잘못된 target을actual로바꾼반례·없는/중복 case·run/hash/pose/step변경·source변경시점/latepublication·실native경계·실제producer→원8재현/nominal/counterfactual→보고서까지 검증한다. 기존 source-bundle/namespace 공통 코드의 실효 음성은 작은 authentic clone에서 보며 동일 호출 재실행만을 다른 관측 기전으로 세지 않는다.

산출: 한국어 cause-report.md, analysis.json,8case 대조행/공칭·실제·반사실 변환/교차 부피/상태,11161행 coupling summary와 peak witnesses, source/input manifest·재현 명령. 모든 count는 실제로 검사한다. 전기록 결합 분석과8개 입체 표본의 범위를 분리한다. 원8 재현이 안 되거나 판단의 필요 관측이 빠지면 전체 확정 true를 내지 않는다.

비작성자 L4는 원 q를 독립 계산하고 scipy Rotation/행렬 solve 또는 원삼각형 ray 같은 다른 기전으로 변환·관측을 검산한다. 같은Boolean커널 수치 반복은 이중커널 검증이 아니다. AC8: (1)권한/고정입력/원135·133보존 (2)3쌍8표본 exact selection·실제row/pose 재현 (3)XML/CAD zero·좌표·SI/부호 (4)전11161 결합·목표추종/실제와공칭 구분 (5)nominal/actual/counterfactual 완전성·유효volume/UNKNOWN (6)실제producer HOST와다른기전 관측 (7)source-byte/input·outputauthority/완료최후 실효 (8)신규/기존class 계보·예산/라운드/결과/최종publication 일치. Root는 FINAL L4 PASS와정확핀 이후만 최종 CLI를1회 실행한다.
