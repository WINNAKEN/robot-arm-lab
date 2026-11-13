> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 089 — Isaac 연결 복구 후 시뮬레이션 재개 / CAN 오프라인 준비 분리

2026-10-31 KST. 사용자 지시: 「다시 issac 써서 시뮬과 can 통신 관련해서 작업을 이어가 아직 실물없으니 조심하고」.

## 권한과 새 단위

실제 Isaac 시뮬레이션 재개를 허용한 새 지시로 접수한다. 실물 없는 범위다. CAN 송신·급전·플래시·보정·모터 운전·설치·재부팅·전원 정책 변경·학습·구매는 제외한다. 모델링은 Claude 소유이며 CAD/URDF/BOM/펌웨어를 수정하지 않는다. hardware_approved/physical_calibration은 false다.

089A 시뮬레이션 실행 재결속은 M/검수급 45분 상한으로 분리한다. 이번 첫 시계 2026-10-31T00:13:37Z, 종료 00:58:37Z(한국 09:58:37), prepare/launch 마감은 00:43:37Z다. 사용자에게 별도 45분을 명시 승인받았다고 쓰지 않는다. 새 지시 범위에 정책 상한을 보수 적용한다. L2/L4 각 최대2회, native import/render_smoke/motion 각1회·600초·재시도없음·발사900초 여유다. 085 이하 종료된 시간·예약·검토 예산은 재사용하지 않는다.

089B CAN 로그→사람용 기록 연결은 별도 후속 S/M 단위다. 이번 시뮬 실행과 물리 통신 검증을 합치지 않는다. 현재 턴에서 자료 대조까지 하고, 새 구현은 독립 계획/검토와 예산을 먼저 선언한다.

## 출발 증거

- 085 기능 기준은 HOST283·L4R2 PASS이며, import 로컬 발사1회는 Remote create에서 실패했다. 과거 상태/실패/커밋을 수정하지 않는다.
- 이번 읽기 확인: isaacpc SSH 성공, Tailscale Running/Online/Health없음, GPU RTX3500Ada 12282MiB·54MiB 사용·0%, kit/Isaac SDK 프로세스 관측없음. 기존 pythonw3.13 프로세스는 이 작업 소유가 아니며 손대지 않는다.
- 원격 `C:/isaacsim_remote/robot-arm-lab/085/runs`는 ABSENT다. 따라서 085의 SDK child 부재 기록과 양립한다. 새089 원장은 새 경로에 둔다.
- 어제 Kernel-Power506/507과 Tailscale 절전 감지·relay 오류를 대조했다. 10/30 16:59~10/31 00:48 KST의 실제 Modern Standby가 확인됐다. 화면 요청 호출자는 미확정이다. 연결 상태만 다시 확인하며 자동 절전 설정은 변경하지 않는다.

## 089A 구현 범위와 수용 기준

1. `src/simulation/floating_balance_run/`의 동결16파일을 새 `src/simulation/floating_balance_resume/`로 복제한다. 새 output은 `outputs/isaac-resume-089/`, 원격은 `C:/isaacsim_remote/robot-arm-lab/089/runs`, experiment는 `floating_balance_089`다. 변경은 driver의 output/experiment/remote root/계획SHA, config의 root/experiment/deadline, test_scene의 결과 경로, README의 단위 설명에 한정한다. 물리/렌더/관측·검증 알고리즘·SDK는 바이트 동일을 확인한다. config는 허용한3키 외 구조 동일을 검증한다.
2. 085 테스트를 새 경로로 결속한 HOST 실행기/독립 테스트 사본을 output에 둔다. 기존 출력·source·HOST자료는 쓰지 않는다. 기본48·scene·13개 HOST 결과의 실제 합계와 원 출력 및 동결 해시를 저장한다. 구현 변화가 실행 재결속 범위를 벗어나면 멈춘다. 085의 HOST283을 새 결과로 복사하지 않는다.
3. L2 및 비작성자 L4 통과 뒤 import1회. 성공 증거를 실제 consumer로 검증한 다음 render_smoke1회. 원 정착·중력·바닥·캡 기준을 통과할 때만 motion1회. 조건 미충족/연결 실패/timeout은 원자료 보존 후 다음 목적 미실행. 자동 재시도나 게인·기준 완화는 없다.
4. 원래 구속·감쇠/외력 미분리, robot PD/포화 UNKNOWN, floating root 독립 운동 교정 NOT_DONE·15항 PROVISIONAL을 유지한다. velocity-only EXHAUSTED 및 기존 정착 실패/class·임계는 그대로다. 현 URDF 물성은 가정이고 최종 큰모터 모델 수용이 아니다. 링 보류·포그 숨김·self collision OFF·floor ON 유지.
5. 확보된 native 결과·부모 회수·원 journal/full15·provenance를 구분한다. 정상 원봉인 자료에서 영상 생성이 가능하면 로컬 생성·decode·첫/중/끝 대조한다. 실패 자료는 별도 결속 검증 없이는 성공 영상으로 만들지 않는다. 이번 지시는 외부 업로드를 요청하지 않았으므로 Drive/Notion 전송은 하지 않는다.
6. 결과·현재상태·다음 지점을 결과문서/result.json과 최소 HANDOFF/SESSION_HANDOFF에 기록한다. Git 소유 변화와 원085/기존 입력 SHA 불변을 대조한다. push는 없다.

## 독립 검토 가용성 / 현재 차단

로스터 `C:/projects/.claude/prompts/topology-roster.md`는 Codex 메인의 L2에 Sonnet 필수, L4에 Sonnet을 둔다. 표준 경로 `agent-bridge.py --help`는 CLI 실행 전에 Codex Python lint hook이 기존 483/484/494/495/510/527/540행의 absolute Windows path를 지적해 차단했다. 도구 자체를 수정하거나 다른 호출법으로 검사를 우회하지 않는다. 이 가용성 문제를 외부 검토 성공으로 쓰지 않는다.

2026-10-31T00:27:18Z 재개 시 사용자가 「동일 계열 비작성자 검토로 진행」을 명시 선택했다. 이 단위의 비작성자 검토 폴백을 허용한 상위 결정으로 기록한다. 같은 계열 편향을 모든 검토/결과에 명시하고 기존 외부 계열 미검증 이력도 유지한다. 원래 종료 00:58:37Z 및 발사마감 00:43:37Z는 연장하지 않는다. L2 PASS 전 구현, L4 PASS 전 SDK 발사는 금지한다.

## 089B 사전 대조 결과

실제 진단 main은 기본 DISABLED JSON 한 줄이며 hardware_approved=false/CAN_started=false다. 준비 경로의 terminal은 숫자 state/error, bus/close 요약, kind/error/at_ms/rx_dequeued_ms/id/dlc/flags/value/data 이벤트를 낸다. 프로필 템플릿은 observed null/UNCONFIRMED와 expected를 분리한 기록용 JSON이며 펌웨어 입력이 아니다.

따라서 다음 최소 CAN 구현은 저장된 로그와 관측 기록만 받는 오프라인 보고서 변환이다. 숫자 enum 의미·missing/mismatch bit·원문 provenance·DISABLED/실패/미완료를 보존하고 ReadyForReview를 물리 승인/PASS_READONLY로 승격하지 않는다. Isaac 관절 운동 성공과 CAN 프로토콜·RTOS/선로·정지 실측도 서로 대체하지 않는다. 실제 포트/장치/네트워크 연결 기능은 넣지 않는다.
