> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 104 — 실제 필터 비교: 효과 미관측·전체 바인딩 복원 / NTP 경로 미해결

2026-11-02 KST. **[관측]** 사용자 `지금 다시 띄워줘` 응답 후 동일 검토 코드의 Windows 관리자 승인이 통과했다. `nt_rtf64`를 끈 상태에서도 NTP 요청 3회가 모두 시간 초과였다. 실행기는 켜짐 상태로 복원했으며 처음과 마지막의 전체 20개 바인딩 맵이 정확히 같다. **시간 정렬은 미완료이며 정지 검증·42초 진단은 NOT_RUN이다.**

## 실제 비교와 복원

실행 자료: [실제 실행 폴더](../../outputs/ntp-transaction-104/uac-ready-attempt-2/outputs/ntp-transaction-104/execution/), [controller 결과](../../outputs/ntp-transaction-104/live-retry2-controller.json), [현재 결과 정본](../../outputs/ntp-transaction-104/result.json).

| 단계 | 필터 상태 | 실제 결과 |
|---|---|---|
| A0 | ON | 3/3 시간 초과, 표본별 약2초 |
| B1 | OFF | 3/3 시간 초과, 표본별 약2초 |
| A1 | ON 재현 | NOT_RUN — B1 실패 |
| C1 | 조건부 영구 OFF | NOT_RUN — 인과 수용 실패 |
| 실패 후 복원 | ON | Enable job Completed/errors 없음; 전체 맵 원복 |

**[관측]** controller 약48.157초/rc1. actor 원결과 `UNKNOWN_OR_RESTORED_NO_ACCEPTANCE`, 오류 `B1 not three valid replies`, `inflight_unknown=false`, `diagnostic_faults=[]`, 영구off 수용false다. Disable 1회와 복원 Enable 1회 모두 OS job 종료와 오류 없음을 확인했다. OFF 맵은 초기 맵에서 `nt_rtf64` 한 항목만 다르고 최종 맵은 초기20항목과 정확히 같다. `001-map-stdout.raw`, `008-map-stdout.raw`, `014-map-stdout.raw`, `007-disable-*`, `013-enable-*` 참조. 후속 OS 조회에서도 `nt_rtf64=true`였다.

**[추론]** 이번 시험에서 Realtek 필터를 끄는 효과는 관측되지 않았다. **[미지]** 해당 드라이버의 모든 가능한 영향까지 배제하지는 않는다. 102의 마지막 Realtek Upper 관측은 실제drop이나 NIC출고 증명이 아니다. 원인 수용 기준은 완화하지 않았고 OFF 유지나 동일 시험 자동 재발사는 하지 않는다.

## 설정을 바꾸지 않은 후속 진단

원자료: [post-trial](../../outputs/ntp-transaction-104/post-trial/).

- **[관측]** 로컬 Python의 Microsoft·Google·Cloudflare UDP123 질의는 모두 시간 초과였다. fresh/zero transmit timestamp와 NTPv3/v4를 비교했다. 로컬 .NET의 Microsoft·KRISS fresh v3 질의도 시간 초과였다. `local-server-comparison.json`, `local-classic-servers.json`, `local-v3-v4.json`, `local-dotnet-fresh.json` 참조. 게이트웨이 UDP123도 시간 초과였지만 게이트웨이가 NTP 서버라는 주장은 하지 않는다.
- **[관측]** 같은 로컬 프로세스의 DNS UDP53 질의는 게이트웨이와 `8.8.8.8` 모두 응답/transaction ID 일치였다. 일반 UDP 전체 차단으로 판단하지 않는다. `local-dns-udp-control.json` 참조.
- **[관측]** 원격 PC의 Microsoft fresh v3/v4 요청은 모두 `52.231.114.183:123`에서 응답했고 origin timestamp가 각 요청과 일치했다. 해당 요청 계열을 서버가 받을 수 있음은 확인했다. 단, 앞선 원격 stripchart는 2회 시간 초과 뒤 1회 응답했고 오래된 로컬 timestamp 재생 요청도 시간 초과였다. 원격 간헐 손실을 숨기거나 모든 원격 질의가 성공했다고 쓰지 않는다. `remote-fresh-stamp.json`, `remote-classic-v3-v4.json`, `remote-w32-current.json`, `remote-exact-request.json` 참조.
- **[관측]** 로컬은 `192.0.2.10 → 192.0.2.10`, 원격은 `192.0.2.10 → 192.0.2.10`로 둘 다 Wi-Fi다. 서로 다른 게이트웨이이므로 원격 성공을 동일 공유기 경로의 대조군으로 취급하지 않는다. 로컬 Ethernet은 Disconnected, 공인 IPv6 기본 경로도 없다. `local-context-*`, `remote-context-*`, `existing-interface-paths.json` 참조.
- **[관측]** ActiveStore 활성 송신 차단 규칙 두 개는 sandbox SID1003의 loopback UDP/TCP 규칙이었다. 진단 프로세스는 winna SID1001/FullLanguage/비관리자였다. 해당 규칙이 공인 NTP 주소를 차단한다는 근거는 없다. Windows Defender가 SecurityCenter에 등록돼 있다. 모든 WFP callout·드라이버의 차단 부재까지 증명하지는 않는다. `active-outbound-blocks.json`, `local-identity-stdout.raw`, `local-context-*` 참조.
- **[관측]** 상세 WFP 조회는 비관리자 ERROR_ACCESS_DENIED였다. 조회 전용 UAC도 약125.547초 뒤 Windows 취소 오류/rc1로 끝나 `wfp-query-result.json`이 없다. 의도적 취소/응답 만료는 미확정이다. QoS 조회도 접근 거절이었다. 조회 실패를 정상 조회나 차단 없음으로 쓰지 않는다. `wfp-uac-*`, `wfp-read-only-query.ps1`, `existing-interface-paths.json` 참조. 추가 창은 사용자 응답 가능 여부 확인 뒤 띄우며 자동 반복하지 않는다.

**[추론]** 로컬 호스트 또는 그 NTP 네트워크 경로의 문제로 범위를 좁혔다. **[미지]** 실제drop 구성요소·NIC출고·공유기/ISP 인과·현재 두 PC 정렬 수용은 미확정이다. 여러 서버에서 실패해 서버 주소만 바꾸는 수리는 아직 근거가 없다. 필터·방화벽·VPN·공유기·시계 설정을 추측으로 바꾸지 않았다.

## 보존과 다음 단계

기존 L2R1/L4R1 PASS5/0·각1/2, 작성자 새배선12·독립 재사용포함24·실상속통합8case 및 gate/quote/bootstrap/receipt/timeout 검토를 유지한다. 이번 소스 수정·검토 회차 추가0이며 실제OS 결과의 독립 수용은 수행하지 않았다. 동일계열 비작성자 폴백 공통편향은 남아 있다.

source-freeze SHA `ab73bf3f9d76d6937e371431a860a49c745d0c182899f7bd5b1b8cfd160a1be2`, L4R1 SHA `1385ce9227cf015a1f5089482bb5ff566e378008452891e67cfee3c73881f9a7`. 실제 실행 뒤 11개 동결 입력 SHA 일치를 재확인했다. 원103 최종BLOCK·각2/2 종결·monitor2→다음3·restoration I/O2→다음3 및 옛099 raw/time 계보·임계는 그대로다.

첫104 UAC 취소·원request/raw/controller 실패와 재요청 입력 영수증을 보존했다. 이전 result/본 문서/공유인계 원문은 [before-report](../../outputs/ntp-transaction-104/post-trial/before-report/)에 바이트 그대로 저장했다. 아래 이전 기록 역시 당시 이력이다. 실제 비교는 새root에서 한 번 수행했으며 옛103/099 재발사·실패 marker 삭제/reset은 없다.

후속 설정 변경·resync·시계 보정0회. 실물CAN·급전·flash·모터·보정·SDK/native/physics/PNG0이며 게인64/16·cap·모델·원기준·097후보·물성가정·링보류와 기존 실패는 그대로다. 다른 작업자의 MP10/J5 tracked22개 SHA가 이전 기준과 같았다. 외부게시·push는 하지 않는다.

현재 승인 범위의 조회 전용 WFP·QoS 상세 확인에는 실제 Windows 관리자 동의가 필요하다. 사용자 readiness 응답 후 조회를 이어가며 관리자 우회·창 자동반복은 없다. 조회로도 위치가 안 좁혀지면 같은 로컬 PC를 별도 인터넷 경로에서 비교하는 절차의 영향과 범위를 구체화한다. 새 네트워크 설정이나 새 시계 보정 방법은 해당 범위 승인 뒤 진행한다. 새 시뮬레이션은 별도namespace·필요검토·첫 원격부터 새45분 명시승인 경계를 유지한다.

공식 서버 확인 자료: [KRISS 현재 NTP 안내](https://www.kriss.re.kr/menu.es?mid=a10305000000), [KRISS 구서버 종료 공지](https://www.kriss.re.kr/board.es?act=view&bid=0002&list_no=63463&mid=a10503000000&nPage=8), [Google 공개 NTP](https://developers.google.com/time/faq), [Cloudflare NTP](https://developers.cloudflare.com/time-services/ntp/usage/), [Microsoft 시간서비스 명령과 포트](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/Windows-Time-Service-Tools-and-Settings). 공개 서버 질의는 진단이며 OS provider 설정 변경·프로그램 설치·물리 제어용 시각 인증을 뜻하지 않는다.

---

# 이전 기록 — 단일 로컬 실행기 검토 통과 / 첫 Windows 관리자 승인 취소

2026-11-02 KST. 사용자자율진행·기존nt_rtf64조건부수리승인은유효하다. 작업전체를10분마다중단하지않는다. 103의실패한파일watchdog진입점을제거한104새배선은L2R1 PASS5/0, L4R1 PASS5/0을받았다. 작성자새배선12시험·독립재사용포함24시험·실상속통합8case·gate12/actor4·bootstrap/Windowsquoting/receipt/timeout-prefix검사를수행했다. 코드/HOST수용이며실제OS A/B나시계정렬PASS가아니다.

source-freeze SHA `ab73bf3f9d76d6937e371431a860a49c745d0c182899f7bd5b1b8cfd160a1be2`, L4R1 SHA `1385ce9227cf015a1f5089482bb5ff566e378008452891e67cfee3c73881f9a7`. 원103source/최종BLOCK·각2/2종결/열린monitor class2→다음3/restoration-I/O2→다음3·옛099계보는보존하며104이름으로폐쇄/초기화하지않았다. 동일계열비작성자fallback의공통편향은유지한다.

검토된104 execute를1회호출했다. 시작전전source/검토/실사용자승인핀을확인했고,새execution/request.json을생성한뒤UAC를요청했다. Windows Start-Process는약125.329초후 **The operation was canceled by the user** 로rc1을반환했다. 의도적인사용자취소인지응답만료인지까지이메시지로확정하지않는다. actor결과와phase/map/probe파일이전혀없으며UAC에서actor시작전중단했다. 최상위controller는result.json부재를FileNotFoundError/실패로남겼고PASS로덮지않았다.

실제binding변경0/방화벽·Tailscale·NTP설정변경0/SDK·native·실물CAN0. 실제A/B/A/C·시간정렬·정지·42초진단은NOT_RUN이다. 102후보관측을Realtek원인확정으로승격하지않는다. 로컬NTP상태는마지막102관측의미동기화이며현재두PC상대차이는새로인증하지않았다.

작업범위승인을다시요청한것이아니다. Windows관리자창에‘예’를누를수있는지를질문창으로확인중이며동의대기때문에추가UAC를무한반복하지않는다. 응답하면동일검토바이트로재개한다. 원execution/request/취소raw/실패는지우거나reset하지않는다.

재요청준비는`uac-ready-attempt-2/`의독립실행root다. 실제11개동결입력·원L4PASS·freeze를바이트동일하게복사했고,검토된기존`--root`인자로validate가통과함을확인했다. **source/계획변경0**,새코드/103R3/old099재발사가아니다. `uac-retry-input-receipt.json`에각입력SHA·원실패SHA·검증핀을보존한다. 아직새UAC/actor는실행하지않았다. 새root의execution네임스페이스가비어있고동의후새controller PID/nonce로기록한다.

정본outputs/ntp-transaction-104/result.json·execution/launcher-stderr.raw·live-controller-*.raw·uac-retry-input-receipt.json·review/L4-r1.json. 사용자readiness응답이후결과가있으면그후속기록을우선한다. 같은목적의보안우회·자동관리자승인은없다. 새시뮬45분은별도승인경계이고실물CAN금지는계속유지한다.
