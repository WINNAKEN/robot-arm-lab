> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 027 / PA-20261024 — 휴대폰 숫자 상대각도 제어 연결

2026-10-24 사용자 승인. 실물 보정은 미승인, 링 형상은 계속 미해결 보류. 실제 네트워크/장치/플래시는 실행하지 않는다.

## 목표/범위

휴대폰에서 명시적으로 입력한 상대 이동량을 기존 인증·제어권·Arm/Ticket→새026 BenchRun::request_joint_step→Gate/MKS codec/CanPort에 연결한다. deg/rad와 상대 변위임을 화면에 명시한다. 현재100pulse/speed5/acc2 제한은 유지하므로 보정된 한 단발에 해당하는 각도만 허용한다. 절대 위치 목표/임의pulse확장/자동분할/자동승인/자동재시도 없음. 실제기본 app·normal/hardware 승인false와 measuredfalse를 유지한다.

소유: robot_phone wire.hpp/cpp, owner.hpp/cpp, web index.html/app.js, main/phone_http.cpp의 상태 직렬화 최소 변경, robot_run bench_run.hpp의 읽기전용 각도 가용성 getter만 추가. 기존026 변환/진입/const보정/철회 로직, run.cpp/gate/codec/boot/app/runtime/CAD·원본 수용 산출물은 무수정. 새 tests/phone_angle/의 실제통합/JS시험·runner, 최소 기존phone테스트의 확장(필요시), .dev/phone-angle-evidence/ 및 인계문서만 소유한다.

## wire/서버

v1 11필드 프로토콜과 기존 op numeric순서는 보존한다. 새 Op::JointStep을 마지막에 추가한다. v2는 정확히12필드 `v2|boot|phase|seq|request|joint-step|lease|ticket|axis|joint|deg 또는 rad|signed-decimal`만 허용한다. 모든identity는기존uint64 strictparser. axis1..2/joint1..6/unit정확일치. 상대각도는선택적마이너스·1~6자리정수(0외leadingzero금지)·선택적소수1~18자리만 허용하며공백/+기호/지수/NaN/Inf/문자/빈값/중복필드/범위밖/0은거부한다. 수동고정범위 십진파서로locale·strtod예외·overflow를피한다. body256/HTTP기한·host/origin/credential·Stop listener격리는기존그대로다.

Owner 생성자는 기본미승인 calibration2개를받는추가default인자를가지고 실제run_3arg생성자로복사한다. 설정은신뢰된생성측전용이며wire로보정을받지않는다. 기존3arg호출은미승인배열이라새각도명령이실행되지않는다. JointStep은기존auth/phase/seq/rate/lease/session을그대로지나고run활성분기에서request_joint_step을호출한다. 기존direction Move fallback을하지않는다. boot/정지phase의새op는거부한다. 선택된axis 외 요청은기존arm/ticket/axis경계와명시selectedaxis검사로거부한다.

새 BenchRun 읽기전용 getter는026의동일const보정에서선택axis의 joint/유효성만반환한다. 보정유효성은기존prepare를재사용해100pulse상대deg를검사하고boot/profile/axis/revoke/normal승인/actor활성을확인한다. 상태에는angle_available(bool)와angle_joint(정수0또는1..6)만노출한다. double각도/보정값/미실측값을status에만들어넣지않는다. Owner는Run phase+유효보정일때가용으로표시하며ready와분리하고그외매publish마다false/0으로초기화한다. HTTP의boundedJSON에두필드를추가한다. 표시가true라도서버의실제gate/보정검사를대체하지않는다. Owner의신뢰된revoke API는run의영구철회를위임하고publish해phase변경/가용성차단을즉시반영한다(요청wire에관리op노출안함).

## 휴대폰 UX/취소

입력은문자열을유지하는text+inputmode decimal, deg/rad선택, ‘상대각도 한 번 이동’ 버튼. 서버가현재보정미승인이면버튼비활성/설명, 입력값편집은가능하나실행불가. 빠른누르기/Enter중복으로별도권한을만들지않는다. 기존고정pulse방향버튼은그대로유지하고각도성공이기존raw버튼자동실행으로이어지지않는다.

PhoneControl.moveAngle은문자열문법/단위/가용성/axis·joint/normal권한·freshness를확인한뒤입력문자열·unit·epoch·boot/generation·선택axis/joint를캡처한다. 각Arm/Ticket await뒤같은epoch/권한/lease·freshness/phase·선택axis/joint/가용성을재확인하고마지막에v2단1회보낸다. hide/offline/Stop/재연결/상태세대·축·관절/가용성변화시기존clear/epoch로취소,타이핑/단위변경은시작한명령을재해석하지않는다. 직접command('joint-step')에도문법/가용성검사를둔다. 성공후ticket폐기,모든오류clear/재시도없음. Stop은새입력문법/보정상태와무관하게기존분리port로전달한다.

## 증명/수용

strictC++17 actualparse→Owner→실제Boot/maintenance/enable/handoff/session→request_joint_step→Gate/codec→FakeCAN을fixturecalibration으로실행한다. 실제기본미승인fixture에서는같은문법의v2요청이FD0으로거부되어야한다. 양음deg/rad와두축/선택축·잘못된joint·권한/phase/seq/lease/ticket/범위/비100pulse·revoke·Stop우선/firstfault보존을검증. boot전이fixture값은실측이아님을명시한다.

JS시험은새v2바이트·uint64문자열·단위·중복호출/캡처값·Arm/Ticket실패/await중Stop-hide-stale-phase-axis-joint/보정가용성변경을검사한다. HTTP실제handler SDKstub에서새형식parse/상태JSON/분리Stop/전달을검사하고실제runtime C++stub·기존wire/phone/UI/026/boot/runtime회귀실행. UI숫자입력을실제Owner가소비하는명령으로재생하는연결시험을포함한다(양쪽을독립모사한것만으로endtoend라하지않음). positivePASS후compiled3변형(Owner각도분기rawMove잘못연결/서버decimal검사누락/JSawait후취소fence제거) 실제회귀검출. source/embedded웹바이트동기·헤더bounds·strictcompile검증. 로컬UIpreview가능시실제DOM도확인하되진짜휴대폰/WiFi수용과구분한다.

L1→비작성자L2→L3→비작성자L4, 각최대2회첫선언. 기존020/023startup역사EXHAUSTED·다음추가독립수용sameclass1→EXHAUSTED 및firmware firstfault N+1임계유지.026calibration/permit CLOSED,021math/023dependency/025serialization CLOSED이력유지. ring미해결보류. 같은class재발시잔여회차무관소진판정/중단. 외부계열중앙bridge차단NOT_RUN·우회없음,동일계열독립검토잔여위험기록. 수용후HANDOFF/SESSION/LESSONS/구조지도·로컬scopedcommit/push없음.

## L2 R1 처분 — 보정 capability와 이동 readiness 분리

PA-L2-R1-1 수용. angle_available은 현재Run phase의 불변보정 capability이며 ready와 독립이다. 정상FD전송후ready=false가되어도calibration capability는true이고JS는기존정상lease/authority를유지·갱신한다. 숫자버튼/각도sequence시작·각Arm/Ticket후fence에는ready=true를별도조건으로검사한다. 철회/fault/phase/boot/선택축·관절/capability변경은취소하지만단순ready변화는clear하지않는다. 정상동작중readyfalse→true에서lease가유지되고만료없이명시적renew가실제Owner까지전달되는연결회귀를추가한다.

숫자angle sequence전체는angleBusy/context토큰으로고정한다. 동시에다시누른숫자이동과다른일반제어클릭은거부하고Stop만항상허용한다. 각내부Arm/Ticket/JointStep만같은토큰으로진입하며clear는epoch를바꾸고기존sequence는끝나기전재사용하지않는다. pulse갱신은일반busy중동작하지않고숫자단발sequence가끝나면기존lease/ready와독립된normal권한갱신을재개한다. 불리한HTTP지연에서허가가만료하면서버가거절하며성공을보장하거나재시도하지않는다. 테스트는허용시간창에서성공하는실제경로와취소·거절을구분한다.

L2예산2/2최종R2. 새로운class를기존026calibration불변/firmwarefirstfault에귀속하지않으며동일기존원장임계는유지한다. 계획의숫자v2는수치값+단위·상대변위의직렬화계약이며보정/권한을사용자payload로승인할수없다.
