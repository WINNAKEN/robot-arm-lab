> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 106 — 관리자 WFP·QoS 조회 완료 / 실제 차단 위치 미확정

2026-11-02 KST. 사용자 `지금 조회창 다시 띄워줘` 응답 후 조회 전용 UAC가 통과했다. **[관측]** 실제 관리자 프로세스가 현재 NTP 목적지의 WFP 송수신 필터와 QoS를 읽었다. 보안·네트워크·시계 설정 변경과 실물 CAN 접근은0이다. 시간 정렬이나 새 시뮬레이션 수용을 얻은 것은 아니다.

원자료: [결과 JSON](../../outputs/ntp-path-read-106/result.json), [관리자 원결과](../../outputs/ntp-path-read-106/query-result.json), [OUT 필터](../../outputs/ntp-path-read-106/wfp-ntp-OUT.xml), [IN 필터](../../outputs/ntp-path-read-106/wfp-ntp-IN.xml).

## 확보한 관측

- 첫 조회는 UAC 포함16.375초/rc0, admin=true다. `192.0.2.10 → 192.0.2.10`, Wi-Fi 경로와 기존 Microsoft 주소 `52.231.114.183:123`을 확인했다. XML은 UTF-8 BOM이며 실제 parse에 성공했다. 최초 텍스트 보기에서 UTF-16으로 잘못 읽은 오류는 조회 실패가 아니며 원XML을 수정하지 않고 올바르게 파싱했다.
- OUT377필터 중 BLOCK15·PERMIT317·callout45개, IN1001필터 중 BLOCK24·PERMIT900·callout77개가 조회됐다. 이 숫자는 후보 정책 목록이며 실제 패킷의 차단/허용 횟수가 아니다. 기본/부팅/서비스·앱 격리 필터가 함께 있어 `BLOCK` 글자만으로 NTP 차단을 선언하지 않는다.
- 활성 QoS 정책 조회 결과는 빈 목록이다. 별도 활성 QoS 제한 정책을 원인으로 특정할 근거를 얻지 못했다. 드라이버 내부 정책까지 없다는 뜻은 아니다.
- WFP 필터99850은 `svchost.exe`·W32Time 서비스 SID·UDP 로컬123→원격123을 허용한다. `sc showsid W32Time`의 SID `S-1-5-80-4267341169-2882910712-659946508-2704364837-2204554466`과 조건이 일치한다. 필터99856에는 Wcmsvc NTP 허용도 있다. **[추론]** W32Time의 NTP 송신 허용 정책이 아예 없다는 설명은 현재 목록과 맞지 않는다.
- 최근90분 Security5152/5157 조회에서 조건에 맞는 이벤트를 찾지 못했다. 수집/감사 조건·버퍼 보존 여부를 인증한 결과가 아니므로 실제 drop 부재의 증거로 쓰지 않는다.
- 현재 바인딩20항목은104 시험 전 전체 맵과 정확히 같고 `nt_rtf64=true`다. BFE는Running으로 조회됐다. 등록 provider 이름이나 부팅 필터의 존재만으로 차단 원인을 귀속하지 않았다.

WFP는 여러 계층·하위계층·callout의 판정을 조합한다. 허용 정책이 있다는 사실만으로 최종 통신을 보장하지 않으며, 목록 조회를 실제 패킷 분류 이벤트로 취급하지 않는다. 근거: [Microsoft 필터 조정 규칙](https://learn.microsoft.com/en-us/windows/win32/fwp/filter-arbitration), [WFP 동작과 부팅 필터](https://learn.microsoft.com/en-us/windows/win32/fwp/basic-operation).

## 부가 조회의 실패와 보존

첫 helper의 부가 `netsh wfp show options`는 필수 `optionsfor`가 빠져 사용법만 반환했다. native rc0을 옵션 조회 성공으로 세지 않았다. 설치본 도움말과 [공식 명령](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/netsh-wfp)에서 `optionsfor=NETEVENTS`와 `show netevents` 인자를 확인했다.

이후 기존 이벤트 조회와 NTP 질의1회 대조를 준비한 별도 helper는 Windows Start-Process에서 약123.718초 후 사용자 취소 오류/rc1로 끝났다. `event-read/result.json`과 before/after 이벤트 XML이 없으며 계획한 NTP 질의도 실행되지 않았다. 의도적 취소인지 응답 만료인지 미확정이다. [원stderr](../../outputs/ntp-path-read-106/event-read/uac-stderr.raw)와 예약·helper·transport를 보존하며 자동 재발사하지 않는다. 이벤트 수집을 켜거나 trace를 시작한 적은 없다.

## 현재 판단과 다음 구분

**[미지]** 실제 drop 구성요소·NIC 출고·공유기/상위회선의 인과는 여전히 미확정이다. 104의 로컬 여러 NTP 서버 무응답/UDP DNS 정상·원격 별도 게이트웨이에서 응답 및 간헐 손실, 필터OFF 개선 미관측을 그대로 유지한다. 이번 읽기로 방화벽·QoS·Realtek 중 하나를 유일 원인으로 선언하거나 설정을 변경하지 않았다.

다음 후보는 [107 동일 PC의 별도 인터넷 경로 비교](107-alternate-network-ntp-comparison.md)다. 현재 승인된 조회 범위와 달리 사용자가 Wi-Fi 경로를 잠시 바꾸는 새 동작이므로 아직 실행하지 않았다. 같은 PC/NIC/필터·고정 NTP 주소를 유지하고 네트워크 프로필 차이도 기록해 호스트와 경로를 더 구분한다. 결과가 달라도 특정 공유기나 ISP의 차단을 곧바로 확정하지 않는다.

105의 시뮬 병렬 분석/사전점검과 자료감사PASS5/0은 그대로다. 새namespace 구현·native-ready·새45분·정지/42초 실행은 아직 없다. 원 게인/cap/물리기준·시간 gate·모델·모든 과거 실패/소진·실물 금지를 보존한다. 105의 한정74개 목록 SHA와 다른 작업자의 CAD22개를 확인하며, 전체5995개 재감사나 독립 OS/물리 수용은 주장하지 않는다.
