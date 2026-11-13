> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 080 — PD 토크 의미·포화 구분과 정착 원인 조사

사용자 최신 지시는 PD 구동 토크와 포화 여부를 분리하는 새 계획·기준 무완화 재검증·영상이며 실물 운전 제외다. 전체 M45 시작 2026-10-30 02:48:15UTC, 종료03:33:15UTC(한국11:48:15~12:33:15), 조사·검토·영상·인계 포함. L급을 A(새 관측/기준물·HOST·검토)와 B(native단계·분석·영상·인계)로 분할한다. L2/L4각최대2, native import1/정지1/큰동작1 각600초, prepare/launch900초 여유. 실패도 소비·추가발사/자동새예산 없음.

## 기존 사실과 새 반증 경계

079의양의계측6240·정착15실패쌍·원장·영상은보존한다. source scene은명시적으로 acceleration drive를설정했고 실제USD/row도그방식이다. 따라서64/16을Nm/rad·Nm_s/rad로치환하거나 net projected−FF를검증없이PD라고할수없다. API문서는incomingjointforce에user torque/drive/friction/limit/velocityclamp등이포함됨을설명하지만,정의만으로이번설치본의단독기여를확정하지않는다.

새소유 src/simulation/pd_isolation_trial/ (기존14+reference.py), outputs/isaac-pd-isolation-v1/, 본계획·080-results와최소인계. SDK/init/capture/program/workspace·모델16·robot 제어식/게인64_16/cap/경로/초기화·물리기준은079와동일. 추가독립reference는robot원본/CAD/URDF수정없이같은stage의/World/TorqueReference에둔다. 카메라밖·충돌없음·부하미연결·중력은기존−9.81그대로,회전축Z/COM축일치라중력토크0이다. physicsclock을추가진행하지않고원스텝과동시에관측한다.

## A — 설치본 의미 확인과 관측

서로무연결인1DOF 기준물2개(force/acceleration모드를시작전에각각고정): 각질량1kg,대각관성0.2kgm2,COM0,고정base+rotor·Z회전,넓은각도/속도한계·마찰/armature/rigid damping0. source와실제getter관성/형식/한계를결속한다. 첫2초의고정단계는external-only(.02Nm), force-PD-only(64/16,cap.01Nm), combined(.02+PD), acceleration-PD(64/16,cap.01Nm), free/coast를각0.4초. 비참여기준물은gain/외부명령0으로coast하고모드의운전중USD전환은하지않는다. q/qd덮어쓰기없이연속운전하며각step전후q/qd·실제모드/gain/cap/외부명령·incoming/projected를기록한다. 기준물회전동역학 I*(v_after-v_before)/dt는순관절토크의독립식이며PD는이값에서실제적용외부기여를뺀값이다. getter명령이실제기여와같다는것은external-only/combined의검증을통과하기전에는전제하지않는다. 경계step는실제사용command에결속하고step0은양의측정에서제외한다. robot정본static추출뒤reference를생성해robot11body/9DOF정적검사와분리하되scene.usda와별도reference inventory에추가body/joint를명시하고각reference는동일Labview에개별결속한다.

기준물의실제관성/마찰/armature/모드·원시clock/개수와모든양의표본의유한값/형상·명령readback을root에서도재구성한다. 수치대조허용은고정 abs1e−4Nm+rel1%로사전선언하며원robot물리기준과구분한다. 다섯단계의실제양의표본이각각존재하고, external/drive/combined의신호가0대체가아니어야한다. reference측정의projection↔독립동역학/PD상한관계가맞지않으면MEASUREMENT_SEMANTICS_UNRESOLVED로표시하고그자료를robot PD의실측으로승격하지않는다.

robot에는readonly 마찰3채널/armature/drive envelope·가속도드라이브방식을초기및행기록에더한다. PD후보=projected−외부명령은단지조건부residual로표시한다. force 방식이아닌64/16의Nm식추정은금지. 마찰/한계/속도clamp/그리퍼결합·reference전이한계·cap모순이있으면PD단독·포화/유일원인은UNKNOWN이다. net/cap초과를포화증거로삼지않는다. **실제PD단독측정은기준물의외부명령0인force-PD-only/acceleration-PD-only구간에서만 I*Δv/dt로성립한다. combined의balance−readback은계속조건부residual이며단독측정으로승격하지않는다.** 외부only는외부명령과실제총기여의일치를,combined는사전고정된가산/상한예측과의일치여부를확인하는별도반례시험이다. reference가통과해도robot단독PD를직접측정했다는주장은하지않는다.

## B — 실행과 정직한 판정

fresh import→동일2초정지+reference검증→정지의원robot물리기준PASS일때동일52초큰동작을1회실행한다. reference가실패해도collector예외로데이터를잃지않고원자료·별도관측FAIL을보존한다. **큰동작의PD단독판정은reference계약PASS가필수**이나,원robot정지PASS이면동일제어의큰동작·영상으로현상을계속관측할수있다. 물리FAIL과관측FAIL은별도필드이며전체성공으로합치지않는다. original root checks를모두유지하고마지막0.5도/1도_s·1초hold를늘리지않는다.

HOST는기존191중소스영향부와nativecaller회귀를재검사하고,새기준물동역학부호/단계경계·외부기여/shape/관성·wrongclock/실제caller변수·非有限·零fallback·mixed mechanism을음성대조한다. L2는plan+실제079 source/record·공식API를읽고5범주반례, L4는새source·HOST·실제호출/관측소비까지읽어9MET/UNMET와class판정한다. 비작성자review079동일계열폴백의잔여편향을명시하고외부CLI거부우회없음.

영상은sealed nativePNG만원속도/요약인코딩·full decode·첫/중/끝시각확인후기존Drive날짜폴더에영상만저장·metadata재조회한다. JSON로컬. 결과가미확정이어도원인을만들지않으며더깊은SDK/통제시험후속을별도미실행으로남긴다. 실물보정/모터/CAN/구매/설치/재부팅/학습없음. 물성가정·자기충돌OFF/바닥ON·링보류·포그invisible 유지.
