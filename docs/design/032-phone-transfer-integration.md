> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 032 PT-20261025 — 명시 인계 예약의 actual Owner/HTTP/웹 연결

사용자 ‘좋아 계속 작업해’는031 후속 실제Owner·웹 연결을 허용한다. 실물/normal/hardware/measuredfalse,100pulse상대각만,링 unresolved/deferred,실물/flash/구매/출력/CAD 제외. 031 MODEL_ONLY 수용과030 PB-R1-1 OPEN/BLOCK은 과거정본 그대로 보존한다. 새 범위 L2최대2/L4최대2를 첫 검토 전 선언. 기존 PA 역사/다음추가 독립실측+작성자수용 동일class1 즉시EXHAUSTED와startup/SB/firstfault 충분다음임계 이월, 번호변경으로원장초기화없음. 외부계열 중앙차단 NOT_RUN/우회없음.

## 생산 연결 설계

기존 v1 Op enum 값/legacy Handoff·Acquire 흐름을 보존하고 append-only `handoff-acquire`, `handoff-result`를 추가한다. 기존 POST /api/command를 써서 새 unauth GET 또는700ms long-poll을 만들지 않는다. runtime exchange50ms/HTTP250ms 제한 유지. Result에 transfer_id/state/generation/pending_until/grant_at/lease_until/sequence_floor를 추가하고 HTTP bounded JSON과 새 시험 bridge가 동일 필드를 직렬화한다. 실제HTTP SDKstub에서 추가필드와 listener/auth/path/timeout을 검사한다. 기존 status는권한결과를추정하는통로로쓰지않는다.

예약은 Owner의 단일 struct/단일 control actor만 소유한다. nonce=id는 최초combined요청의w.request이며0/MAX/replay금지, boot/authenticated-session/principal/selected-axis와묶는다. 최초 요청은 boot Granted/같은 boot_session owner/현재boot lease/선택축/기존queue age·seq·rate를모두검사한다. 증거가없으면 기존short Busy로끝내고자동재시도없음; legacy의49msdeferred와분리한다. mint_handoff 성공시에만Pending생성, deadline=min(originalBootlease_until, accepted_at+700), overflow거절. 정상lease는아직0. 한 Owner lifetime에하나만생성하고새pair/조회로다시생성하지않는다.

매tick순서는 기존 Stop slot→일반명령→Run.poll→publish→pending진행→최종publish. queue Stop가먼저성공하면pending취소,같은tickexpiry가grant보다우선. 기존Run이이미Stopping/Fault면새Stop이firstfault를덮지않게receipt종결만한다. Pending deadline 도달은실제현재actor시각에기존Run Stop로종결(D소급기록금지). grant는현재profile/principal의run_session을열고 **그때의actual position/diagnostic proof**와기존 Gate Acquire를한번만통과할때일어난다. 필요하면 BenchRun에읽기전용 current acquisition proof predicate를추가하되 snapshot ready를위조/유지시키지않고 Gate/Arm/Ticket/Move의증명·기한을완화하지않는다. 실제Acquire결과실패는Failed+정지,재시도없음.

내부Acquire는신규run_session seq/request1을소비,receipt floor1을반환한다. 이미재사용run_session/선행일반Acquire가있는경우combined와충돌하지않게Pending중readonlyquery/Stop외일반명령을Busy로막는다. 증거에서운전주체principal을상속하고기존BenchRun acquireprincipal검사를그대로통과한다. 성공이후normal800ms lease/explicit Renew만,grant시각에만provisionalBoot기한해제. Grant이후실제gate owner/session/lease불일치나Stopping/expiry면storedreceipt는Revoked/Expired로바꾸고lease0으로반환한다.

결과조회는같은인증session/boot/id(w.ticket)만조회한다. 의도된Checking→Run 세대전이를가로질러조회할수있게조회만w.phase비교를면제한다. listener/age<50/auth/boot/ID/rate를유지하고새seq·Acquire·renew·receipt기한연장없음. 타세션조회는Denied,상태조회/재접속은예약생성0. 일반명령의phase/Replay검사는변경없음. 단, 아래의새예약에결속된Stop만명시예외다. malformed/idMAX/axis이상값은strictparser/소비검사로거절한다.

## 휴대폰 소비 경로

기존 PhoneControl.handoffAndAcquire는 legacy호출부/시험을위해보존한다. target DOM의‘인계+제어권’버튼은새 transferAndAcquire를호출한다. h.mode=transfer, id는해당명령의실제w.request,관측until=click+1147ms. 이는서버발급기한연장이아니다. 기존h boot/session/credential/axis/expected0→1→2검사를보존한다. combined ACK는generation이이동했어도같은live h에만결속하고Stop/hidden/disconnect후수신은무시한다.

250ms poll은actual status phase2(Run)가관측된경우ready와독립적으로 `handoff-result`를한번조회한다(반복조회는readonly이며Acquire재시도아님). Pending이남으면다음250ms조회,successreceipt는현재Run namespace와정확히같은 transfer_generation/currentboot/axis/session/ID,유효uint64 nonzero lease,floor검사를거쳐normalauthority로채택한다. 이를위해snapshot ready/phase를인위변경하지않는다. seq=max(local,floor) 이후다음request는floor보다커야한다. 성공채택때만h종결/renewAt설정. 기존readyfalse중normallease유지와숫자context별도취소를그대로사용한다. namespace전이중normallease를미리채택하지않아추가authority경계상태를만들지않는다. serverAlreadyGranted인데status가Checking이면아직조회하지않고다음Run조회까지기다린다.

새결과가serverclock상유효했더라도전송중lease가만료될수있다. client는fresh actual status와응답에찍힌시간/lease_until의보수잔여(로컬request RTT를차감,시계원점직접비교금지)를검사한다. 실제서버최종요청guard가항상최종권위. boundedreply보다늦거나now>=h.until·Stop/다른boot/axis/session이면채택/이동0. 로컬Stop취소와아직모르는외부Stop을구분하고후자는서버거절로보장한다. busy기존Stop독립lane/finally규칙을보존한다. 무한조회/자동예약/자동acquire없음.

031의관측식은직접receipt조회모형이었다. 실제웹은phaseRun status조회후receipt POST가필요하므로status 왕복과후속receipt 왕복을모두센다: grant→다음status주기250 + jitter50 + status request49+response49 + receipt request49+response49 =496ms. 다음명령49까지545ms<lease800(엄격margin<255, ACK가더늦으면추가). browser관측cleanup1147ms은phase관측추가98ms때문에모든위상の成功保証ではない. 이한계는안전취소/거절로보존하며clienttimer를늘려통과시키지않는다. 조건부실제DOM양성은필요하나모든지연·위상성공으로표현하지않는다.

## 소유와 검증

허용생산변경: robot_phone/{wire.cpp,include/...wire.hpp,owner.cpp,include/...owner.hpp,web/app.js}, robot_run/include/...bench_run.hpp의currentproof predicate, main/phone_http.cpp. 기존HTTP/runtime시험의신규명령/필드coverage만필요최소추가. 신규 tests/phone_transfer/ 와 tests/phone_transfer_browser/; .dev/phone-transfer-evidence/와본계획/종결색인. 030/031/028의정본·원기록·모형은변경금지. app의실물프로필·기본false,Gate·CAN·TWAI·CAD는수정하지않는다.

1. strictC++17 actualparse→Owner→Boot/Run→Gate 실제회귀:양축/측정false·true,한번grant/receipt/key분리·교차세대·seqfloor·readonlyquery/noautoRenew,경계D-1/D/D+1・noProof/overflow・Stop동시·latequery・既存firstfault/Stop원시각 유지. polling위상/지연은실제corefakeclock1msstep으로관측. actualrun gateclaim이없으면모형결과로대체금지.
2. 실제JS새메소드의ACK/checking/run/receipt·취소·namespace·seqfloor・lateerror/adoption검사를actualcompiledOwner bridge에도연결한다. legacy028/027/UI/HTTP/runtime/Boot/Run/phone 회귀는적절한기존runner실행한다. 실패원출력보존/자동유리한전체재실행선별없음.
3. 새browser하네스는030 actualHTML/app.js+loopbackfixture+C++bridge/Wpump를복사하고새Op/receipt를지원한다. original250/50ms/자동안전갱신false/명령favorable없음. 새 버튼요청만실행한다. 부팅은기존공개상태·실제DOM과명시적두번째unloaded확인을사용하며testoperator有利위상를표시한다. 숫자모션까지는기존actualGate read/Arm/Ticket admission 제한이여전히있으므로실패시그대로BLOCK/후속NOT_RUN. 정상시1FD100pulse/완료/정지,unapproved/heldACK+Stop/Arm·Ticketdelay/statusdelay/offline를검증한다. wrongasset/Stop누락/FD누락3behavioralcontrols는정상양성후만credit.
4. C++/JS 정책변형2개以上(예약만료등호/조회중복claim/타session조회/lateACK부활등 실제유일목표선택)는정상positive이후compile/syntax0/assertionfail로실효확인. 원본PASS복귀. fullbaselineUTF8 gitlsfiles-z/명시source허용목록/frozenSHA와기존원장변경없음대조.

L2논리PASS후구현·기계검사→L4비작성자actualsource/원기록/독립실행. 5공격분류와class/착지·EXHAUSTED충분임계필수;새PA동일class추가수용1이면잔여회차불문중단,사용자처분. 030 PB-R1-1은actualDOM 양성+controls/회귀가모두실행되어검토될때만폐쇄할수있고부분Owner성공으로닫지않는다. 결과는actualcore/JS/browser/SDKstub/target/physical을분리해HANDOFF/SESSION/BACKLOG/LESSONS/architecture/scopedlocalcommit에남기고push하지않는다.
## L2R1 수정 — 첫 상태 조회 전의 정지

PT-L2-R1-1 수용. 기존 actualOwner legacy Handoff6558 뒤 서버gen2에 client의이전gen1 Stop을보내면 Phase오류/stop_at0이고, gen2 대조Stop은동일시각수락되는 독립실측을보존한다. Stopslot우선만으로인증/세대거절을해결할수없다.

새 combined경로의Stop은 clear() 전에 현재handoff컨텍스트를캡처하고,ACK전에도알고있는최초request nonce를 v1 Stop의ticket에담는다. 서버는같은boot/authenticatedsession/axis/nonce와 활성Pending/Granted예약, 초기boot generation B(최대MAX-3)의예상namespace B/B+1/B+2, 현재Checking/Run과예상generation관계를모두검사한경우에만 Stop의옛w.phase를허용한다. 잘못된credential/boot/axis/nonce/비예상세대는예외불가. Stop의lease/ticket는이동허가로사용하지않는다. combined와Stop이동일tick에있으면현재Boot세대의기존Stopguard가먼저수락해아직생성되지않은예약을취소한다. 예약이이미terminal이면재발급0,첫stop/fault시각을보존한다.

기존 legacy Handoff/일반Stop의phase규칙을전역완화하지않는다. 따라서새combined의첫status전Stop 폐쇄와 기존legacy publicAPI의세대제약자체는분리한다. 알려진legacy제약은BACKLOG에OPEN으로남기고전역Stop호환수용으로표현하지않는다. 새DOM버튼이combined소비자를실제로쓰는것을확인한다.

실제시험: 첫250ms status전에즉시Stop,ACK1100ms지연중첫status전Stop,같은tickStop+combined,정지된뒤늦은ACK/receipt 및같은키조회,반대로wrongkey/wrongboot/wrongcredential/axis가전이예외를얻지못하는양성·음성대조. C++ bridge에읽기전용 transfer_attempts계수를제공하여 wire에Acquire가없다는관측만으로내부Acquire재생성없음을허위증명하지않는다. Stop이받아들여진후attempts증가0/FD0/새lease0과실제stop시각을핀한다.

구현상enum15는이미JointStep이므로v1 names를그대로append+index cast해서신규Op를잘못매핑하지않는다. client는새h의초기generation B와receipt generation B+2/currentRun namespace를모두검사한다. 서버result.accepted_at와lease_until의차이에서BigInt로전체로컬요청RTT를보수차감하고다음명령여유50ms를엄격히확보한때만채택한다(서로다른시계의절대값비교금지). 유효한이름의수신오류·만료상태·서버거절을성공receipt로채택하지않는다.

새 Stop namespace/admission 최초지적 OPEN/NOT_EXHAUSTED, PA등기존역사/충분다음임계 NOT_REACHED/유지. L2최종R2에서전체수정논리검토후에만구현한다.