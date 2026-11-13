> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 098 — 실행기 검토 통과 / 최초 시계 인증 실패로 native 미실행

2026-11-01 KST. 사용자 승인 범위의 새 실행기를 src/simulation/hold_diagnostic_run/에 통합했다. 아래 최초 작성자 준비 기록은 원격 실행 전의 이력이다. 최종 L2/L4는 각각 2/2 종결, L4 R1 BLOCK5/4 → R2 PASS9/0이다. 새45분은 최종 검토 후 첫 원격 실행 직전에만 활성화한다. 설치·급전·모터·flash·실물보정·시스템 설정 변경·학습·외부 업로드도 없다. hardware_approved=false다.

097의42초 후보 바이트를 사용하며 원0~34초4081명령과33~42초1081개 전체9목표 고정을 유지한다. 5040step/5041관측/421PNG는 계획 수량이며 실제 관측이 아니다. 원34초 checkpoint와 원위치0.5°/속도1°/s 등 기준, 게인64/16·cap·가정 물성을 보존한다. sdk/scene/workspace 등10파일과 recovery.py는096과 동일하다. validate.py는verify_workspace의실행program결속helper만명시예외로수정했고그외AST/물리기준은원본과동일하다. test_scene은 정확42초 수량과098 결과 namespace만 바꿨다.

최초작성자/비작성자HOST253(회수89/scene29/활성화53/시계·실caller64/분석10/실native entry8), Python26파일compile/PowerShell parse/기존5808파일SHA는통과했으나L4R1은실제 호출경계4건으로BLOCK5/4였다. 원source18/하네스13/당시HOST·freeze·계획/결과45파일을review/l4-r1-preserved에보존했다. 수리추가HOST23에는새UUID재발사/prepare차단,NOT_STARTED실패archive,거절clock raw/원오류보존·재조회0,전체actualprepare→45inputsnapshot→46entrybundle과5개악성/원helper반례를포함한다. 시간검사는원wall-only900초및600.125초반례와strict600경계를유지한다. 최종합계/compile/보호게이트는새host-summary/source-freeze-r2에결속한다. 모두HOST/과거자료재생이며실제원격/물리수용이아니다.

전역2700초는 최초UTC+같은PC의monotonic anchor로 소비한다. wall은일관성만확인하고예산시각은anchor의expectedUTC만쓴다. 회수는추가exclusive startMono/endMono+600에결속하고timeout은각300·회수mono잔여·전역잔여의min이다. remote UTC/Win32 TickCount64는SDK/site시작을끄는기존Python의표준라이브러리조회(-I -S -B)만사용한다. 이조회는SimulationApp/native목적실행이아니다. 인증된clock증거와remoteUTC+2초를입장상한으로쓰며,입장여유1380/1680초의등호는거절한다.

L2 R1 BLOCK6/3·F1 fixture수량/F2 wall기한을수용했다. 진행중R2에서600.125초잔여F2와원096보고서덮기F3도수용했다. R2완주전작성자의1회semantic계획대상갱신은비작성자절차판정에따라중간바이트/반례/사유를보존하고같은상한·같은round에서재핀했다. 최종L2 R2 PASS9/0,누적3·미해결0이나실구현폐쇄는L4확인대상이다. L2 2/2종결/L4 0/2. 같은계열공통편향과과거실패/소진을유지한다.

코드검토후단일활성화·첫원격OS조회부터새45분,import1→정지1수용→motion1순서다. 각목적실패도소비하고retry0이다. source18/검토하네스/모델/후보/기준을execution-freeze에묶고config의deadline숫자한토큰만활성화한다. 코드/모델/기준변경,예산reset/추가native없음. 늦으면motion NOT_RUN이다.

실행 결과, 원봉인 감사, 33~42초 진단, 영상과종료PID/lock은아직미확인이다. 34초실패가남으면42초에서진입해도전체consumer 실패를보존한다. PD/포화UNKNOWN·moving-root독립교정NOT_DONE·물성가정/링보류·자기충돌OFF/바닥ON·정착15/velocity-onlyEXHAUSTED는유지한다.

이 아래에 검토/실행 데이터만 추가하며, 코드나원후보를 사후 수정하지 않는다.

## L4 R1 처분과 R2 범위

F1 localpurpose각1 marker, F2 native전거절시원로그누락, F3 clock거절raw누락, F4 canonical52 workspace와approved42실행결속충돌을수용해수리했다. F4는비작성자의한정범위판정에따라원계획을보존하고추가절로verify_workspace helper 예외만명명했다. canonical52의6241path/cloud/모델검증은그대로이며42실행후보는첫9segment+동일목표8초의정확파생만허용한다. source.scene/SDK/다른validate함수·모든수치기준은불변이다. L2 2/2상태는유지하고새L2/R3를발사하지않는다. L4 R2가최종코드검토이며이후사후runtime감사는작성자범위다.


최종 작성자 게이트: **HOST276/compile27/PS parse/보호5808 PASS**, R1 보존45파일 전체hash 일치. 이 게이트 당시 원격/native/production45는0이었다. 공유HANDOFF에는진행중다른세션의938B공지커밋f06f06c가덧붙었고,원문을되돌리지않고별도shared-base로보존했다. 원초기HANDOFF바이트도그대로prefix로남는다.

최종 비작성자 R2는 독립 HOST276, R1 네 경계의 실제 함수 재현 폐쇄, 보호5808/R1보존45 전수 SHA, source18/harness14 고정을 확인해 **PASS9/0**으로 종결했다. 판정 JSON SHA256은 6999f6ef182d0d13efcb934cff2e96777dd750b2a7a7b503a5c50fd64df08637이다. L2/L4 각2/2이며 추가 R3 또는 사후 독립 runtime 검토 슬롯은 없다. 이후는 승인된 단일 실행기와 작성자 원봉인 감사·분석·영상 및 데이터 인계만 허용한다. 실제 물리 수용은 이 코드 검토가 보증하지 않는다.

## 단일 원격 실행 결과

최종 검토와 로컬 preflight 통과 후 `execute.py --review-round 2`를 **1회** 실행했다. 새2700초는 2026-11-01 **10:20:16.532658~11:05:16.532658 KST**로 활성화됐으며 config의 deadline 숫자 한 토큰만 바뀌었다. budget/READY/실행 source18/검토 harness14 결속은 실행 후 로컬 대조도 통과했다. 이 활성화는 실패로 소비됐고 삭제·reset·재조회·재개하지 않는다.

[관측] 첫 OS 시각 조회는 SSH 종료0·유효 JSON으로 응답했고 그 표본의 Kit 수는0이었다. local send→receive는9.34278392791748초, monotonic 경과는9.34399999998277초였다. 원 코드가 계산하는 offset 가능 구간은 **[-0.3801445026397705, +8.96663942527771]초**로, 양 끝이[-1,+1] 안에 있어야 하는 시계 인증 조건을 거절했다. 이 구간은 실제 PC 시계가약9초 어긋났다는 측정값이 아니다. 원격 시각은 local receive보다약0.378초 전이지만 실제 offset과 SSH/네트워크/PowerShell/Python 시작 비용을 단일 표본으로 분리할 수 없다. PowerShell CLIXML progress stderr도 바이트 그대로 보존했고 종료0/유효 응답과 분리했다.

실행기는 `COORDINATOR_FAILED: ValueError('Remote clock offset uncertainty exceeds one second')`·종료1로 멈췄다. 이 실패는 prepare/upload/supervisor/원장예약/SDK API/SimulationApp보다 앞이다. 새 runs 디렉터리·목적 attempt·native terminal·session-clock 인증서는 생성되지 않았다. import0/정지0/motion0, 물리step0/새PNG0/CAN0이다. 정지 검증·42초 진단·회수 exporter 원격 성능·원봉인 native 감사·새 영상은 모두 **NOT_RUN**이다. 새 worker PID/lock은 생성 경로에 도달하지 않아 종료 확인 대상이 없다. 단일 시각 표본의 Kit0을 이후 전체 PC 상태 확인으로 확장하지 않는다. 추가 원격 closeout도 보내지 않았다.

원래42초 후보와 게인64/16·cap·물리 기준·모델은 불변이며, 095/096/097 실패/원자료와 정착15·velocity-onlyEXHAUSTED·PD/포화UNKNOWN·moving-root 독립교정NOT_DONE도 그대로다. 원 응답·local UTC/monotonic·실패 packet·최초 chain/budget은 `outputs/isaac-hold-diagnostic-098/`에 보존했다. `runtime-diagnosis.json`은 작성자 로컬 원자료 진단이며 새 비작성자 runtime 검토나 물리 수용 판정이 아니다.

## 남은 작업과 재개 조건

42초 물리 진단은 미완료다. 다음 수리 대상은 물리 제어가 아니라 **프로세스 시작 비용이 섞인 단일 clock query의 인증 계약**이다. [추론] SSH/PowerShell/isolated Python 시작 비용이 표본 구간을 넓혔을 수 있으나 성분별 원인은 미확정이다. 다음 별도 계획에서는 ±1초 시계 조건·기존 게인/cap/물리 기준을 유지하며, 시작 비용과 시각 표본 구간을 분리할 방법 및 느린 전송/clock jump/재조회 금지 경계를 먼저 설계·비작성자 검토해야 한다. 098의 source/harness를 사후 수정하거나 남은 벽시각으로 다시 발사하지 않는다. 이번 L2/L4는 각2/2 종결이며 새 수리·검토·원격 실행은 이번 결과로 승인된 것으로 간주하지 않는다.
