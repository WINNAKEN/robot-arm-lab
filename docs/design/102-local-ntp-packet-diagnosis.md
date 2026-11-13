> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 102 — 승인된 NTP 원인 진단·복구 (사용자 자율 진행 지시 반영)

2026-11-01 사용자: `계속해봐 근데 계속 10분하고 멈추는건그러지말고 좀 자가적으로진행해`.

이 지시는 아래 제안의 **전체600초마다중단/재승인** 조건을 대체한다. OS 시간 문제 해결을 자율적으로 이어가며, 명령·UAC·통신·캡처별 제한과 실패증거 보존은 유지한다. 캡처는 동일 NTP IP/UDP123에 한정해최대60초·32MiB·128B prefix, resync1회와stripchart3표본을관측한다. 다른사람의capture/filter는건드리지않는다. 결과에따른상태읽기/원인분석/기존설정내복구를이어갈수있으며무근거동일명령반복은하지않는다. 새보안/네트워크설정변경은필요근거를먼저제시한다. 실물CAN금지와새시뮬별도45분승인경계는불변이다. 옛098~101예산/실패/marker를reset하지않는다. 이번은102의새OS범위이며옛실패를재사용하지않는다.

관리자helper의UAC대기에는개별상한을두되,취소/실패면임의우회하지않고실제상태를보존한다. 캡처소유/자동stop과고유filter정리여유를준비한뒤시작하고읽기실패를성공으로덮지않는다. 원래제안바이트는outputs/pc-clock-diagnosis-102/before/approved-proposal.md에보존한다. 아래는승인전제안이력이다.

---
# 102 — 로컬 NTP 패킷 경로 진단 제안 (미승인·미실행)

2026-11-01. 101에서로컬W32Time은Running/Manual로시작됐으나resync본문은no-time-data,상태는Leap3/LocalCMOS였다. 같은52.231.114.183:123에로컬stripchart3/3timeout·원격3/3응답,로컬선택라우트는Wi-Fi/공유기였다. 실제drop위치는아직모른다.

## 구체 범위와 영향

사용자승인후새OS진단최대600초를시작하고고정한다. 로컬에서Windows기존pktmon으로 **현재기존peer time.windows.com의동일IP·UDP123만 최대60초** 캡처한다. 시스템패킷추적상태를잠시바꾸고로컬ETL에주소/시간/NTP패킷일부를저장하므로101의일반상태조회와구별한새범위다. 로컬 resync도관측용으로추가1회만허용받는다. 설치·일반트래픽캡처·보안/방화벽/NTP/라우트/VPN/공유기설정변경·외부업로드는없다. 원격서비스/시간변경·SDK/native/CAN도0이다.

1. 관리자승인1회후pktmon도움말/현재상태/filter와서비스/peer를읽는다. 기존capture/session이있거나기존filter가비어있지않으면다른세션을Stop/제거하지않고변경전중단한다. peer가101의대상과달라지거나필터/기한/정리가보장되지않아도중단한다.
2. 고유필터명으로동일IP+UDP+port123을한filter에묶는다. 예시형태는 `pktmon filter add KMJH102NTP -i 52.231.114.183 -t UDP -p 123` 이며실제기존CLIhelp와대조후쓴다. 기존필터들을OR로합쳐다른트래픽까지포함하는실행은하지않는다.
3. 추적시작1회·max60초/파일cap32MiB·packet prefix128B·로컬owned ETL만사용한다. 시작전에stop/기한/소유cleanup여유를확보한다. 전체networkstack과NIC의방향/drop관측을보존하며NIC출고가확인되기전‘공유기차단’으로단정하지않는다.
4. 캡처안에서기존peer `w32tm /resync` **추가1회**(max20초)와stripchart3표본(max20초)만관측한다. 실패하면추가변경/재요청0이다. 이미시작한소유capture정리와기존로그/status읽기는원기한안에서허용한다. 이읽기정리예외를다음실행권한으로해석하지않는다.
5. 본작업이시작한capture임을확인하고종결1회·고유ownedfilter만제거한다. 기존다른세션을정지/전체filter remove하지않는다. 기한/정리소유가불명확하면UNKNOWN으로남기고자동재시도하지않으며실제잔여상태를즉시알린다. 종결은600초안cleanup예약을포함한다.
6. 원ETL·counters·텍스트변환·상태·전체명령rc/raw를보존한다. pcapng는stack/drop정보가빠질수있으므로원ETL/텍스트를정본으로쓴다. 송신미생성/로컬drop/NIC송신후무응답/응답수신후거절을구분하고근거없는인과나시간정렬PASS는선언하지않는다.

로컬캡처하나로공유기외부의정확한차단장비를항상특정할수있는것은아니다. 필요시추가범위는별도제안한다. 101resync1회/원실패는소비·보존하며099재발사/예산reset은없다. 이번제안은새시뮬45분승인이아니다. 게인/cap/기준/모델/CAN금지와기존검토/소진계보를유지한다.

공식근거:[pktmon](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/pktmon), [필터와관측](https://learn.microsoft.com/en-us/windows-server/networking/technologies/pktmon/pktmon-syntax), [W32Time명령](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/Windows-Time-Service-Tools-and-Settings). 현재로컬pktmon가용성·실제capture/정리수용은아직미확인이다. 운영launcher와cleanup절차는승인후실행전에구체화·기계확인하고제품소스를수정하지않는다.

## 설치본에 맞춘 운영 명확화

설치된pktmon의filter remove help는전체제거만지원한다. 시작전filter0을확인하고, 정리직전목록이본작업이추가한전용filter1개와바이트동일하며capture도본작업소유일때만remove하여그1개만정리한다. 외부filter가추가되거나세션소유가달라지면삭제/stop하지않고UNKNOWN을보고한다. 일반방화벽규칙과무관한수집필터이며사용자자율진행범위의실행선택이다. 캡처중각명령이공유하는45초soft deadline을쓰고stop에추가6초를예약해60초한도안종료를시도한다. 무제한명령/무한대기는없다.
