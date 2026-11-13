> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 065 — Windows 교체 잠금 대응과 journal 진행 조회

사용자 「새 예산으로 계속」 승인.08:41~09:26UTC45분, M급 source9+plan1. L2/L4각max2, 실제감사/진단/연결 각max1(실패포함), 독립SDK0. 소유 src/simulation/sharing_gravity/9파일·outputs/isaac-sharing-gravity-v1/·이계획.064원본과 실패/원장소비 보존, .dev/CAD/BOM/기존소스무수정. 재부팅/설치/권한·보안설정변경/실물보정/모터·CAN/flash/구매/학습 없음. 질량관성가정·링보류·047미해결 유지.

064실제연결은78.797초 WinError5로 종료됐고93완성행/0.766667초가 정상 FAILED JSON·journal·checkpoint에 보존됐다. 진행관측 ReadAllText의 기여가 유력하지만 실제독점lockowner는미확정. 호스트held-reader→교체거부/해제→성공 대조가 있고 Delete공유플래그만으로 해결되지 않았다. 이를 새물리실패나 전체600초 성능검증으로 해석하지 않는다.

064source9 복사 후 namespace/OUT/remote_root/legacy064·fixture·README 및 robot의 replace 재시도/순수journal진행parser, session/launch의 read-only progress 역할만 변경한다. physics/providers/worker는064와바이트동일. 기존collect_trace/check_gravity/check_journal·명령전토크대조·pending4단계·atomic first-fault·243journal/241state/9artifact/root내용검사·zeroPD/cap·모든물리/frame/float32·600초/freshness300·종료코드 계약 불변.

atomic_json의 직렬화·temp쓰기/fsync/FDclose는 한 번만 한다. os.replace 호출에만 WinError5/32/33 한정 재시도를 추가한다. 첫교체 시도부터 monotonic250ms 이내에만 다음 시도를 시작하며 최대11시도, sleep최대25ms와남은시간의min. OS syscall 자체의실행시간을중간취소한다고 주장하지 않는다. SDK API·명령·sim.step·journal append를 재실행하지 않는다. 첫오류를 객체로보존하고 영구잠금/250ms/maxattempts/다른오류가 나오면 최초오류와후속notes로 실패한다. 첫오류가다른종류면즉시거절한다. 기존FDclose/unlink/초기journalclose/collectorclose first-fault 보호는 유지한다. 정상성공은기존hash 반환, 실패중이전완성target/journal행 보존. source/purpose별 실제예약한도는 늘리지 않는다.

진행관측은 checkpoint target을 절대열지 않고 gravity-journal.ndjson만 읽는다. session/public에 progress 역할을 추가하고 현재source/job/prepared pin과run경계를검사한다. 고정remote root/runID의journal을 Windows FileStream(FileShare.ReadWrite|Delete)로열어 시작시길이만 읽고최대16MiB, try/finally로즉시닫는다. Base64 ASCII로전송하여 PowerShell확장문자열metadata/코드페이지를회피한다. 원격SDK Python/App를추가실행하지않는다(기존로컬Python-I frontdoor는사용한다). snapshot중새append를쫓지않고 마지막미완성줄만제외한다. robot의순수parser는완성줄의닫힌schema·run/job/동일positivePID·연속seq/hashchain·HEADER→ROW연속index→선택적COMPLETE를검사한다. 중간손상은거절한다. 결과는UNSEALED_PROGRESS_ONLY, 완성행수/최종index/bytes/선택적pending없음을표시하고 run/progress.json에만저장한다. 이역할은예약·freshness·current.json·terminal·권한을갱신하거나최종성공판정을하지않는다. 최종수용은기존9artifact/243record/fullreport/physics검사만이다.

새legacy는 원064원장 SHA433892e3ca7ebbf3ff37218e05fd4edd230f9344a115c0900b4bacbab6b61a0c/schema1/legacy_063/정확3purpose와IDs94ccf968ac464bba9ab08773ca2f3bc3,d0d672f24c4041f1aa110e5b2190c465,1b7e5739236a4f1886673d3b05bda042를검사한다. 새원장은legacy_064로nested이력유지, 원064delivery 실제SHA추가, 기존frozen refs/seal무변경. 새감사→fresh진단→same-signature연결 각1회. 실패원본회수/ownedPID·Kit·lock·원064SHA불변확인.

host는기존28개보존(legacy fixture와진입role변경만), 새대조: transient WinError→성공,250ms/11회/영구잠금·다른오류→최초오류보존, SDK명령중복없음, serialize/temp/fsync한번, release reader→성공과지속reader→실패/이전target보존, journal열린reader와append공존, 혼합run/중간손상/완성줄뒤비최종손상parser거절(같은run의유효옛prefix는UNSEALED만허용,맨끝미완성1줄은제외허용하고완주수용에는사용안함) 및progress가current/원장/freshness에영향없음을검사한다. Windows 실제filehandle 대조와 deterministic clock 대조를구분한다. AST/바이트·함수대조/범위whitespace/host 후 L4, 지문동결 후실제3단계. 네트워크/권한sandbox차단은독립환경문제로구분하고필요승인절차를따르며우회하지않는다.

이번runtime에서는 checkpoint를읽는임시PowerShell관측을금지하고새progress역할만사용한다. 240step/241state/엔진2초·6열선택/토크·hold/drop/contact를최종root로검증한다. 실제완주전성능해결을선언하지않는다. L4최대2와09:26cap내완료가능한단계만착수한다. 기존provenance7/physical6 EXHAUSTED·eligibility2 다음동종독립실측+작성자수용1충분임계/firstfault·CC062폐쇄·063overwrite소진·CJ064한정정적폐쇄는유지한다. 새Windows원인/착지·소진판정은비작성자가구분하며counter리셋없음. 외부hook재시도없고same-family비작성자fallback한계. 결과/가정/미수용을분리해delivery/HANDOFF/manifest저장·소유scopecommit,push없음.
