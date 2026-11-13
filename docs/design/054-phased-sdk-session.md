> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 054 — 설치 감사와 앱 실행을 분리한 유한 SDK 세션

2026-10-28 사용자 「자이제 계속 이어가」는 직전 결과에서 제안한 설치 검사/앱 실행 시간 분리와 실제 종료 관측의 후속 구현·연결 확인 권한이다. 재부팅·설치·전역 설정·장치·실물 보정·모터/CAN·플래시·구매·학습·링 검증은 제외한다. 질량/관성 가정·047 정착 실패를 보존한다.

## 새 경계와 소유

053은 source/SDK1/robot1/2회 L4를 그대로 동결한다. 새 이름으로 그 원장을 비우거나 같은 053 stage를 다시 호출하지 않는다. 이번의 서로 다른 실행 목적은 **설치 파일 감사**와 **감사 완료 후 앱 관측**이다. 사용자 후속 권한하의 새 세션이며 이전 053 예약2개/원장SHA를 필수 입력으로 보존한다. 특히 이전 053 SDK 단독 진단 성공을 새 source의 사전 성공 증거로 재사용하지 않는다. 새 앱 프로세스 안에서 SDK numeric을 다시 측정한다.

M8/45분: 이 계획과 `src/simulation/phased_session/{launch.ps1,session.py,audit.py,worker.py,settings.json,test_session.py,README.md}`. 증거 `outputs/isaac-phased-v1/`. L2/L4 각각 최대2, 기존 비작성자 읽기 검토만 재사용한다. 구현 위임 없음, 외부계열 bridge의 이전 hook 차단을 재시도하지 않으며 동일계열 잔여 한계를 기록한다. 다른 BOM/CAD/.dev/펌웨어 무접촉. 소유 파일만 로컬 commit, push 없음.

핵심은 설치 감사 권한/시간과 앱 실행 권한/시간을 다른 프로세스·원장 전이로 분리하는 것이다. 053 supervisor/entry/public/consume는 호출하지 않는다. 053의 최종 SHA 고정 kernel 수학 검증과 SDK collector는 읽기 전용 내용 자산으로만 재사용한다. 새 session이 단일-read source/job Snapshot, 목적/실행 원장, 감사 수용, 종료·transport 수용을 소유한다. frozen kernel의 api_for와 수치/프레임/접촉 판정, providers 수치 수집, robot 수집/lifecycle만 cached bytes에서 호출한다. 053의 full-prefix 검사/감독·단계 gate는 실행 경로에 없다. 이 구조가 기존 source 수리나 일반 소진 취소인지 L2가 독립 판정한다.

## 불변 입력과 감사

공개 PS → Python `-I -B -c` hash-bound loader만 허용한다. 전체 source/payload 정확 집합과 SHA를 확인한 동일 bytes를 immutable context에 보관한다. job 역시 단일 read에서 hash와 parse한다. native module은 그 bytes만 compile하며 supervisor는 프로젝트 helper를 다시 읽어 실행하지 않는다. 참조 source/asset/설치 seal은 settings의 고정 SHA로 묶는다. 기존053 ledger는 b610183f3dddb7ea10f127f353bd8d170b33722ca01e1570e55dbae7aabfe8cc이며 두 original run을 검사한다.

`installation_audit`는 **SDK를 import하지 않는 stdlib 전용 프로세스**, 최대900초/1회다. 고정048 prefix 전체 파일 집합/심볼릭 링크·junction/파일 해시를 원 seal39,919개와 대조한다. 경로를 canonicalize하고 예상 relative path를 벗어나면 거절한다. 최대4 thread, thread당1MiB streaming buffer로 메모리를 제한하며 큰 DLL 전체 read_bytes 방식은 쓰지 않는다. audit-progress는 완료 파일/byte/단조시계 경과를 관측하고 최종 verdict와 구분한다. 완료 시 원 seal SHA·전체 해시 동등·파일수/총byte·PID·jobSHA·input signature·시각/기간을 report에 기록한다. numpy/scipy/isaacsim/carb/isaaclab import0을 확인한다. 실패/timeout도 이 목적1회를 소비한다.

원본 SDK/048 prefix는 세션 동안 readonly인 신뢰된 설치 runtime이다. 감사 뒤 OS 동시 공격자의 임의 설치 변경까지 봉인했다고 주장하지 않는다. 새 앱은 동일 prefix/version/origin/모듈 DLL root를 다시 측정한다. 이 신뢰 한계는 프로젝트 source/job의 동일-byte 의무를 완화하지 않는다.

## 실행 전이

새 원장은 기존053 이력을 고정한 뒤 각 목적1회를 누적 기록한다. lock 아래 예약을 durable write한 다음 Popen한다. duplicate·미완료·실패는 재시도할 수 없다. `app_observation`은 installation_audit의 원본 job/report/terminal/parent-exit/remote-shell 증거를 bytes cache로 읽고, report hash·직계 PID·정상 actual exit0·timeout false·동일 input signature/설치 seal·최근300초 완료·원장의 original run을 모두 확인해야 시작한다. 증거 없는 성공 boolean은 사용하지 않는다. 예약 후 기존 Kit가 있으면 보수 실패하며 사용자 프로세스는 종료하지 않는다.

app은 별도 최대600초/1회다. full-prefix 재감사 비용은 이 프로세스 안에 없다. 검증된 SDK bootstrap bytes→SDK NumPy2.3.1/SciPy1.17 FFT/Rotation·모듈 root 재측정→SimulationApp→prefix-last/SDK Warp→Lab3.0·Torch2.11cu130·GPU sum6→기존 CAD v2 USD의 static/bodies/trace/contact4facet·중력0/PD0/10step11row를 수집한다. SDK numeric checkpoint와 phase를 앱 전에 저장한다. 필수 source inertia/FK/양쪽 joint frame/시간·접촉 index mapping 및 force×normal 합은 기존053 canonical kernel로 대조한다. 비영점 실제 접촉을 만들거나 일반6축 운전/중력 정착·학습으로 확대하지 않는다.

## 종료 관측과 소비

supervisor는 `actual_child_exit_code`, `policy_exit_code`, `timed_out`, cleanup 결과를 서로 다른 필드로 저장한다. normal wait의 실제 반환값은 원래 정수 그대로 보존한다. 최상위 정책은 portable0..255이면 같은 값, Windows32bit/음수 등 그 밖의 값이면1이며 매핑 근거를 명시한다. timeout은 소유 PID tree만 종료하고 **종료 뒤 wait의 실제 code도 저장**, 정책124와 혼동하지 않는다. taskkill/후속wait가 예외를 내도 이미 관측한 timeout·PID·정책124를 지우지 않고 cleanup/reap 오류·실제 code미확인·프로세스 생존 여부를 별도로 남긴다. 예외/terminal 부재도 parent envelope의 실제 실패를 먼저 처리하며 FileNotFoundError가 timeout 원인을 덮지 않는다. fast-shutdown의 old COMPLETE_PRE_CLOSE는 실제 child0·원자료 SHA/PID/필수facet가 전부 맞을 때만 수용한다.

원격 PowerShell은 Python의 LASTEXITCODE를 별도 `remote-shell.json`에 기록한다. SSH client return/stdout/stderr도 보존한다. SSH transport가 nonzero를1로 정규화해도 그 사실을 숨기지 않는다. 정상 root0+transport nonzero는 실패다. root의 비영점 정책은 증거와 일치하면 로컬 PS에 보존하며 실제 SSH code와 별도로 보고한다. 정상0은 parent/worker/audit/remote-shell/transport/모든 데이터 검증을 만족할 때만 허용한다. 반환 코드가 서로 다른 것은 보고된 실제 값이며 전 구간 값이 같았다고 표현하지 않는다. 전송 실패는 원자료 회수만 허용하고 재실행하지 않는다. subprocess는 Windows CREATE_NO_WINDOW를 사용한다.

## 검증과 정지

호스트에서 감사 정상·누락/변경/경로 이탈과 bounded streaming, source/job Snapshot, 전이 정상·실패/오래됨/다른 signature/PID/중복, 실제 child7와 timeout 정책124/실제 wait분리, cleanup/reap 예외의 timeout 정보 보존, signed/unsigned32bit 실제값과 portable 정책1 매핑, terminal 부재와 transport1, 완전한 로봇 수치 양성 및 mapping/force/inertia 음성을 검증한다. 필요한 경우 기존053 호스트 내용의 수학 fixture만 새 job/PID에 맞춰 사용하며 old public/entry는 실행하지 않는다. static AST·범위 whitespace·비작성자 L4 뒤에만 실제 감사1→조건부 app1이다. source 변경은 성공 감사의 재사용 권한이 아니다.

이전 provenance7/physical-frame6 EXHAUSTED, eligibility2/다음 독립실측·작성자수용1 충분 임계, startup/SB/first-fault/PA/terminal/039/SDK/링 이력은 그대로 재상정 입력이다. 검토는 class·착지·예산 종결 판정과 정적/실행 증거를 구분한다. 신규 같은 class 반복은 비작성자 판정을 따르며 시간 예산이나 목적 이름으로 소진을 취소하지 않는다. 실제 단계 실패 시 그 purpose의 추가 실행·기존 source 수정 출하 없이 raw/PID/cleanup·도달 지점을 기록하고 종료한다.
