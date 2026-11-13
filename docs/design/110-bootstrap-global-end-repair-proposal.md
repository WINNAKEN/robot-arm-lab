> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 110 B 후속 보완안 — 첫 claim read 전 고정 global end 결속

2026-11-04 KST. 현재 L2 R2 후보의 추가 미해결에 대한 **보수적 수정 제안**이다. canonical110 계획이나 R2 검토 대상 bytes를 변경하지 않았고 구현/새 검토/원격 실행을 허용하는 문서가 아니다. 원109/110의 회차·class 원장은 그대로다.

## 구체 누락

후속 request를client가t2695에보냈더라도remote entry가t2701이면, 현재 initialFence(now+20)는2721까지claimread를허용할수있다. 절대global끝2700을읽은뒤fullFence로옮기는순서로는그read앞의끝을소유하지못한다. 기존R1의동일late입력도실패하므로새class나수리→생성소진으로부풀리지않는다.

## 대체할 계약

첫 READY→LIVE 교환과 고정20차감은 유지한다. 그때 고정한 remote started_monotonic+2700과 deadline_unix 및claimSHA를 client의 배타 receipt에 저장한다.

**모든 후속 operation**(upload/extract/activate/controller/export/fetch/상태조회)의 caller는이 receipt의 expected_remote_end_monotonic과 expected_remote_end_unix,nonce/claimSHA를명령의typedscalar로전달한다. 누락/비유한/형식오류는SSH전에거절한다. 새 now+2700을계산하지않는다.

remote relay는압축helper고정bytes검증뒤, managedstate를읽기전에 전달받은end의형식과현재mono를검사한다. 이미끝났으면claimread/managedwrite/child0으로거절한다. 아직유효하면 **initial_end=min(now+20,expected_remote_end_monotonic)**인Fence를실제로armed한뒤만최초claimread를한다.

읽은claim의SHA·nonce·고정start/end가전달받은receipt와정확히같아야한다. 다른end/더긴end/짧더라도다른claim이면권한실패다. 같은원끝으로fullFence를실제armed한후만initialFence를close/join한다. 모든이후managedIO/relay/SDK/회수도그끝을공유한다. 초기20초는global끝의예외나재시작이아니다.

예상대조: entry2701/end2700은read0거절; entry2695/end2700은initial끝2700; entry2500/end2700은initial끝2520→동일2700 full로인계; claimmismatch는권한실패; pause duringclaimread는min끝에따른self-fence/UNKNOWN으로종결한다. sourceactualcaller와별도독립관측으로검증해야하며이문서의표는HOST성공자료가아니다.

## 요청 가능한 범위

이2개scalar배선과min경계를canonicalplan에반영하고, **B/통합 계획 검토만1회 추가**하는명시결정이필요하다. A/C의기존2/2처분과원109소진은재설정하지않고영향을받는연결부만실제검토한다. 추가판정도BLOCK이면그대로보존하며자동연속발사는없다. B구현은그계획이PASS한뒤,코드L4는기존미사용예산내에서한다. native45는계속미사용이며실물CAN·시계변경0이다.
