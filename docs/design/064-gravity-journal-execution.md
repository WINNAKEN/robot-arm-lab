> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 064 — 중력 기록의 일정 크기 checkpoint와 추가 저장 journal

사용자 새 지시:600초 시간초과·기록단절 수정 후 실제 SDK/2초 유지·낙하·접촉 재검증. 새 예산07:47~08:32UTC45분. L2/L4각max2, 실제 감사/진단/연결 각max1(실패포함), 독립SDK0.063의 각1회는 그대로 보존하며 새 사용자 승인 아래 새064 input/원장으로 실행한다. 600초를 늘리지 않는다. 재부팅·설치·실물 보정·모터 운전·CAN·flash·구매·학습 없음. 질량관성가정/링보류/047미해결 유지.

소유는 src/simulation/journal_gravity/9파일, outputs/isaac-journal-gravity-v1/, 이계획.063 소스를 복사해 namespace/OUT/root/legacy와 robot의 기록부, root의 기록 대조, host fixture/tests만 바꾼다. physics/providers/worker byte-identical063. 기존 매핑/API/source·actual LINK/COM·명령전1e-3Nm·zeroPD/cap·240/241·엔진2초·frame/contact/float32구간/물리기준·baseline0g10step·종료코드 경계는 불변이다. .dev/CAD/BOM/047~062무수정;063은 실패원본+인계/검토결과만 보존하며 재실행하지 않는다.

관측:063 actualchild1/policy124/shell124/SSH1/local124, cleanup0 REAPED. 600초 timeout, 원 gravity-report1,500,699bytes가 중간 JSON이다. live145 RAW/173 MAPPED는 전체수용이 아니다. 정적 코드의4회/step whole-trace 재직렬화는 누적행수에 따라 O(n²) 비용이며, 최종파일을 직접 truncate/write하는 방식은 kill시단절 가능하다. 이것을 독점적인 실측 원인이라 단정하지 않는다. 새 host에서 직렬화량/쓰기구조를 계측하고 실제 새 wall duration은 별도로 보고한다.

새 writer는 작은 atomic checkpoint, append-only journal, 마지막 atomic full report로 분리한다. atomic JSON은 같은폴더 임시파일에 compact UTF8/allow_nan=False로 완전히 직렬화·flush/fsync 후 os.replace한다. 실패시 이전 완성 target은 유지하고 임시파일만 정리한다. 기존 frozen kernel.write나 다른 source를 고치지 않고 robot 내부 helper로 구현한다.

gravity-checkpoint.json은 rows를 담지 않는다. run/job/PID, phase/status, header(원 report에서 rows/pending 제외), pending_native(QUERY→SHAPE→RAW→MAPPED), row_count/last_index, last_sequence/last_record_sha256/journal_bytes, report_sha256를 담는다. 각 관측을 취득한 직후에 atomic checkpoint를 완료하고 다음 API/변환/명령으로 넘어간다. 특히 SHAPE 저장이 numpy 전에 끝나는062 수리는 유지한다. 저장실패는 명령 전에 실패한다. 전체 rows를 기록하는 작업은 per-stage에 없다.

gravity-journal.ndjson은 새 파일로1번 열고 이어 쓴다. ready HEADER1개, 완성 ROW0~ROW240 각1개, 마지막 COMPLETE1개만 기록한다. 각 줄은 schema_version1/run_id/job_sha256/pid/sequence/previous_sha256/kind/payload의 닫힌 JSON으로 compact UTF8+newline이다. 정확한 line bytes(newline포함)의 SHA를 다음줄에 연결한다. ROW는 기존 실제 row 자체이고 HEADER는 gravity 설정/actual API/base/clock을 읽은 collecting header다. 각 줄을 완성하여 append·flush/fsync한 후 checkpoint의 행수/chain head를 갱신한다. 쓰다가 죽으면 마지막 partial line은 미완료로 남을 수 있으나 앞선 완성줄을 truncate하지 않는다. checkpoint가 journal보다 뒤처진 창도 완주로 해석하지 않는다.

성공은 기존 check_gravity를 메모리상 원241row에 먼저 적용하고(물리FAIL이면 유효자료로 반환하는 기존계약 유지), unsubscribe/cleanup후 full gravity-report.json을 atomic으로1번 출판한다. journal COMPLETE에는 그 실제 report SHA·241row·last_index240을 묶고 checkpoint를 COLLECTED/GRAVITY_COMPLETE, pendingNone/reportSHA/chainhead로 출판한다. 정상 예외 시 primary를 먼저 보존하고 journal의 이전 줄/atomic checkpoint를 유지하며 가능한 경우 FAILED full report를 atomic 출판한다. cleanup 오류가 primary를 덮지 않는다. 강제 timeout이면 보고서가 없을 수 있어도 journal/checkpoint로 중단 지점을 확인할 수 있으며 성공을 제조하지 않는다.

terminal의 파일 해시 집합을 기존7개+gravity-journal.ndjson+gravity-checkpoint.json 정확9개로 늘린다. root는 terminal 해시를 확인하고 journal의 닫힌 schema·모든 줄 newline/유한JSON/중복key거절·동일run/job/PID·연속sequence·exact rawline hashchain을 대조한다. success는 정확243records(HEADER+241ROW+COMPLETE), ROW index0..240와 final report의 행 내용이 정확히 같아야 한다. HEADER는 final report의 header와 status/phase의 명시된 BUILDING/GRAVITY_COLLECTING→COLLECTED/GRAVITY_COMPLETE 차이만 허용한다. COMPLETE/report 실제SHA/checkpoint의 행수/chain/bytes/최종phase/pendingNone을 서로 대조한다. 그뒤 기존 check_gravity를 그대로 수행한다. partial journal·stale checkpoint·잘못된hash·추가/누락/중복/재정렬·혼합run은 전체수용 거절이다. forensic prefix 조회는 별도의 진단이며 final consumer 수용으로 사용하지 않는다.

계보: 원063원장 SHA0619f51fa90606a4efcaf3f0542d955676bfcc9cdb2bea0457c7d1506e62684c, schema1/legacy_062/정확3purpose와 IDs11d53ced16e14791a30c365655f21777,6060a3cc2dbb4fe5a8f6c1bbe36fe5a6,514d41126f9640be9c80cb1469dc1a8d를 고정한다. 새원장은 legacy_063으로 전체nested이력 보존. settings에 원063 delivery 실제SHA 추가, 나머지 frozen refs/prefix seal 그대로. 새 audit→fresh diagnosis→same-signature connection 각1회·900/300/600timeout·freshness300·원래 directPID/actual-policy-shell-SSH-local/cleanup 계약 그대로다.

host는 기존24시험을 보존/fixture의 새3artifact publication과9hash에 맞추고, 기존 deep 변조 음성은 journal/checkpoint/report를 함께 재생성·재해시하여 hash불일치만으로 거절되지 않게 한다. 추가: atomic replace 실패시 이전 target/observed shape 보존, append중간 partialline과 last complete row 보존/최종수용거절, chain/row/complete/checkpoint 혼합변조, actual mocked collector의 shape-conversion-fail/firstfault·명령0, complete240/241와기존물리FAIL, checkpoint 크기 bounded·final fullreport publish1회 및 journal row payload 직렬화량 선형성 계측. 시간 수치만으로 성능PASS를 만들지 않는다. AST/범위whitespace/host 후 L4, source 지문동결 후 실제3단계 실행한다. 예외/실패도 슬롯소비·native 재실행/튜닝없음. 완성/정리 가능한 단계만08:32UTC내 착수한다.

비작성자 검토는063 실패자료의 주장/class 처분과064 계획/코드를 구분한다. 기존 provenance7 EXHAUSTED/physical6 EXHAUSTED/eligibility2 다음 동종 독립실측+작성자수용1 충분임계/first-fault를 유지한다.062 CC부분영속화 수리와 이번 hard-kill/기록비용의 관계를 독립 분류하고, 새namespace로 소진 초기화하지 않는다. 외부hook 재시도/우회없고same-family비작성자fallback 한계. 종료시 실측·host·static/부분증거를 구분해HANDOFF/delivery/manifest·원격PID/Kit/lock/원063원장불변 확인·소유경로commit, push없음.
