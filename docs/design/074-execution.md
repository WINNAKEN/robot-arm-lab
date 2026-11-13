> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 074 실행 계약

사용자가074제안의새45분을승인했다. 시작2026-10-29 22:16:50UTC/종료23:01:50UTC(한국10월30일07:16:50~08:01:50). L2/L4각최대2, native import1/smoke1/motion1 각600초,남은600초미만시시작금지.073원실패·소스·원장무수정. 새소유src/simulation/gravity_init_trial/,outputs/isaac-gravity-init-v1/.

설치SDK파일무수정과runtime함수무변경은다르다. 새init_boundary.py가pinnedLabmanager moduleSHA dc1a3fbabbb54a4a3f7c45bf10e25643a346b06a6d9577e8f974584df9869742 및원classmethod AST를검사하고프로젝트안에서원함수의정확한두Call `physx.update_simulation(cls.get_physics_dt(),0.0)`의첫인수만0.0으로변환한다. 변환수2외에는AST동일을검사한다. 원AST/변환AST/runtimecodeSHA를기록한다. 실제클래스의원descriptor를보존하고reset호출기간만classmethod를대체,finally에서복원·동일성확인한다.모듈globals는pinned원함수globals를그대로사용한다.

자동physicsplaySimulations=False를SimulationContext생성전설정·readback하고rawPhysx pre/post구독도그전에설치한다.늦은Labcallback에의존하지않는다.양의dt사건은native시간과실제q/qd조회가능여부를기록한다.뷰준비이전양의단계·조회누락은INIT_OBSERVATION_GAP이다.초기0dt콜백의뷰불가를명시하고0으로채우지않는다.콜백예외는fault로보존하고다음경계에서실패시킨다.

zero-time reset의전후native시간불변·실제초기q/qd원0자세(수치1e-6)·Labstep0·양의callback0을검사한다.불지원은INIT_BOUNDARY_UNSUPPORTED로실패하고양의warmupfallback은없다.실제뷰생성후FF/잔여원cap/drive목표를설정하고첫양의sim.step을허용한다.원g−9.81·cap·Kp64/Kd16·속도/정착/바닥기준유지.전체운전callback의pre/post count=명시적step수,실제q/qd와원clock기록·fault0을독립root에서도검사한다.

/World는stage설정시UsdGeom.Xform.Define으로명시하고strict원oracle무완화.새job/source13개·init증거도기존원본seal에포함.전체프로그램·workspace generator/데이터/모델16·SDKlifecycle은073그대로.원test48/B29와새변환·관측·실패음성HOST를실행하고비작성자L4후에만native.원실물미승인·링보류·물성가정유지.
