> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 102 — NTP 패킷 진단 완료 / Realtek Wi-Fi 필터 후보

2026-11-01. 사용자의 자율진행 지시로 OS작업을10분마다중단/재승인하던조건을제거했다. 명령별상한·원본로그·기존시뮬/실물CAN경계는유지한다. 아래는작성자의OS진단이며독립제품검토/물리수용이아니다.

첫관리자사전점검은실제출력`패킷 필터:\r\n 없음`의개행을판독하지못해캡처/필터추가/resync전에중단했다. 원본을보존하고한글다중행판독만수리했다. 두번째관리자진입에서실제캡처1회를수행했다. 첫실패를성공으로덮거나기존100/101실패를재사용하지않았다.

실제관측은기존IP **52.231.114.183·UDP123만** 23.021초캡처했다. ETL25,030B, EventsLost0, filecap32MiB/prefix128B. resync1회는rc0이지만no-time-data였고이후Leap3/Stratum0/LocalCMOS다. stripchart3표본도전부timeout. 캡처는정지됐고전용필터는제거돼필터목록이없음을확인했다. 설치본remove는전체명령만지원해시작전0/정리전본작업전용1개목록바이트동일을확인한뒤그1개만정리했다. 외부capture/filter는변경하지않았다.

ETL의4개Tx이벤트는**동일90B프레임의4스냅샷**으로송신4패킷으로세지않았다. rawframe은192.168.0.5:123→52.231.114.183:123, NTPpayload48B/clientmode3/version3이다. TCPIP43→QoS18→Realtek19 Upper까지보이고이후NativeWiFi20/VirtualWiFi21/IntelNIC6에는관측이없다. Rx0·명시drop0이다. 따라서**NIC출고/공유기차단을확정하지않으며**, Realtek부근의실제중단과계측한계를아직구별하지못한다. [Microsoft관측해석](https://learn.microsoft.com/en-us/windows-server/networking/technologies/pktmon/pktmon-syntax).

별도PythonWinsockUDP요청1개(48B)도5초수신timeout이었다. 같은현재시점의원격읽기대조는동일IP에서3/3응답(raw+.5470900/+.5478340/+.5477232초)했으며원격W32Time은Stopped그대로다. 원격서비스/시각은변경하지않았다. 동일도구로반복한응답을독립검수로세지않고, Winsock관측도프로그램이달라도같은OS/네트워크를공유하는한계를기록한다.

바인딩읽기에서Intel Wi-Fi AX211의`nt_rtf64`가Enabled이고`rtf64x64.sys`3.15.1128.2025가Running임을확인했다. 이것은Realtek필터를후보로지목할근거이며원인확정은아니다. 네트워크바인딩/방화벽/NTP서버/라우트/VPN은아직변경0이다.

다음103의대상한개A/B/A와원인입증시조건부off유지·기존시간설정내복구는사용자가명시승인했다. 실제네트워크변경은복원실행기L2/L4검토와복원준비후진행한다. Wi-Fi가잠시끊길수있는영향을사용자가확인했다. 원복은인터넷/SSH에의존하지않는다. 방화벽/Tailscale/다른바인딩/CAN은제외한다. [변경영향Microsoft설명](https://learn.microsoft.com/en-us/powershell/module/netadapter/disable-netadapterbinding?view=windowsserver2025-ps).

새SDK/SimulationApp/native/physics/PNG/실물CAN/설치/재부팅은0. 기존098~101원예산/marker/실패/검토종결/소진계보와게인64/16·cap·기준·모델/097후보는유지한다. 시뮬42초진단은NOT_RUN이며새namespace/검토/새45분별도승인이선행된다. 별도MP10/J5 CAD수정은소유밖으로보존한다.

정본:`outputs/pc-clock-diagnosis-102/result.json`·`packet-analysis.json`·`capture-r2/ntp102.etl`/`ntp102.txt`·명령/원시stdout/stderr/cleanup증거. 103후속상태는그정본을먼저확인한다. 이번결과는별도네트워크A/B결과나시간정렬PASS가아니다.
