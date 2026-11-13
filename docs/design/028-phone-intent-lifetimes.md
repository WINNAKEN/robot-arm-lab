> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 028 / PC-20261025 — 인계 의도와 숫자 이동 취소의 수명 분리

## 권한·원장·범위

2026-10-25 사용자 명시 재처분으로027 PRODUCT/EXHAUSTED 뒤 새 상태 설계를 시작한다. 이전027 계획/시험/receipt/원장 바이트와026 보정·Gate·CAN·C++소스는 보존한다. PA 두 반례를 이월하며 다음 추가 독립실측+작성자수용 동일capability/authority-lifecycle 인스턴스1개는 즉시EXHAUSTED다. 기존startup/firmware firstfault 임계도 불변. 새 L2최대2/L4최대2를 첫 검토 전 선언한다. 외부계열 중앙bridge차단 NOT_RUN·우회없음.

소유: production `robot_phone/web/app.js`의 제어상태/응답/DOM버튼 활성화, 새 `tests/phone_intent/`와 `.dev/phone-intent-evidence/`, 이 계획과 인계색인만. 숫자v2/서버/보정/100pulse 제한/기존API/HTML/물리app는 무수정. 실물보정·hardware/normal/measured 기본false, 링보류, 장치/전원/flash/구매/출력/모델변경 없음. 임의각도·절대위치·분할·재시도는 추가하지 않는다.

## 제품 상태 모델

공통clear를 정상capability변화에 사용하지 않는다. 세 상태의 소유권/취소를 분리한다.

| 상태 | 생성·소비 | 취소·수명 |
|---|---|---|
| 현재 authority/lease/ticket 및 control epoch | 기존 명시Acquire/Drive/Maintenance의 현재문맥 응답만 설치 | 부팅/세대/phase/선택축 변경, Stop/hide/disconnect/stale/fault/현재문맥 오류로 폐기. 정상ready변화·각도capability변화만으로 lease를 지우지 않는다. |
| 명시 Handoff→Acquire intent 레코드 | handoffAndAcquire 한 번의 사용자행동만 생성. boot/선택축/session/deadline700ms/관측phase/객체identity 캡처. Ready에서 Acquire전 원자적으로 한 번 소비 | 동일boot/축/session에서 정상0→1→2 또는0→2만 보존; 시간 연장/새로 생성 없음. Stop/hide/disconnect/stale/fault/축·boot변경/역전·예상밖세대전이/실패·만료는 폐기. capability/joint 상승은 취소조건 아님. |
| 숫자 이동 context 및 angle revision | 한 사용자행동의 입력문자열/unit/boot/generation/axis/joint/lease/control epoch/angle revision 캡처 | capability/joint 변화는 이 문맥과 ticket만 폐기. 모든 hard reset도 폐기. angleBusy는 비동기 작업 finally까지 유지, 다른 숫자·일반명령은 거절. ready=false만으로 제어권을 취소하지 않지만 새 이동/Arm·Ticket후 fence는 ready필수. |

`clear()`는 명시적인 hard reset(세 영역 모두 폐기) 전용으로 유지한다. 숫자취소는 angle revision/ticket만 바꾸고 인계 intent나현재lease를 지우지 않는다. 선택축 변경은 제어 대상 변경이므로 hard reset이다. 세대/phase변화는 authority/숫자context를 폐기하되 기대한 인계 전이이면 별도intent가 살아있다. intent용 boolean을 clear뒤 임의복원하지 않고 객체identity/전이표로 관리한다. 기존 handoffIntent read는 파생상태로 제공해 소비자호환을 유지한다.

## 순서·응답·사용자 행동

중복 Handoff 클릭/진행중 숫자 이동·다른일반명령/이미pending intent이면 새로운 의도를 만들지 않고 거절한다. pending Handoff동안 임의일반명령도 거절하고 Stop은 항상 기존독립listener로 가능하다. DOM은 pending intent동안 일반버튼을 비활성화하며 입력편집은 진행중 명령을 재해석하지 않는다. 자동Acquire는 객체가유효하고 phase2/ready/fresh/현재session/기한내/다른normal전송없음일때만 한 번 실행한다. 자동재시도나 polling에의한intent 재생성 없음.

Handoff ACK전에도 poll이 정상세대전이를 관측할 수 있다. 해당전이는 intent를 보존하고현재권한만폐기한다. ACK가늦어도 그intent를지우거나죽은intent를복구하지 않는다. Stop/새boot/숨김후 늦은ACK·Acquire·Arm·Ticket 응답은 현재문맥에 lease/ticket/intent를 설치하지 않으며 새문맥을 전역clear하지 않는다. 이미취소된 이전응답의오류도 새로운문맥을소거하지 않는다. 현재문맥의실제전송/서버오류는 기존fail-closed hard reset한다. 숫자문맥만취소된응답은ticket을설치하지않는다. 정상전송busy는Stop의완료로조기해제하지않고그normal요청의finally까지유지한다.

poll은 시작session identity를 캡처해 재연결 전의 늦은상태를 무시한다. fresh/700ms 한도는기존대로이며시간초과인계를자동재생하지않는다. 숫자 마지막전송 후문맥변화는요청이미전달가능성을취소된물리운동으로표현하지않는다. 로컬취소는후속요청차단이고실제정지는명시Stop/기존서버정지절차다.

## 검증·수용

새시험은 실제productionJS를 사용한다. 이전반례의uncalibrated positivecontrol와calibrated handoff를 둘다 검증하고, 합성snapshot만으로 전체연결수용이라 하지않는다. 기존BootFake/AngleFixture는 소스무수정 재사용하여 새C++bridge를 **Granted/아직Boot**에서 시작한다. 실제Owner Handoff→RunChecking→Run의 snapshot과실제JS Handoff/Acquire 바이트를 연결하고이어숫자deg/rad→실제Gate/codec/FakeCAN 한단발, readyfalse중 실제renew를 확인한다. 보정false는인계/Acquire는가능하나숫자FD0을확인한다. 기존실행부/서버무수정과기본false를검사한다.

표기전이만이아니라Handoff ACK 지연/상태poll 선행, 중복클릭/중복poll, Stop/hide/offline/stale/기한/boot·축·fault/역전전이에서pending Acquire없음, Acquire응답지연후취소, Arm/Ticket중capability/joint변경취소와lease유지, 정상readyfalse갱신, 원래context가돌아와도재생안됨을시험한다. 기존legacyJS34/027JS50/027실제C++5057/JS-C++156·HTTP/runtime SDKstub/026회귀실행. 기존027 witness는역사기대(버그존재)라새소스에서그자체를PASS로재라벨하지않고 새회귀로양쪽결과를고정한다.

positive통과후실제동작변형3개: capability변화에globalclear복원, Handoff전이에서intent항상삭제, angle revision fence무시. 모두구문/컴파일정상후행동단언실패해야한다. baseline전체해시와소유변경목록, 고정소스manifest/author로그/독립L4재실행을보존한다. 변형실패LASTEXITCODE를정상결과exit0과혼동하지않도록새runner는전체판정뒤명시exit0한다. 브라우저/실제휴대폰/WiFi/target/물리CAN NOT_RUN은별도표시한다. 비작성자L2→구현→비작성자L4, 새동일class반례수용이면잔여회차무관중단·사용자처분. 종결시HANDOFF/SESSION/BACKLOG/LESSONS/구조색인과소유범위localcommit/push없음.
