> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 096 결과 — 기존52초 독립감사·정착 분석·회수 수리

2026-11-01 KST. 상태 **OFFLINE_REVIEWED_COMPLETE_REMOTE_NOT_RUN**. 새native/SimulationApp/SDK/SSH/네트워크/실물CAN/flash/급전/모터/보정/설치/학습/외부업로드0, 새45분 예산 없음. 게인64/16·cap·물성·52초 경로·판정 기준 무변경. 새 source18은 deadline0/native각목적0과명시거절을유지하는비활성후속후보다. 원095 source17/원장·원회수FAILED/복구receipt/모든과거실패·소진/정착15·velocity-onlyEXHAUSTED·임계는 보존했다.

## 기존095 자료 감사

원job/source/terminal·parent·remote-shell·원봉인·원transport0/최초FAILED/별도복구결과를읽고 원consumer를 오프라인으로 다시 실행했다. import IMPORT_VERIFIED/정지 SMOKE_VERIFIED/모션 LATEST_SCENE_DYNAMICS_FAILED를 재현했다. 모션52초6240step6241obs521PNG, 전체 연속journal와report/PNG CRC·sidecar/7endpoint를 대조했다. 34초 J3/J5 위치미달이 전체physics BLOCK의 원인이며 나머지9checks와fixed9/COM 검사는 통과한 원판정을 유지한다. 작성자 감사는 native-audit-*.json, 새096 비작성자 L4에서도 독립 감사 PASS를 확인했다. 원095의 소진된R3를 추가한 것이 아니다.

## 관측된 정착 패턴

전체목표벡터가 일정한33~34초 hold만분석했다. 정확33초의앞선move endpoint는목표벡터가hold와같은경계표본으로만포함한다. 34초뒤는J3의개별목표가같더라도다른축/위상목표가바뀌므로정착연장근거에서제외했다.

| 시각 | J3 부호있는 위치오차 | J3 속도 | J5 부호있는 위치오차 | J5 속도 |
|---|---:|---:|---:|---:|
| 33.0s | -0.971448° | +1.609361°/s | -0.837497° | +1.357601°/s |
| 33.5s | -0.079333° | +1.734724°/s | -0.072044° | +1.519227°/s |
| 33.9s | +0.491809° | +1.043213°/s | +0.436089° | +0.942575°/s |
| 34.0s | +0.584715° | +0.814251°/s | +0.520335° | +0.740712°/s |

두 관절은33.541667~33.55초표본 사이에목표를지나고,끝에서는양의오차가증가중이다. 마지막0.1초의절대위치오차증가는J3 0.092906°/J5 0.084245°다. 단순히목표에늦게도착하는단조접근패턴이아니다.

원조건은위치≤0.5° 및속도≤1°/s를동시에요구한다. J3는이hold내동시통과표본이0이다. 위치는33.9초까지통과하지만속도는33.925초부터통과해겹치지않는다. J5는33.875000~33.966667초의12개표본(첫~끝 간격0.091667초)에서만동시에통과한뒤위치기준을벗어났다. 이구간은120Hz기록의연속표본이며연속시간안정성인증이나원endpoint판정변경이아니다.

기록된남은cap명령·설정값은J3 3.063100~3.197865, J5 1.464775~1.510080다. 이는명령/설정관측이며실제PD토크·포화센서가아니다. PD/포화UNKNOWN, moving-root독립교정NOT_DONE을유지한다. 제어·모델·구속중유일원인이나단순hold연장으로해결된다는결론은없다. 다음진단은별도승인후말단접근/hold중한요소만바꿔확인하는후보다. 이번에경로/hold/게인/cap/허용오차를바꾸지않았다.

## 회수 경로 수리와 검증

원export는일반snapshot의smoke 물리 의미검사뒤에진입하고caller/SCP는default120초였다. 새source18의실제entry export는일반snapshot앞에서고정SHA로결속된stdlib회수모듈만로드한다. 입력/출력/프로세스/닫힌native seal 또는실패parent snapshot/안전한경로를검증하고기존파일만복사한다. SDK·기하학의미검사import없음, archive/receipt exclusive생성·전체파일hash/ZIP CRC/receipt결속·실패결과보존·수용권한false다.

실제launch caller는export/SCP에정확int300초를명시하며,한번exclusive예약한총600초와원절대deadline중이른기한의남은시간으로각호출을제한한다. 실패뒤시계재설정/자동retry/기존파일덮어쓰기없음. native transport와recovery상태를분리해회수실패로SDK미실행을추론하지않는다. public prepare/run·remote supervise/native·직접supervise는명시차단되어있다.

HOST는회수89/분석21/기존scene29=139개통과다. 실제entry가snapshot을호출하면실패하는검사, 실제launch의가상130초회수양성,default120/snapshot-first복원변형검출,300/600/절대기한·시계소비·native실패보존·public예외분류,resealed미검토helper·ZIP탈출/중복/link와원파일변조음성을포함한다. transport는합성이며실제네트워크가아니다.

실제095의기존1077파일도새도구로로컬복사/해제해원바이트전체일치를확인했다. 로컬1회계측:원snapshot 17.900초,새metadata검증 7.703초,새export+archive검증 32.414초,해제+검증 31.850초. 위타이밍은R1초기구현의로컬1회계측이다. R2최종상태/경로게이트로같은095archive와원본및094실패snapshot을재검증한근거는local-revalidation-r2.json이다. 원격120초실패의지배비용/유일원인이나실제원격300초성공보증은아니다. 재조회는최초validation을덮지않고별도exclusive query파일과최초SHA를남긴다. terminal의CLOSED/APP_CLOSED 또는PRE_CLOSE/CLOSING_APP(닫힌parent) 또는FAILED/비영코드와failedparent의FAILED marker를검사한다. 실제수리SSH/native성능은NOT_RUN이다. 원095실행기는동결보존했고수리본은새비활성사본이다.

## 검토·인계

L2R1 PASS9/0. L4R1은자료독립감사PASS/코드BLOCK7/2였다. F1재조회실패분류·최초validation덮어쓰기와F2닫힌상태검증을수리하고R1원본41파일을보존했다. L4R2 PASS9/0 및새독립095감사PASS. 동일계열공통편향은남으며외부계열가능시전제재검증을우선한다. L2/L4각max2·기존과거소진/임계보존·자동추가라운드/예산없음. 근거는 outputs/isaac-offline-096/analysis.json·hold-series.csv·recovery-host.json·analysis-host.json·local-copy-verification.json·native-audit-*.json·review/다.
