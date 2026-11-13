> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 078 — 관절 힘과 제동 응답 계측

사용자의 새 지시: 실제 구동 토크와 제동 응답을 계측해 정착 실패 원인을 구분하고 원 기준으로 재검증·영상 보존, 실물 제외. 077의 속도 계약 수리는 유지하되 단일 속도 수리로 정착을 해결한다는 소진 가설을 다시 발사하지 않는다. 이번은 제어 변경 없이 계측 계약을 새로 검증하는 가설이다. 과거 실패·원장·class/임계는 보존한다.

설치 API 근거는 outputs/isaac-torque-observer-v1/tensor-api-source.py·tensor-api-pin.json이다. high-level Articulation 소스 SHA9a2b6170...가 get_dof_efforts→get_dof_actuation_forces(외부 명령), get_dof_projected_joint_forces(실제 incoming joint wrench의 운동축 투영), get_link_incoming_joint_force(자식 관절 프레임6D반력)를 구분한다. 별도의 native PD drive 토크 getter는 확인되지 않았다. **명령 FF를 측정 토크로 바꾸어 부르지 않는다.** 관절 운동축의 실제 합성 힘/토크와 외부 명령을 각각 수집하며, PD drive 단독 토크와 포화의 분리가 검증되지 않으면 UNKNOWN으로 남긴다. 차감값을 직접 측정값으로 승격하지 않는다.

14개 source는 077의13개 복사본 + torque.py다. scene은 zero-time view 준비 뒤 첫양의step전에 force getter를1회 prime하고 API/형상/단위를 기록하되 그 숫자를 물리 샘플로 쓰지 않는다. step0은 NOT_SOLVER_SAMPLE로 명시한다. step1..6240 매120Hz 스텝 직후 command_effort(1,9), projected_active(1,9), incoming force/torque각(1,11,3)를 같은 native clock에서 읽는다. 예외·비유한값·형상·이름 중복/누락·시간변경은 실패한다. unavailable을0으로 채우지 않는다. sensor를 위한 추가 물리 스텝·정착 제외 구간은 없다.

일관성: DOF→모델 child→실제 robot.link_names 및 실제USD joint의 body1·axis로 매핑한다. incoming은 이미 자식 관절 프레임이므로 revolute는토크,prismatic은힘의XYZ축 성분을 택한다. root는 producer를 호출하지 않고 원배열·모델/관절·native 이름에서독립재계산한다. projected와6D투영의 신설센서일관성기준은 abs<=1e-3+1e-4*max(abs)다(기존물리기준 변경아님). command_effort는 실제설정FF의binary32명령과 원1e-8로검사한다. 센서prime에서는일관성수치를물리증거로쓰지않고, smoke의양의240step은전부검사해큰동작게이트에포함한다.

제동 분석: 원52초 경로 각move후반(u>=0.5)와 이어지는1초hold를 고정분석창으로 잡는다. error·qd·finite-difference qdd·힘/토크·power(projected*qd)·readback cap·실제목표/명령을 기록한다. hold 내 원0.5deg/1deg_s를 계속만족하는 suffix의 시작을 time_to_settle로 보고, 원1초안에못들어오면 CENSORED_NOT_SETTLED다. 시간을 늘리거나 마지막위반을제외하지않는다. 6축 동시 움직임이라 힘과응답의 상관관계를 원인확증과 구분한다. 포화·감쇠·결합을자료로분리하되 isolated drive가 없으면 포화판정 NOT_DETERMINABLE, 유일원인 INCONCLUSIVE로남길수있다. 추정PD식만으로실제토크를제조하지않는다.

위치/속도경로·게인64/16·중력FF·cap·원정착/속도/위치/바닥/중력/FK기준·시간코덱·초기화·모델16·포그invisible는077과같다. 계측 추가 외 제어기/물성/SDK설치/CAD/URDF/펌웨어 변경없다. 자기충돌OFF/바닥ON·질량관성가정·링보류 유지. 실물보정/모터/CAN/재부팅/설치/구매/학습없음.

L급을A(계측계약구현/HOST/검토)와B(freshimport→smoke→같은52초motion·분석·영상·인계) M단위로분할하되 전체45분, 시작2026-10-30 01:28:57UTC→02:13:57UTC(인계포함)로한정한다. L2max2/L4max2, native목적각1회·각600초·prepare/launch900초여유guard. 같은제어의 계측유효성 시험이며 실패기준을완화하거나추가튜닝/가설/계획/자동예산·반복발사없음. 센서계약실패시큰motion닫힘, 물리FAIL은과거와같이보존한다. 077결과재사용으로새계측PASS를제조하지않는다.

소유 src/simulation/torque_observer_trial/, outputs/isaac-torque-observer-v1/, 이계획과결과문서·최소인계. 새tensorAPI pin은실제SDK파일SHA와결속한다. L2/L4는AGENTS→DEV_PRINCIPLES에따라비작성자review074 재사용; 이전외부CLI거부우회없음·동일계열폴백편향을기록한다. 5범주반증/9MET-UNMET/class판정과원자료실측읽기를요청한다.

HOST: 기존152와 shape/name/frame/axis/단위/시계/step0구분/NaN/inf/명령을측정으로바꾸기·관절열교환·incoming축부호변조·getter예외·hold censor/경계대조를검사한다. 같은힘채널두이름만비교하는것이아니라원6D배열/다른열순서/실제USD축으로음성을만든다. Native수용은별도다. 실제PNG로원속도/요약영상만Drive에올리고 metadata재조회, JSON로컬보존. 계측/분석PASS를정착PASS로승격하지않는다.
