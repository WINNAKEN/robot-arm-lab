> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 114 제안 — 제어용 바이트 동일성 확인과 숫자 소비 검증 분리

이 문서는 최초 작성 시 **구현·새 원격 실행 미승인**이다. 현재 허용 작업은113 회수자료 진단과 이 설계의 읽기 전용 L2 검토다. 사용자 승인 기록은 별도 intake에 결속하며 계획 본문을 사후 승인문으로 바꾸지 않는다. 113의 단일 원격 시도는 이미 소비했고 남은 시간을 재시도로 재사용하지 않는다.

## 1. 확인한 실패와 수리 목표

113은 HOST92/92·주/보조 L4R1 PASS12/0 뒤 실제 첫 원격 실행을 했다. CLI2, outer279.406초, controller 내부 child124, terminal/raw_complete=true·job_active_after0이었다. 닫힌 ZIP72파일을 정상 회수했고 SHA256은 bdc290bb381f83f5649f4f604d61e96f9a2aec3abc8d6abc9443b4f423e2d484다. import 시도 예약은 있지만 OS 시계 transport 파일/admission·SDK supervise/본실행·정지·motion·frame은 없다. fetch는 파일만 회수하므로 빈 디렉터리 생성 여부는 미관측이다. OS 프로세스 호출 전에 반드시 쓰는 request.json의 부재와 실제 clock marker·중첩 원 owner·원 실행 순서·종료124를 결합해 본실행 미도달을 판정했다.

원 clock20 안 첫 session_now→Runtime.verify→B.context→D receipt consumer→새 전체 policy가 반복된다. marker 시점에 이미11.391초를 쓰고8.609초만 남았다. clock_exchange는 같은 원 owner에서 OS argv 생성 전 session_now를 다시 호출한다. 이때 원 guard가 종료했다. 로컬 actual C clock 경로+actual B.phase/A Fence에 같은11.391초 verify 지연을 넣으면20.219초/exit124·OS argv0, 빠른 대조는0.360초/exit0·실제 로컬 OS clock/certificate 통과였다. verify 지연과 local executable만 HOST seam이며 실제 B context 지연 측정인 것처럼 쓰지 않는다.

실제 로컬 B.context 프로파일은4.218초 중 D consumer4.039초·fresh policy3.307초·JSON2.557초였다. profiler 오버헤드를 포함한 노트북 값이며 원격 CPU의 함수별 시간은 아니다. 따라서 **원20초 소진 기전은 재현됨**, 원격 세부 CPU 귀속은 호출 순서와 로컬 프로파일이 지지하는 추론이다. 근거는 OUT113/performance-diagnosis.json·clock-owner-postmortem/result.json·actual-context-profile.*다.

수리는 숫자를 읽지 않는 제어 경로에서 전 입력 숫자 파싱을 반복하지 않도록 역할을 나누는 것이다. **20초/cleanup2·global2700·native600/motion900·원 headroom·게인64/16·cap·모델/물리기준은 그대로** 둔다. clock owner를 늦게 시작하거나 end를 다시 잡아 통과시키지 않는다.

## 2. 소유와 제안 예산

새 SRC는 src/simulation/control_identity_split_114, OUT은 outputs/control-identity-split-114다. B2=bootstrap.py/test_bootstrap.py, C4=driver.py/config.json/test_driver.py/OUT execute.py, D4=validate.py/decision_schema.py/test_validate.py/test_decision_schema.py로 분할한다. 운영 source9+harness1=10, 각 그룹 구현+HOST+수리+root 귀속 검증의 누적 **1500초**를 제안한다. 작성 동결 대기/독립 검토는 구분하고 리셋하지 않는다. 첫write 전에 시작시계를 저장하고5/19/22분에 실측한다. cap 소진은 보수 종결이며 다른 그룹으로 비용을 숨기지 않는다.

L2/L4는 각각 최대2회·각 main/lens2700초, noR3다. 같은계열 비작성자 폴백의 기승인과 공통편향을 명시하고 막힌 Sonnet bridge를 수정/재실행하지 않는다. 새 implementation/native 승인은 이 설계와 최종 L2 검토를 사용자가 확인한 뒤 받는다. 실제 코드 작성은 그 승인 전0이다.

## 3. 유지할 입력·역사·숫자 검증

원source69=기존59+113 source9/harness1, currentCAD22, critical112/113 및 닫힌 실패 ZIP을 보존한다. actual model16·refs11·immutable source10815·USD3·immutable A1은 그대로다. 새 helper alias만114 경로로 옮기며 원 A SHA2ca8c90616026a103eb41da18c33f34b012bcd56439cb39af967ea9bf2f683b0를 사용한다.

runtime21(A8/B13), key48=source21/model16/ref11, typed20/opaque28, receipt12, import49, dependency47=immutable46+receipt1, capsule63=payload62+manifest1을 유지한다. source_count는 runtime21이며 mutable10과 혼동하지 않는다. template cfg 변경은113→114의 unit/root/experiment/source 식별 결속만이며 deadline exactint0·native_limits1씩·hardware/calibration false다. refs11에 receipt 자기참조를 넣지 않는다.

113의 JSON 양방향 역할 coverage·필수 노드·정확bool/int·중복키/overflow 거절, URDF 명시 profile 전 numeric scalar, binary/ASCII STL 전건 유한성/문법을 그대로 가져온다. IR은 같은 데이터이고 source/unit 결속만 새114다. empty STL format 양성과 원 full/물리 geometry 수용을 구분한다. 원45 physical 함수 AST는 verify_workspace 외에 같고 model 수정/clamp/학습/실물 보정은 없다.

현재113은 oldJSON3/ET03 실제 새 코드 폐쇄·numeric union2/currentopen0이고 historical112 BLOCK/open1/sourceEXH/noR3는 그대로다. 다음 DISTINCT numeric3 충분 임계도 유지한다. OBS-113-R1-01은 별도 관측기 실제 코드 폐쇄, FS semantic union3/currentobserver1/open0·다음semantic4 충분 임계이며 old110 sourceEXH를 되돌리지 않는다. 이번 clock 비용 문제의 class/중복 여부·착지·다음 충분 임계는 **첫114 L2 비작성자가 사전 확정**한다. 작성자는 새 sourceEXH나 기존 class 증가를 자의 선언하지 않는다. 제어/소비 역할 분리의 우회가 발견되면 실제 원인 착지에 따른 source 판정을 받는다.

## 4. D: identity 결과는 숫자 검증 결과가 아니다

기존 bind_decision_schema(bytes)는 실행/I/O0이고 기존 producer/consumer/verify_workspace는 **매 사용 fresh 실제 policy**를 실행한다. public verify_workspace_receipt에는 skip/cache/fast flag나 caller contract를 추가하지 않는다. producer는 원 full8192/6241, consumer는 full math0·fresh data/metrics, physical API는 원래대로다.

새 별도 API를 제안한다:

```
verify_workspace_receipt_identity(bundle48, receipt_raw, independent_expected_sha)
  -> closed4 {unit: str114,
              scope: IDENTITY_ONLY_NOT_NUMERIC_OR_NATIVE_AUTHORITY,
              receipt_sha256: actual SHA,
              inputs_sha256: actual canonical input48 pins SHA}
```

이는 바이트 동일성 증거만 반환한다. data/metrics/numeric_contract·형식 적합 판정·native 권한을 반환하지 않는다. policy bind/self raw pin, closed48 exactbytes/private copy, actual receipt expectedSHA/closed12 schema/unit/scope/input/algo4/resultSHA 및 receipt 내 작은 타입 구조를 전부 확인한다. 후보 input의 대형 JSON/XML/STL 숫자를 파싱하거나 policy code를 실행하지 않는다. control cfg를 읽을 경우 독립 freeze/expectedSHA가 결속한 원 template와 정확 active stamp, 기존 budget/정확 타입 검사를 먼저 충족해야 하며 임의 cfg 숫자를 신뢰하지 않는다.

검사 공통부는 구조·hash 검증으로 factor하고 numeric 소비 API는 그 뒤 반드시 actual fresh policy를 실행한다. identity API는 workspace data/metrics를 반환하는 내부 경로에 진입할 수 없다. caller가 identity 결과를 numeric_contract로 넣으면 거절한다. expectedSHA는 후보 receipt의 자기hash가 아니라 final freeze/dependency와 비작성자 검토가 결속한 독립 값이다. 이 역할의 차이를 API·scope·시험으로 드러내고 identity 양성을 숫자 반례 폐쇄로 세지 않는다.

## 5. B/C: 현재 바이트는 매번 확인, 숫자 소비 시 다시 실제 policy

B context/control metadata와 Runtime.verify/session_now는 매번 current plan/finalL2/freeze/review/approval·source21·독립 receipt·입력48의 이름/길이/hash·active config stamp·budget/claim/execution 결속을 확인한다. 이 경로는 위 identity API를 쓰며 전체 숫자 policy를 실행하지 않는다. 이전 context/input snapshot/hash/authority를 재사용하지 않는다. 검증 비용을 원 owner 밖으로 옮기지도 않는다.

Runtime.workspace_authority는 원7키/current decision48 바이트 pin과 receipt/template/active raw를 같은 원 scope 안에서 새로 확인한다. C provider는 pure 원token/thread/end→원 min childphase→actual current B authority→전체 current job/input/source/policy/receipt 이름·bytes/pins→정확 template projection 순서를 유지한다. 그 with 안에서 **D의 기존 숫자 소비 API**를 호출하므로 전20 typed 파일을 실제 새 policy로 검사한다. 같은 D 두 번째 use·postyield exit까지 owner를 유지하고 stale/current mutation·부모종료·동일end 재진입·다른thread를 거절한다.

clock_probe의 원20은 함수 진입에서 시작하며 session_now/중첩 clock_exchange/실제 OS 프로세스·종료·cleanup2까지 같은 min end를 쓴다. 해당 제어 경로의 정책 실행 횟수는0, workspace producer/consumer의 실행 횟수는 각 실제 사용마다1 이상으로 관측한다. 정책을 먼저 실행해 둔 캐시로 대체하지 않는다. known-end 전 read0·first stateless HELLO20/차감·canonical float·helper/완성 argv8000·다섯째 admission/exportNone·EOF/UNKNOWN을 그대로 지킨다.

## 6. 필수14 AC와 반증

| ID | 필수 수용 조건 |
|---|---|
| B1 | final plan/L2/freeze·typed14AC·B/C/D/integration/performance 각PASS·nativeapproval 없으면 actual root 첫remote 전 거절 |
| B2 | 원 HELLO20/float/known-end read0/helper/새 entropy 완성argv8000미만·실제 caller 결속 유지 |
| B3 | source9+harness1/deps47/runtime21/key48/import49/receipt12/capsule63·독립 SHA·배타생성·변조 거절 |
| B4 | metadata identity 경로 전current48/source/authority 확인·원 token/end/thread/process/EOF/UNKNOWN·cache0 |
| C1 | 세 caller→actualB→actualD numeric API·sameD second use·새 실제policy에 도달 |
| C2 | 원 template→active exactstamp·original20/cleanup2/global2700·native/headroom/물리 값 불변 |
| C3 | current job/model/ref/source/policy/receipt/authority 변조와 부모종료/동일end/다른thread/postyield 거절 |
| C4 | import→정지 성공→42초 motion 원 순서·실패 후 후속 NOT_RUN·원 회수/정지 유지 |
| D1 | identity API는 closed4 evidence만·data/metrics/contract/권한0·numeric 소비로 전환/skip/cache/flag 우회0 |
| D2 | actual full reference 동등·FS 차단·원physical45AST·JSON3/ET03/all-format/coherent consumer 반례 및 정상 유한 대조 유지 |
| I1 | actual B producer→D 및 C→B→D whole current source21/input49·첫/두 번째 사용을 비작성자 독립 재현 |
| I2 | source69/CAD22/critical112/113·원 실패/원장/임계·cap/회차·fresh freeze 실제 요약·root 음성 결속 검증 |
| P1 | unmodified 실제 clock 경로 원20 안 identity 확인+실제 OS clock+cleanup 완료, all-format policy call0·cold/반복 원권위·stall/current변조 음성 |
| P2 | numeric producer/consumer는 매 사용 actual policy 실행·identity-only 소비/단독 `_run_policy` 생략 대조와 old 반례 폐쇄를 별도로 확인 |

typed review는 unit114/phase/실제 최종plan·freeze SHA·required14/met14/unmet0과 B/C/D/integration/performance 개별PASS/미결0이어야 한다. 기존12행/old113보고서는 허용하지 않는다. main은 보조 finalSHA를 pin하고 순환하지 않는다. 새 codePASS도 target native 수용이 아니다.

HOST는 원 시험과 변경 영향 통합을 돌리고 실제14 AC에 대응하는 새 회귀를 추가한다. control path에서 fresh policy 실행을 막아둔 in-memory 대조는 통과해야 하고, numeric path에서 그 실행만 생략한 대조는 실제 ET03 검출 능력을 잃어야 한다. all-format policy가 느리다는 이유로 input hash mismatch만 숫자 거절로 세지 않는다. 실제 current B authority를 써서 metadata/clock의 반복 policy0을 계측하고, 정책 guard를 느리게 만들거나 I/O를 막는 explicit HOST seam을 공개한다. 원20을 늘리거나 실제 raw 입력을 줄여 passing fixture로 만들지 않는다. target 원격 함수별 profile은 이번113 자료에 없으므로 최초114 성공 전 성능 개선 수치/완주를 확정하지 않는다.

## 7. 승인 후에만 새 단일 원격45분

제안 scope는114 새 첫remote2700초/import1·render_smoke1·motion1이고 모든 최종 codePASS와 actual root missing-nativeapproval 거절 후 exact plan/freeze/finalmainL4를 새 closed12 nativeapproval에 결속한다. 승인 전 source0/native0이다. 그 뒤 일반 재확인으로 멈추지 않되 실패도 같은 단일시도로 소비하고 재시도0이다. local daemon/peer만 조회한 뒤 첫remote부터 시작하며 dummy SSH를 하지 않는다. 일반사용자 transport를 적절한 tool권한으로 첫시도부터 실행하고 OS/보안/UAC/시계·네트워크설정을 바꾸지 않는다.

정지 검증 통과 뒤에만 원42초/5040step/5041obs/421frame 동작을 한다. 실제 닫힌 회수자료를 원 f34911 관측기와 같은 prearmed exact A owner 아래 local audit하며 remote Runtime/cross-host mono 비교/추가 SDK/SSH를 만들지 않는다. 관측도구 새unit 변경도 별도 실제 block/정상 경로로 검토한다. 영상은 실제 frame이 있을 때만 만들고 actualframe수/encoded duration과 simulation duration을 구분한다. 실물CAN/RS485/포트·급전·flash·모터·설치·구매는 전부 제외한다.

## 8. L2 고정 자료

- OUT114/intake.json: 구현/native 미승인·source0·제안 caps/14AC.
- immutable46 raw SHA58c37df5add73181b4dbc9149c7626008770f31abde683260abfdd2e689d9f3f / canonical records SHA1b567f86f8c75b3f13260ed2ebde6de30950b61ed38e32827d7dd3f91f40d00a.
- role IR SHA698307f7ece43d64e9d0d044553d6b5bbcf3237545f1630c7577d8975faaf4a8.
- protected baseline SHA f15f9a8752d76b7fea35cd0f912b96018edb14fade7bb68ca3f828038dead4de.
- 113 finalmain b33e74c6849e92d30e9a547b6f5e169f2dcda6b0952fa34b8194de3b3a81cbaf, finallens41352cfcef336ffcfa74de59ef80b0cc589a63eae3ed79840b880d300f50ed7a. codePASS와 실제 prestart failure를 함께 읽고 실패 이력을 숨기지 않는다.
- OUT113/performance-diagnosis-errata.json SHA4a895e359d450e0840cf9a7b7703809142d22f1ea785261dcd2d21aa57577acc는 directory 미관측/transport 파일 부재를 구분하는 명시 addendum이며 원 보고서·raw·source·수용 판정을 바꾸지 않는다.
