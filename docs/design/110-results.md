> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 110 — 같은 호스트 감독자 수리·검증 기록

2026-11-04 KST. 사용자 「결함두건을 포함해서 해결진행해」에 따른 진행 기록이다. **최종 A는 PASS5/0 유지, C는 R2 BLOCK4/1·2/2 종결, B/통합은 L2 BLOCK2/2다. 전체 구현·원격 재개 완료가 아니다.**

## 원래 두 결함의 처리

원109의 실제 보정량 5초 cap 및 pending launch 결함은 기존 실패·미해결·L2/L4 2/2 종결·소진을 그대로 보존했다. 원109 소스를 고쳐 R3로 재개하지 않았다. 새110은 Isaac PC 안에서 controller와 SDK를 같은 시간축에 놓고 OS 시각 setter/UAC 경로를 제거하는 설계다. 자식은 정상 사용자 CreateProcessW의 생성 순간부터 Job에 배속하고, 실제 handle 종료와 자식 수 0을 확인한다. A의 이 경계는 실제 비관리자 자식으로 독립 관측해 PASS했다. 원격 준비 B는 아직 구현되지 않아 두 결함의 **통합 대체 경로 수용은 미완료**다.

원108 실제 생성 entry에서 admission 다섯째 인자 누락도 확인했다. 새110 literal은 다섯째 인자를 전달하고 export만 None으로 보낸다. 원108 bytes는 수정하지 않았다.

## 로컬 구현과 검증

실제 mutable source 5개와 harness 1개만 작성했다. 계획상 8개 중 B의 bootstrap.py/test_bootstrap.py 두 파일은 없다. A의 winjob/test_winjob, C의 driver/config/test_driver와 status-only execute가 대상이다. execute는 B/통합 BLOCK 상태에서 run/controller를 거절한다.

- [관측] A HOST14+kernel10=24개 통과. fault subcase17을 시험 총수에 중복 합산하지 않았다.
- [관측] C 최종44개 통과. 실제 동일 호스트 OS clock 자식·PowerShell/Python print/sleep 자식만 사용했다. 합계68개는 전체 108 HOST587 재실행이나 Isaac 수용을 뜻하지 않는다.
- [관측] Python5개 compile과 config JSON parse 통과. config의 비활성 deadline은 정확 int0이며 게인64/16·cap·097 후보·모델·원 물리 및 시간 기준을 유지했다.
- [관측] A 독립 L4 R1 PASS5/0. C R1 BLOCK2/3의 원본 source/관측/raw/판정을 보존하고, C만 수리해 최종 R2에 제출했다. A/config/execute는 R1 동결 지문 그대로다.

C 수리 대상은 복사/압축해제 등 실제 파일 작업의 기한 소유 누락, 자식 실행 후 helper 예외가 NOT_STARTED로 표기되는 문제, process.json 발행 실패 시 이미 알려진 clock 자식 PID/종료 사실이 유실되는 문제 세 가지다. 회수 전체600초·내부300초·업로드/압축해제 각120초와 전역 원끝 중 작은 기한을 독립 Fence가 소유한다. 위임 후 불명 실행은 UNKNOWN이며, 알려진 clock process 사실은 메모리 실패 envelope로 보존한다. 부분 process.json이 그 사실을 덮지 못하게 했다. 작성자 시험만으로 폐쇄 판정하지 않았다. 최종 비작성자는 실제 자식의 고정 handle/FILETIME 및 실제 NTFS 파일잠금 대조로 실행상태·알려진 clock 사실 보존 두 수리를 폐쇄했다.

실제 blocked IO를 짧게 환산한 HOST 대조와 production 600/300/120 상수 검사를 구분한다. 실제600초/120초 경과 실험이나 SDK 동작을 수행한 것으로 쓰지 않는다. 동일계열 비작성자 폴백의 공통 편향도 남는다.

## 최종 C 판정과 소진 범위

[주 검토 R2](../../outputs/single-host-controller-110/review/AC-L4-r2.json) SHA `3e82823f65c088943539df4a215df8933660608de9ea509832e6fbfa78d74572`, [보조 R2](../../outputs/single-host-controller-110/review/AC-lens-r2/report.json) SHA `2d6868557ec573bb7bdeaa42e444e24ff5e1bd895f90c57ccb26850a430d85ae`다. A의 새 회차 소비는0이며 내용 합계9/1은 A5/0+C4/1일 뿐 B/통합 수용이 아니다.

원 F1의 복사/업로드/압축해제 본문은 실제 OS FileIO 차단에서 원 global 끝에 producer exit124로 폐쇄됐다. 하지만 회수 시작 wall/mono/end를 고정한 뒤 `_operation_end`가 runtime-budget을 읽고, 그 읽기가 끝나야 outer Fence가 켜진다. 실제 읽기를 막으면 MainThread만 존재하고 고정 global 끝+300ms에도 producer가 살아 있어, 관측자의 보유 handle로93 종료했다. SDK/body 진입은0이다. 동일 입력을 원 R1 동결 소스에 적용하면 그 새 직접 읽기에 닿지 않고 정상 closed recovery0으로 끝났다. R1 session_now의 다른 metadata 읽기가 전혀 없었다는 뜻은 아니다. 같은 HOST 서비스 seam과 새 direct read의 수리 전후 대응이다.

따라서 `110-AC-L4-R2-F1`, FS lifetime class union2/open1·전체 C instanceunion4/open1/class3이다. 원3건 처분과 새1건을 구별했다. 비작성자는 수리→새 동일class 생성에 따라 **현재 C의 FS owner 배치·검증 source만 EXHAUSTED**로 종결했다. A·Windows·파일시스템·시뮬 도메인 소진이 아니다. 원 finite-stage union2/다음3, raw/restoration/원109 source 소진과 임계는 변경하지 않았다. C의 다른 두 class는 명시 폐쇄 내용 자산으로 보존한다.

주 검토1594.047초/2700, 보조1432.39초/2700이었다. 주 검토의 [manifest](../../outputs/single-host-controller-110/review/AC-main-r2/evidence-manifest.json)는320개 정확 입력/원자료/observer/frozen scaffold를 결속한다. 별도 동결 R2 재현 receipt의 observer3개는 모두0이었다. 이는 새 round나 native 수용이 아니다.

## 검토 횟수와 남은 관문

L2 R1/R2는 A/C의 독립 로컬 구현만 허용했고, B/통합은 같은 REMOTE_BOOTSTRAP_LIFECYCLE_UNOWNED 결함1건으로 최종 BLOCK6/2다. 후속 요청이 원2700초 끝을 지난 뒤 도착해도 initial Fence20 아래 claim 읽기를 할 수 있는 누락이다. [구체 보완안](110-bootstrap-global-end-repair-proposal.md)은 caller의 고정 원격 end를 최초 읽기 전에 넘겨 initial=min(now+20,expected_end)로 묶고 claim SHA/nonce/동일 원끝을 검증한다. 이 문서는 구현/실행 권한이 아니다.

계획에 적은 B/통합 L2 최대2회가 모두 사용되어 그 범위만 추가1회 검토할지 질문했으나 승인 응답은 없었다. 그 질문만으로 새로 종결된 C를 재개할 수 없다. A/C L2와 원109 회차·소진을 재설정하지 않는다. C 최종 L4 R2도 2/2이며 추가 R3는 없다. 원격 B/통합 코드검토 PASS와 typed native 권한 없이는 첫 원격 실행을 시작하지 않는다.

## 시간과 경계

A 구현은 기록상 약552초/1500초다. C R1 약1100초 뒤 R2 잔여399초를 기록했다. 최종 두 소스 mtime은01:00:08UTC로 잔여기한01:01:31UTC 전이고 이후 소스 수정은 없다. 최종44개 회귀검증·동결은01:03:24UTC에 완료했다. 전체 구현과 최종 검증이 누적25분 안이었다고 주장하지 않으며 [시간 관측](../../outputs/single-host-controller-110/C-authoring-budget-observation.json)을 남겼다. 원격45분과 별개다.

이번110의 SSH·원격실행·SDK/SimulationApp·시각변경·UAC·실물CAN·급전·flash·모터·설치·물리보정은 모두0이다. 새45분도 시작하지 않았다. 원109의11월3일 offset 관측은 역사값으로 유지하며 현재 offset으로 재사용하지 않는다. 기존 물성가정·링보류·정착15/velocity-only 소진·PD/포화UNKNOWN·moving-root 독립교정NOT_DONE은 보존한다.

후속 [111 구체 제안](111-lifetime-redesign-proposal.md)은 이미 검증한 원끝을 첫 managed read 전에 scalar로 전달하고 모든 phase가 파일 읽기 전 소유자를 켜는 새 구조다. 제안만 저장했으며111 source/검토/실행/승인0이다. 이전 절차 PASS나 회차를 승계하지 않는다. 새 착수는 원 미해결 답·신선 계보/예산·사용자 권한이 필요하다(DEV_PRINCIPLES 261~267).

정본: components-freeze-r1/r2.json, C-host-summary-r2.json, review/AC-L4-r1/r2.json, 원 L2-r1/r2.json. 과거 실패는 before-* 동결 사본과 원 관측/재현 wrapper·receipt에 남겼다. 공유 인계는 이전 bytes를 유지해 덧붙이고 CAD/MP10 tracked22는 수정·stage하지 않는다. 외부 게시·push는 하지 않는다.
