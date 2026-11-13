> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 103 — 승인된 Realtek Wi-Fi 필터 A/B/A·조건부 복구 (L2 R2)

2026-11-01. 사용자명시답: `비교 시험 후, 원인이 입증되면 해당 필터만 끈 상태로 복구 진행 (권장)`. Wi-Fi가잠깐끊길수있는영향을확인했다. 102원ETL/driver/binding근거와승인사본은outputs/ntp-filter-ab-103/approved-plan-before-review.md 및user-approval.json,102/packet-analysis.json에있다. 기존10분반복중단은사용자가제거했다.

## 대상·권한

로컬Wi-Fi, Intel AX211, GUID F74CC1A2-11BF-449D-99C7-461B173F720A의 `nt_rtf64` 한개다. 현재Enabled/Realtek필터3.15.1128.2025. 다른어댑터·IPv4/6·WFP·방화벽·백신·Tailscale·NTPpeer설정은직접변경하지않는다. 설치/제거/재부팅/전체networkreset/실물CAN/SDK/native시뮬0. 영구off는아래A/B/A/최종B수용을모두만족한때만승인됐고,그외기본은target on복원이다.

## 상태 소유·늦은 명령 방지 (F1 수용)

네트워크변경은**단일독립로컬actuator 프로세스만**직렬수행한다. controller/독립watchdog는인터넷/SSH없이로컬파일로관측·복원요청만하며Enable/Disable을직접호출하지않는다. 시작전에watchdog-ready와승인·L2/L4PASS/sourceSHA를검사한다. 승인없거나검토/동결이안맞으면UAC/변경전에거절한다.

actuator의한mutation은CIMjob생성부터terminal(Completed/Failed/Stopped)과출력회수확인까지하나의in-flight 상태다. 실행중job/process를timeout으로kill/cancel하지않고, terminal확인전에는Enable·다음Disable·최종off를절대겹치지않는다. 실패job도상태를읽어원변경여부를확인하며완료를성공으로바꾸지않는다. heartbeat/progress를별도원자파일로게시하고controller가관측한다.

독립watchdog는temporaryoff시도시각+45초또는controller상실에restore-request를게시한다. **45초는새probe/변경중단과복원요청cutoff이며OS명령완료/연결복원의하드보장이아니다.** 이미돌고있는OSjob은terminal까지단일actuator가관측한다. 늦게반환하면새probe/최종off를생략하고같은actuator가target on복원한다. controller/tool의짧은poll반환은actuator취소가아니다. 네트워크단절에도로컬actuator는계속복원한다.

actuator자체소실/OSjob terminal미확인/heartbeat단절은UNKNOWN이며성공/원복확인/최종off유지로세지않는다. watchdog는늦은원변경의가능성을무시하고경쟁Enable을발사하지않는다. 실제상태와target전용수동복원명령을즉시제시한다. 이경우까지자동원복을보장한다는주장은하지않는다. 원상태Enabled확인전작업종결PASS나재실행은없다.

## 전체 map·복원·인과 gate (F2 수용)

시작전GUID/이름/전체ComponentID→Enabled map을새로읽어고정한다. target이원래on이고이전102target과일치해야시작한다. A0에서는동일NTP IP의고정3UDP표본을읽는다. 이미응답이정상이면binding변경없이NO_CHANGE_NEEDED로남기고기존시간동기화만별도로검증한다.

B1에서target만off명령1회 후job terminal을확인한다. **직후wholemap이baseline에서target한bit만off인map과완전히일치해야**Bprobe에진입한다. Wi-Fi/IP준비가확인되지않거나부수delta/조회실패가있으면B를무효화하고즉시target on복원경로로간다. off동안동일IP의UDP3표본만읽으며각수신2초/전체phase45초cutoff다. validNTP는origin timestamp일치·servermode4·stratum1..15·LI!=3·대상IP일치를검사한다.

B1의성공여부와무관하게target on으로A1을복원하고job terminal뒤wholemap이**baseline전부와일치**하는지검사한다. 자동으로바뀌었던다른binding이남으면원복은UNKNOWN이며추가off/인과수용을금지한다. target on으로되돌리는것외다른binding을직접변경해맞추지않는다. 원본map/현재map/delta/수동처분필요를보고한다. 이는전체원복의실패처분이며delta기록만하고정상계속하는경로가아니다.

A0 3실패→B1 3valid응답→A1 3실패가각각**target-only wholemap gate**아래확인돼야target원인으로수용한다. A1의응답이복구됐거나타bindingdelta/조건불명확/partial표본이면원인UNKNOWN·on유지로종결한다. 승인된수리C1은이인과gate를통과했을때만target off1회 후동일map gate와3valid응답을재확인한다. C1이수용되기전watchdog/finally는항상on복원요청을유지한다. C1의서명된수용상태가생긴후에만conditioned permanent-off유지가허용된다. C1에서도실패/지연/부수delta면on복원·UNKNOWN이며OFF유지하지않는다.

## 복구 검증

원인확인후수용된C1 off상태에서만기존time.windows.com,0x9로시간동기화한다. 새peer/보안정책변경은없다. /resync기본1회, 실제기존peer상태가stale/backoff임을확인했을때만/rediscover포함추가1회를허용하며무근거동일재시도는없다. 각rc/raw와실제Source/Leap/Stratum/최근sync를검사하며rc0만으로PASS하지않는다. 로컬정렬후기존별도isaacpc시간서비스의기존provider조회/필요시Start/동기화1회/상태검증은기존두PC정렬승인과현재자율복구지시범위에서이어갈수있다. 원격NTP서버/보안설정은바꾸지않고시계차이OS읽기로검증한다. old099재발사/원marker삭제는없다. 새시뮬45분은별도승인전실행0이다.

## 검토·증거

L2max2/L4max2, R1 BLOCK2건수용→이번R2재상정. 같은계열비작성자fallback사용자승인과잔여공통편향을유지한다. 옛099각2/2종결·raw/timeclass2→다음별개3임계와기존실패/정착EXHAUSTED/물성가정은reset하지않는다. 이번F1/F2는독립검토자가분류한network-actuator첫인스턴스이며옛clock channel라인과구별한다. 구현은L2PASS후, 실제변경은L4PASS+승인+현재freeze일치후만한다. fake OS job으로late/failed/neverterminal·controllerloss·watchdogrequest·wholemapdelta·승인없음·B/A/C부분표본을검사하고실제binding실행없는시험을먼저한다. source/freeze/전후map/probe원packet/모든jobterminal/heartbeat/복원상태를보존한다.

공식근거: [Disable](https://learn.microsoft.com/en-us/powershell/module/netadapter/disable-netadapterbinding?view=windowsserver2025-ps), [Enable](https://learn.microsoft.com/en-us/powershell/module/netadapter/enable-netadapterbinding?view=windowsserver2025-ps). Microsoft의부수binding변경가능성을위wholemap gate와복원실패처분에반영했다. 명령이반환되지않는OS장애까지자동완료를보장하지않는다. 소유src/simulation/ntp_filter_ab_103/(호스트OS진단전용·Isaac제품연결없음),outputs/ntp-filter-ab-103/,103계획/결과·최소공유인계이며CAD/펌웨어는소유밖이다.
