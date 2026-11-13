> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 060 — 엔진 시계 관측과 IsaacLab 연결

사용자 2026-10-29 「get_simulation_time 오류 해결하는 새 계획…실제 엔진 시간 확인하고 IsaacLab 재연결까지 검증」을 따른다. 코딩 M급: 새 source 9파일 + 계획1, 총45분 01:19~02:04 UTC. 소유는 src/simulation/clock_session/와 outputs/isaac-clock-v1/ 및 이 계획뿐. 059와 이전 산출물·.dev/CAD/BOM은 보존한다. L2/L4 각 최대2회, 비작성자 읽기 정적 검토. 외부 계열은 이전 hook 차단을 재시도·우회하지 않고 same-family fallback 잔여 리스크를 기록한다.

059에서 tensor view 9개 정상·게인/질량 조회 후 최초 trace clock의 omni.physx.PhysX.get_simulation_time 부재로 FAILED했다. Lab base manager는 자체 _sim_time이고 Lab Physx dummy interface도 같은 부재 API를 호출하므로 사용하지 않는다. 설치 SDK manager 구현의 SimulationManager.get_simulation_time은 native _simulation_manager_interface.get_simulation_time으로 위임한다. 이 실제 SDK 구현 모듈을 직접 읽어 핀된 source와 module/type identity·native interface type을 기록하고, 고정된 getter만 사용한다. 모듈 public alias의 Lab 치환을 선택 경로로 사용하지 않는다. getter 부재·예외·None·비유한·음수 값은 FAILED로 기록한다. fallback이나 시계 설정/초기화·SDK 설치 변경은 없다.

059 9파일을 새 namespace로 복사하되 source inventory와 CORE,058→059 nested원장·runID·SHA,legacy delivery핀을 새060 경계에 맞춘다. physics.py/providers.py의검증은그대로이며 robot.py가 엔진 clock report 작성/검사와 collector연결을 소유한다. 초기화의 단일 소유와 각3purpose 순서·예산·숫자/metadata/GPU/해시/PID/transport·기존4facet/root수치gate를 유지한다. clock-report.json을 terminal의6번째 필수해시 artifact로 묶고 root가 같은 cached robot의 순수check로 확인한다. 원job/PID·SDKsourcehash/origin·실제관측 owner와 nativeinterface type·closed schema·11개 row와3개before/read-before/read-after의엔진값 대응·증가를 검증한다. 보고서에 사용 가능한 API 이름·실제 선택·실패원인·완료구간을 기록하며 실패해도 원자료 보존한다.

trace는 기존10step/11row를그대로 사용하고 새 추가simulationstep은 없다. 첫 row전 baseline 실제getter를기록하고 각row의3clock snapshot에서native시간을읽는다. 단계마다이전엔진값대비dt 증가, 읽는동안불변, Labstep·PhysXpostevent·callbackdt와의별도대조를수행한다. 수치허용오차는 기존1e-6 유지. 엔진시계가정지하면시도는FAILED이며Lab시간/구독합/step*dt를engine값으로대체하지않는다. subscriber는try/finally로해제한다. root가각row의report대응과진행을대조하고 기존kernel의독립판정도유지한다.

호스트: 기존059 15시험유지+getter부재/예외/None/NaN/음수/정지/역행/읽는도중변화/정상시간offset/첫row실패terminalcode/실제collector통합/재해시된root artifact변조음성대조. mock은HOST_MODEL이며실제SDK시간과구분한다. source/AST/whitespace와L4후실제audit900/diag300/connection600 각1회(실패도소진),freshness300. 성공은실제clock증가와기존4facet·최종modulebinding·fullrootacceptance까지통과한때만표시한다. 실패시추가재시도없음. 원격프로세스/lock정리확인후결과인계·scopecommit으로종료한다.

provenance7EXHAUSTED/physical6EXHAUSTED/eligibility2+다음독립실측작성자수용1충분임계·기존0593예약SHA와연속원장보존. 새clockfailure착지·소진/미소진은예산내비작성자판정을요구하며임의reset하지않는다. 047 settling미해결·질량관성가정·링보류. 재부팅/설치/실물보정/모터운전/CAN/flash/구매/학습없음.

공식 API 참고: https://docs.isaacsim.omniverse.nvidia.com/latest/py/source/extensions/isaacsim.core.simulation_manager/docs/api.html （웹문서는설치버전실측을대신하지않음）.
