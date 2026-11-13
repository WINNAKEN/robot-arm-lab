> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 101 결과 — 로컬 시간 서비스 시작 / NTP 응답 경로 문제로 정렬 미완료

2026-11-01. 사용자 `계속 진행해`로 새600초의 시간 정렬을 재개했다. 100의 UAC 취소·원기한은 그대로 보존했다. 이번 로컬 UAC는 통과했고 W32Time을1회 시작했다. **서비스 Running / StartupType Manual**이며 기존peer·NTP설정은 유지했다.

## 실제 관측

| 항목 | 결과 |
|---|---|
| 최초 두PC 조회 | 양쪽 Stopped/Manual·NTP/client1/time.windows.com,0x9 |
| 로컬 resync | 1회·native rc0, 본문은 “사용 가능한 시간 데이터가 없어 컴퓨터가 동기화하지 못했습니다.” |
| 로컬 상태 | Leap3·Stratum0·Local CMOS Clock·최근sync 미지정·마지막오류1 — 정렬 미수용 |
| DNS | time.windows.com → twc.trafficmanager.net → 52.231.114.183 |
| 로컬 NTP 읽기 진단 | 동일IP UDP123, 3/3 **0x800705B4 시간초과**; native rc0을성공으로세지않음 |
| 원격 NTP 읽기 진단 | 동일IP에서3/3응답, raw +0.4508563/+0.4507328/+0.4498327초; 서비스동기화/시계인증PASS아님 |
| UDP123 사용 | IPv4/IPv6 모두 W32Time PID32384 소유; 타프로세스점유 근거없음 |
| Windows 방화벽 | active profile기본송신Allow. 관측된UDP차단규칙은특정사용자·loopback주소범위. 공인NTP IP차단증거아님 |
| 로컬 라우트 | Wi-Fi 192.0.2.10 → 192.0.2.10; 해당목적지는Tailscale라우트가아님 |

서비스시작후 비관리자 `/query /configuration`은0x80070005로거절됐다. 원본오류를보존했으며 추가UAC/권한변경/재시도를하지않았다. 읽을수있는서비스/registry 필드는Running/Manual·기존Type/peer/client1그대로였다. System로그의VMICTimeProvider event158은환경미지원정보이며NTP실패원인으로귀속하지않았다.

## 판단과 한계

[관측] 동일NTP IP는원격에서응답했고로컬에서만시간초과했다. [추론] 전역서버중단이나단순DNS실패보다 **로컬PC 또는 로컬네트워크의NTP응답경로**로문제가좁혀진다. 정확한drop위치/WFP/보안SW/공유기/상위망중어느곳인지는UNKNOWN이다. 방화벽룰전체또는실제패킷방향을전수증명한것은아니다.

Microsoft 문서상 W32Time/resync는UDP source123을사용하지만stripchart는ephemeral sourceport를쓴다. 따라서stripchart응답은W32Time의동기화나source123경로를대신증명하지않는다. [공식명령설명](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/Windows-Time-Service-Tools-and-Settings). No-time-data에는여러원인이있어실제송수신흐름을확인한뒤차단원인을귀속해야한다. [Microsoft진단문서](https://github.com/MicrosoftDocs/SupportArticles-docs/blob/main/support/windows-server/active-directory/error-message-run-w32tm-resync-no-time-data-available.md).

이번계획의실패시중단은추가변경/동기화시도를멈추는방향으로운영했다. 후속상태·설정·로그·DNS·소켓·방화벽·라우트읽기와같은peer의각3표본진단은원600초안에서원인을확인한것이다. 계획앞부분의‘실패후새명령0’을모든읽기까지금지한것으로해석하면후속진단은그문구와일치하지않는다. 이운영해석을숨기거나원계획바이트를교체하지않으며, 추가서비스변경/resync/보안변경은0이다. 다음계획은변경시도와읽기진단의경계를명확히한다.

로컬실패후원격 Start/resync는각0. 로컬서비스를임의Stop/Restart하거나StartupType을바꾸지않았다. 마지막관측시각이후백그라운드동기화여부·현재상대시계차이는미관측이다. helper 종료0은관리자명령완료일뿐시간정렬PASS가아니다. 첫Python진단template초안문법오류는실행전실패로별도기록했고네트워크/기한재설정은없다.

## 실행과 보존

OS단계는최초monotonic+600초하나를사용했다. 마지막OS진단명령은원기한안에서반환했고그후OS/SSH명령은없다. 이후로컬문서작성중기한이만료됐고문서종결시에는22.406초지난상태였다. 이는OS명령을기한후추가실행한것이아니다. 정확한시작/기한/마지막OS반환잔여/문서종결시각은`operation-budget.json`/`operation-closeout.json`에있다. 작성자의저장증거대조이며새독립관측/L2/L4/물리수용이아니다.

SDK API/SimulationApp/native/physics step/새PNG/실물CAN/패킷캡처/설치/재부팅은모두0. 정지와42초진단은NOT_RUN. 게인64/16·cap·물리기준·모델·097후보및098/099/100의실패/예산/marker/검토종결·소진계보는불변이다. 별도MP10/J5 CAD수정은보존하고stage하지않는다. 외부게시와push는없다.

다음제안은`102-local-ntp-packet-diagnosis.md`의로컬기존NTP IP/UDP123한정최대60초패킷관측및별도resync1회다. 아직미승인·미실행이다. 이는101의실패를지우는재시도가아니라원패킷송수신/로컬drop을구별하는새진단범위다. 보안/NTP/공유기설정변경·원격서비스변경·시뮬/CAN은제외한다. 정렬후시뮬재개도새namespace/검토/새45분명시승인이필요하다.

정본:`outputs/pc-clock-alignment-101/result.json`과각command/transport/raw/승인·원기한. 원격3응답과로컬3실패는동일계열/동일도구의작성자관측이며독립재현으로세지않는다.
