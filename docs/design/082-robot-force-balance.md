> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 082 — 승인된 비영COM 힘·모멘트 계약과 로봇 동역학 대조

사용자는082후속제안으로계속진행·PD/포화분리·원기준무완화재검증·영상·실물제외를승인했다. M45 관측시작2026-10-30 06:09:44UTC(한국15:09:44)→06:54:44UTC(15:54:44), 검토/영상/인계/Git포함. L급을A(관측/검증수리·HOST·L2/L4)와B(native/분석/영상/인계)로분할한다. L2/L4각max2·native import1/정지1/큰동작1 각600초·prepare/launch900초여유. 실패소비·추가발사/자동새예산없음. 기존081이하원자료/원장/판정과082제안문서는변경하지않는다.

소유 src/simulation/force_balance_trial/ (081의15source기반+balance.py),outputs/isaac-force-balance-v1/,본계획/082-results/최소인계. robot제어/경로/게인64_16/FF/cap·원0.5도/1도_s·1초정착·속도/바닥/중력/FK/그리퍼/영상기준은081과동일하며튜닝하지않는다. SDK설치·CAD/URDF/물성/모델16은변경하지않는다. 초기화/capture/program/workspace/torque SDKadapter수명경계도보존한다.

## A1 — 비영COM·다른축 기준물

기존COM0 force/Z기준물은그대로두고acceleration기준물을Y축·rotor COM=(0.4,0,0)m·질량1kg·등방COM관성0.05kgm²·고정base초기Rz45도로한다. 평행축유효관성은실제readback으로 Ieff=Icom_axis+m*(|r|²−(axis·r)²),명목0.21kgm²다. 두기준물의중력만disabled하고실제tensorflag를검사한다. 이는단독관성식의조건이며robot/world중력−9.81은바꾸지않는다. reference는무연결·무충돌·화면밖이고추가physicsstep/q·qd복원없다. 고정5개0.4초단계·PDonly/외부only/combined/coast·gain64/16/cap.01/명령값은081을따른다.

실제axis/초기pose/COM/관성·중력flag/clock/issued명령·before/after q,qd/연속성·native7Dlinktransform/incoming6D/projected를보존한다. 기준물의외부0 PDonly에서 IeffΔqd/dt가단독PD이며combined−readback은계속조건부residual이다. full6D 독립예측은고정pivot에서 vCOM=ω×r, Favg=m*(v_after−v_before)/dt, Tpiv=Ieff*Δqd/dt*axisWorld이다. 실제회전/COM으로root가재계산한다. 선언된SDK child-joint frame·joint pivot 표현과대조하며full6D각성분고정허용 abs1e−4+rel1%를쓴다. 원robot기준과구분한다. world/parent/child-frame·COM/pivot·부호오류반례를HOST에서강제하며,실제데이터로허용오차/축/기준점을사후fit하지않는다. 다른표현후보가맞더라도원계약FAIL과별개진단으로보존한다.

## A2 — 로봇 M/C/G와 힘 평형

매12번째원step직전에동일clock에서 native mass matrix/C를readonly수집한다. G는같은명령의이미검증된pre-step native gravity/virtual-work 증명을연결한다. native DOF이름·9x9matrix·C9/15열·형상/유한성·질량행렬대칭/양의대각·pre q/qd/후qd와clock를root에서재검증한다. 15x15등미지원layout을9x9로억지절단하거나기저qdd를0제조하지않고관측UNSUPPORTED로남긴다. gravity열은기존명시9/15원매핑을따른다.

계산값 Mpre*(qd_after−qd_before)/dt+Cpre+Gpre와그값−FF는 **단계평균유한차분에의한inverse-dynamics/residual추정**이며직접PD측정이아니다. jointfriction/armature/drive-envelope/속도·각도여유를기록하고body damping은USD설정값으로구분해읽는다. 구속/contact/limit/clamp/감쇠/실제외부기여가미식별이면PD/포화/유일원인은UNKNOWN이다. 투영힘/6D/추정힘의오차분포를분리해관측단계의불일치위치를찾되추정값일치를모터힘교정으로승격하지않는다. 계산불능·getter/shape/시계/저장오류는별도관측FAIL·원시prefix/journal에보존하고0대체/재실행하지않는다.

## 실행·판정·검토

fresh import→동일2초robot정지+reference/평형관측→robot정지물리PASS면동일52초큰동작·영상1회. reference/평형FAIL은별도필드이며물리수용으로덮지않는다. 유효한단독PD식별근거가없으면포화원인확증/게인수정은하지않는다. source-review 게이트전 native없음. 새HOST는기존보존대상과비영COM 평행축·full6D·변환/부호·연속성·M/C/G형상/clock/명령결속·실패격리음성대조를검사한다. 비작성자review079가실제source/config/HOST를읽어5범주반례/9MET-UNMET·class를판정,동일계열폴백편향을명시한다.

실제sealed native PNG원속도/요약만encode/full-decode/첫중끝확인후기존Drive날짜폴더에영상만저장·metadata재조회,JSON로컬. 실물보정/모터/CAN/플래시/구매/재부팅/설치/학습없음. 물성가정·robot자기충돌OFF/바닥ON·링보류·포그invisible 유지. 과거reference성공·robot PD OPEN/settling15·provenance7/physical6/eligibility2·velocity-only EXHAUSTED를초기화하지않는다.
