> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 030 / PB-20261025 — 실제 브라우저·HTTP 일정 검증

## 범위와 검토 예산

사용자가 제품 문의를 끝내고 제어 작업을 계속하도록 요청했다. 028 인계 기록의 다음 항목인 실제 웹 화면의250ms 조회/50ms 갱신과HTTP지연을 부품 없이 검증한다. 새 L2최대2/L4최대2를 첫 검토 전 선언한다. 028수용/027PRODUCT·EXHAUSTED 및PA두반례·다음추가독립실측+작성자수용 동일class1즉시EXHAUSTED 임계를 그대로 이월한다. 기존startup/firmware firstfault 임계도 불변. 중앙 외부계열 검토 도구 차단은NOT_RUN/우회하지 않는다.

소유는 새 `tests/phone_browser/`, `.dev/phone-browser-evidence/`, 이 계획 및 인계색인이다. productionHTML/app.js/서버/제어코어/프로필/기존시험·수용산출물은 수정하지 않는다. 코드 결함을 발견하면 기록하고 class/임계에 따라 판정하며, 시험 편의를 위해 product 타이머·기한·재시도·승인값을 바꾸지 않는다. 기본 물리/normal/hardware/measuredfalse,100pulse상대각만, 링미해결보류 유지. 동시MP6/029와모델링파일은 무수정이다.

## 구성과 증거 경계

1. 이미 설치된 Playwright와 Chrome을 별도 임시프로필의 headless 시험 프로세스로 실행한다. 실제 production HTML과app.js의 원본 바이트를 로컬 Node HTTP 서버가 제공한다. 기존 Chrome 사용자 세션/로그인·탭을 사용하지 않고 설치도 하지 않는다. 모바일 viewport/touch는 에뮬레이션이며 실제 휴대폰 검증이 아니다.
2. 로컬HTTP `/api/session`, `/api/status`, `/api/command` 어댑터는 시험용이다. pairing응답과 HTTP계층은 fixture이며ESP-IDF 실제HTTPhandler/Origin·큐·deadline 검증을 대체하지 않는다. 실제 browserfetch→실제 loopback HTTP→실제 wire parse/Owner/Boot/Run/Gate/codec→FakeCAN을 관측한다. 기존HTTP/runtime SDKstub 시험은 별도 유지한다.
3. 기존AngleFixture/BootFake는 소스무수정 exact-fragment 재사용으로 새 C++ bridge에 넣는다. 시작은NeedsMaintenance Boot이며 실제DOM 버튼이 JS명령namespace를 만든다. JS에seq/lease/authority를 주입하거나 PhoneControl을 교체하지 않는다. 실제Owner snapshot에 표시용 positions등을 추가할 때 값의 원본/fixture 여부를명시하고 ready/phase/capability/identity를위조하지않는다.
4. C++ bridge의 `W absolute-ms`는 원래fakeclock에서 단조 target까지1ms step한다. Node의 단조 경과시간과 연결해 실제경과시간에 따라Owner가계속poll되게한다. 타이머 pump와 각 요청은 하나의순차stdio채널로직렬화한다. proof·lease는오직원래코어규칙으로만갱신한다. 명령처리전favorable() 같은시간/포트정리 편의처리를넣지않는다. clock동기기준/요청·응답monotonic시간/원본wire/core결과를기록한다. 이것은 모의port/host scheduling이지 실제ESP32실행시간증명이아니다.
5. production의 hardcodedStop `http://192.168.4.1:8081/api/stop`은 시험 browser route가 오직loopback의 별도Stop HTTP경로로전달한다. 원래요청URL·실제fixture도착을둘다기록하고 실제LAN/device에는보내지않는다. 그외외부요청은차단한다. 이경로는 production코드무수정하에Stop호출연결을검증하는 fixture redirect이며실제보드CORS/라우팅/네트워크독립성수용이아니다.

## 실행 시나리오와 이진 판정

브라우저 DOM을 통해 pairing→유지보수/무부하확인/토크해제→허가반납/운전/선택축허가→명시Handoff→Acquire→숫자입력deg/rad→Stop을요청한다. 화면의부팅/core상태/오류·버튼활성화를실제snapshot/로그와대조한다. 타이머는production250/50ms를그대로실행하고 실제조회/renew간격을기록한다. 새Ready snapshot이후admission은별도경계이므로매요청결과를평가한다.

- 일반일정: 적어도하나의실제DOM 숫자행동이정확히1개FD100pulse를만들고실제renew와완료/Stop관측으로이어지는조건부성공사례를확보한다. unmeasured fixture는인계가능/숫자버튼비활성·v2없음·FD0. 양축·단위는기존028시험이포괄하므로모든브라우저일정에서성공을보장하지않는다.
- 지연: Arm또는Ticket응답을600ms이상보류해상태/제어권/숫자context경계를관측하고v2추가전송/FD없음을확인한다. Handoff응답보류중Stop을DOM으로요청해Acquire재생성이없고늦은응답이권한을복구하지않는지확인한다. Status응답단절/지연·실제browser offline전환후이동비활성/명시재연결필요를확인한다.
- 실패일정: 실제코어Busy/Denied/Expired이면그대로기록한다. 해당명시사용자행동에대한자동재시도·자동권한획득·추가FD가없어야한다. 기존20ms경계등은안전거절관측이며새성공으로라벨하지않는다. 안정된성공사례가없으면후보수용으로표현하지않고실패·제약을보고한다. 유리한fixture부팅시점위상선택은원본로그에명시하며production타이머는변경하지않는다.
- 실제background visibility는headless브라우저에서검증가능하면기록하고,불가하면NOT_RUN으로둔다. synthetic visibilitychange를실제모바일background로표현하지않는다. 실제offline은browser network emulation이며전화기무선단절그자체가아니다.

실제pageerror/consoleerror, DOM버튼상태, 요청원문·응답·coreframe count, scenario별accepted/denied/cancelled 판정을보존한다. 모바일viewport screenshot을출력해직접확인한다. 전체시간/요청수/프로세스종료상한을두고 browser/server/child를finally에서정리한다. 실패한처음시도도보존하며무한재시도/전체suite재실행으로유리한결과만선별하지않는다.

positive 후검증장치의실제negative control3개: 잘못된targetDOM asset, 원래Stop URL이서버로전달되지않음, 숫자실행후FD카운트누락/불일치. 구문·컴파일성공후명시검사실패로검출해야하며실패를성공으로취급하지않는다. 장치교란은fixture에만한정하고production수정은하지않는다. 기존028/027/UI/HTTP/runtime/C++회귀실행과baseline/frozenhash로무변경을확인한다.

## 수용·종결

비작성자L2→새시험구현/실행→비작성자L4로실제소스/소비경로·negative control·로그/스크린샷을대조한다. PA추가동일class수용반례면잔여회차무관즉시중단/사용자처분이며이단위이름으로원장을초기화하지않는다. 네트워크fixture의성공은실물프로필승인·ESP32/WiFi/실제CAN/토크/기계정지수용이아니다. 실제SDKtarget/휴대폰하드웨어/장치/flash/출력/구매/CAD/링은제외한다. 종결시HANDOFF/SESSION/BACKLOG/LESSONS/구조지도와소유범위로컬commit·push없음을기록한다.
