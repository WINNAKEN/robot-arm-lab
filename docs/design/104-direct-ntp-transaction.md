> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 104 — 파일 감시를 제거한 단일 로컬 NTP 바인딩 트랜잭션

2026-11-01. 103최종BLOCK의source특정파일관측결함을반복수리하지않고,외부watchdog/파일progress소비를제거하는새구조다. 103추가R3/재발사/예산reset은없다. 사용자동일target조건부네트워크수리승인과10분반복중단철회는유효하다. 실제네트워크영향/권한범위를넓히지않는다.

대상GUID F74CC1A2-11BF-449D-99C7-461B173F720A/Wi-Fi/nt_rtf64만변경한다. baseline A0 3실패→Boff 3valid→Aon복원 3실패→Coff3valid와각target-onlywholemap gate/온복원wholebaseline일치가조건부off유지의필요조건이다. partial/부수delta/관측실패는on복원·UNKNOWN·추가off금지다. 다른binding/WFP/방화벽/Tailscale/NTPpeer/설치/재부팅/SDK/native/CAN변경0. 기존source103의검토된trial/Live terminal순서/온복원I/O분리/receipt취소/validNTP파서만고정SHA로재사용한다. 103 gate/actor/execute/watchdog는새진입점에서호출불가해야하며이negative를시험한다. source103은변경하지않고의존도달배선전체를L4검토한다.

권한검사와L2/L4PASS/sourcefreeze/hash/실사용자승인검사는어떤의존코드exec/UAC보다앞선다. 고정SHA로읽은source103 바이트를그버퍼에서exec해TOCTOU재읽기를피한다. 단일독립로컬actuator만CIMjob을직렬실행하며runningjob timeoutkill/cancel/경쟁Enable은없다. terminal/출력확인후만후속변경/복원한다. controller는nativeprocesshandle로종료를관측하며,살아있음은phase/진행성공을뜻하지않는다고표시한다. progress.json/파일watchdog/별도변경작성자는없다.

actuator의progress는메모리진단이며수리조건으로파일을읽지않는다. restore_requested는자기monotonic cutoff45초·진단fault메모리·엄격한controller PID+creation ID만직접검사한다. controller상실또는늦은CIMterminal이면새probe/off를시작하지않고같은actuator가on복원한다. 파일관측실패가시계·PID검사까지skip하는분기가없다. 네트워크단절에로컬actuator동작은의존하지않는다. actuator자체사망/미확인terminal/OS명령미반환은UNKNOWN·수용/최종off금지이며자동복구완료를보장하지않는다.

45초는임시오프의새작업중단/복원요청cutoff이지OS복원완료의하드보장이아니다. controller의개별실행관측상한300초초과는UNKNOWN으로반환하며actuator를kill하지않는다. controller프로세스가끝나면actuator의직접PID생성ID검사가복원신호가된다. 이300초는작업전체10분예산이나재승인조건이아니다. root는실제상태를읽어복구를이어가되무근거동일재발사는하지않는다.

I/O는F1수리된103backend대로terminal메모리확정뒤저장하며온복원발행을막지않는다. C수용실패/최종결과게시실패는F2수리대로현재receipt/영구flag를취소하고온복원한다. 고정SHA의기존성공경로와같은F1/F2부정시험을새배선으로재생한다. result파일은nativeactor종료후한번소비하며읽기실패를성공/무한생존으로세지않고UNKNOWN을보고한다. accepted최종result·receipt결속·wholemap이모두확인될때만조건부off수리수용이다.

sourcefreeze/현재상태/모든probe원bytes/명령rc/raw/terminal/원복결과를보존한다. 실제Coff수용뒤기존provider로로컬시간동기화·상태검증,로컬정렬후기존isaacpc서비스의필요시Start·기존peer동기화1회·상태검증을자율적으로이어간다. 새NTP서버나보안정책변경은없다. old099재발사/marker삭제없고새시뮬45분은별도승인전실행0이다.

L2max2/L4max2를새구조첫검토전에선언한다. 103각2/2종결·기존monitor union2→다음3 및restoration-I/O union2→다음3·옛099 raw/time계보/임계는reset하지않고새지적이같은class이면비작성자가연속원장으로센다. 다른설계라는이름만으로class를소거하지않는다. 같은계열비작성자fallback/공통편향을유지하며실제검증은코드/HOST/OS A/B/시계정렬/시뮬/실물을구별한다. 소유src/simulation/ntp_transaction_104/,outputs/ntp-transaction-104/,104계획/결과·최소인계. MP10/J5 CAD/펌웨어소유밖.
