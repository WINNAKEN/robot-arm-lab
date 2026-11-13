> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 101 — 승인된 두 PC 시간 정렬 재개

2026-11-01. 사용자 `계속 진행해`는 직전 제시한 새10분 시간 정렬 재개를 승인했다. 100의 UAC 취소와 종결기한은 보존하며 새101 namespace를 사용한다. 서비스 시작·기존peer resync 범위는100과 동일하다. 제품 소스/시뮬레이션 수리는 없다.

첫 OS 조회 직전 monotonic+600초를 한 번 고정한다. UAC 대기도 포함하며 늦은 승인 후 작업은 fixed TickCount guard로 거절한다. 각 명령/통신은 남은 원기한으로 제한하고 기한/실패 후 새명령·재시도·자동새anchor는0이다. 최초 조회에서 양PC 서비스/설정/권한을 확인한다. 서비스가Stopped일 때만 Start-Service W32Time, Running이면유지; 기존 Type/peer/client/starttype이 바뀌면 중단한다. w32tm /resync는각PC1회, 실패/데이터없음은중단한다. 기존 time.windows.com,0x9 이외의 강제서버·NTP/registry/StartupType/timezone/policy변경·Set-Date/설치/재부팅은없다.

로컬은 Windows UAC를1회 요청하며 사용자의 실제 관리자 승인만 허용한다. 원격은 기존 isaacpc SSH 관리자 토큰을 사용한다. local완료 후 remote실행이며 어느쪽이든실패하면 다음변경은NOT_RUN이다. status/verbose/설정/서비스의실제관측과원본bytes를보존한다. rc0만으로정렬성공을선언하지않으며 실제source/최근sync/leap/stratum을평가한다. 필요시기한안읽기재관측만허용하고추가resync는없다.

SDK/SimulationApp/native/물리/실물CAN/급전/flash/모터/보정/구매는0이다. 098/099/100의원budget/실패/marker/검토종결·소진계보와원게인64/16·cap·물리기준/모델/097후보는불변이다. 정렬후에도old099재발사없음; 새namespace/필요검토/새45명시승인까지실제시뮬원격실행없다. MP10/J5 CAD 변경은소유밖으로보존한다.

소유: outputs/pc-clock-alignment-101/, 이계획/101-results.md, 최소공유HANDOFF/SESSION 덧붙임. 이번은승인된OS운영실행이며새제품코드/L2/L4/독립재현PASS로표현하지않는다. 로컬저장/커밋만,외부게시없음.
