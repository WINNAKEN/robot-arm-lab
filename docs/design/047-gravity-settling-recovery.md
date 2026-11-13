> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 047 — J2/J3 정착 실패 수정 · 시뮬레이션 재검증

2026-10-28 사용자 「실패 두건과 아이작랩 연결 진행해」. 코딩/시뮬레이션 세션이다. 기존043 DYNAMICS_FAILED/0of28와044 준비본/가중치null을 보존한다. 다른 작업 HEAD92028db의 MP8/CAD/그리퍼도 수정하지 않는다. 실물 보정·모터/CAN/플래시/구매·링 검증은 계속 제외한다. 이번 명시 지시는 새로운 수치 설정 실험과 후속048의 프로젝트 전용 IsaacLab 설치/연결 검증을 허용하지만 학습 최적화/장시간PPO는 포함하지 않는다.

## 범위·예산

047은 M급8파일: 신규 `src/simulation/settling_recovery/{runtime.py,core.py,verify.py,driver.ps1,pins.json,test_recovery.py,README.md}` +이 계획. 새 파일/출력 `outputs/isaac-settling-v1/` 소유. 041~044·펌웨어·CAD는 읽기전용. 외부 계열 bridge는043의 보호 hook 차단 이력 유지/이번 재시도·우회 없음, 기존 비작성자 L2/L4 fallback/잔여리스크를 명시한다. 각각max2. 새 구현 working agent 생성 없음. AGENTS→DEV_PRINCIPLES 의무에 따라 기존 비작성자만 검토한다.

043 닫힌 실행 예산을 재개하지 않는다. 명시된 수정 실험으로047 author 실행은 **최대2회, 각각600s**, 매 실행 예약을 시작 전 영속화하고 실패/시작오류도 소비한다. 1번은고정solver설정만 변경, 2번은1번이정착실패일때만 사전정의PD설정 추가 또는 측정된 시작/API 오류의 최소수정 검증에 쓴다. 성공한 실행을 반복하지 않는다. 호스트 의미 검사는 물리 실행 예산이 아니다. 이후048 native Lab 연결은 별도 계획/실행예산으로 단위분리한다.

기존 physical-frame accepted2/다음독립실측+작성자수용동종1 ⇒ EXHAUSTED, 실행의존/provenance accepted2/다음동종1 ⇒ EXHAUSTED와039/041~044·firmware/startup/SB/PA/terminal/외부SDK 실패 이력 유지. 새 이름으로 초기화하지 않는다.

## 관측·가설·변경

043 실제6781샘플을 재조회했다. 기존kp `[9.3451,9.9980,5.02052,.194449,.519683,.00669014]`,kd `[2.33627,2.49950,1.25513,.0486123,.129921,.00167253]`,总 effort `[3,6,5,2,2,1]Nm`. 최종q오차 J2+.78727°/J3−3.61589°, 실제qd J2−2.97120°/s/J3+6.24325°/s. 마지막1초의 q차분속도와APIqd의평균도일치하지않는다. 중력ff미포화·원치않는접촉0이라는 기존 사실만으로 원인을 확정하지 않는다. 긴 저관성 직렬관절의 제약 solver 수렴/드라이브 정착을 우선 가설로 둔다.

1번 설정 `solver`: 현재 PhysX articulation position iteration64/velocity iteration16을 **명시적으로 author하고 source/static에서 readback**한다. 기존gain64I/16I,force모드·feedforward와보수적residualPD cap은 그대로. solver default와 차이는 별도 기록하며 형상/중력/충돌·가정질량/관성·토크cap/120Hz·원래56.5s/28checkpoint recipe/오차.5°·속도1°/s·원래 frame tolerance를 바꾸지 않는다.

2번 후보 `solver_pd`는위solver그대로 +K=256I,D=32I(자연진동수16rad/s,critical damping 가정). 원래K=64I,D=16I와 비교하며 총 effort cap은 늘리지 않는다. 원인 분리는 1번 결과를 보고하며2번 성공을solver단독수리라고표현하지않는다. q/qd직접설정이나teleport/kinematic target을성공궤적으로사용하지 않는다. 실제LINK/COM/관절/접촉/시계 관측을 보존한다.

## 구현/검증 경계

047 runtime/consumer/driver는 승인된043 구현을 새 소유경로로 복사해 변경한다. 기존environment·gravity/motion core·041/042검사기/frames/extractor를 재사용할 경우 **모든 실행 transitive dependency를 승인 SHA로 확인한 뒤 import**한다. runtime bundle의 local/remote hash·job/PID/실제exit/completion·원자료 결속과 누락입력FAILED 경계를 보존한다. current/source pin은 실제 원본과 일치해야 하며 유저 편집 readyflag로 통과시키지 않는다. 새core.gains는 static variant와 실제 설정을 참조하고 consumer도 같은허용variant를엄격검사한다. 임의variant/gain/solver/토크/실행예산변조는거절한다.

호스트: 기존 프로그램/가정/043파일불변, 두고정gain/solver설정, 선언한variant와source/PID/hash/누락 실패, 실제solverreadback변조/한계완화음성, 이전043실패를PASS로오인하지않는 경계. 047 실제검사는041정적 frame·실제 runtime mass·모든6781시계/LINK/anchor/signedaxis/collider/contactframe을 포함하고, 28 checkpoint .5°/1°/s와접촉양성대조/원치않는충돌0·ff미포화 조건을원래대로적용한다. 새solver assertion을추가할뿐 기존검사를빼지않는다.

원자료는GUID/write-once 보존하고 실패와INVALID_EVIDENCE를구분한다. author+독립검토가수용한 경우에만新047동작PASS를기록한다. 기존043·044의historical failure/status/hash를소급수정하지않는다. output delivery/HANDOFF에 실행/검토예산·가정/한계·차이·다음048참조를남기고소유범위로컬commit한다. 보호 `.dev`는이전hook경계유지/도메인결과에인계한다.

048은별도M단위로공식IsaacLab release/3.0.0 commit `270a8c1d4a26181adf2c5bd2fc9a3c649f17a294`를검토·설치하고기존6.2RC와native환경/모델연결을검증한다. 원격git는현재PATH에서발견되지않았고C여유약341GB다. 새드라이버/보안/서비스/기존Isaac교체는하지않고공식소스·의존버전·실제모듈경로/RC호환을별도확인한다.
