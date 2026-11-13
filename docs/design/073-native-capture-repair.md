> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 073 native capture integration repair

073의 조건부 두 번째 smoke를 위한 한정 API 수리다. 원 실험·실패 원장과 A/B/C 준비 검토는 그대로 보존한다. D 시작 16:08:08 UTC, 종료 16:53:08 UTC를 옮기지 않으며 새 native 목적이나 실행 횟수를 만들지 않는다. 첫 import 1회와 첫 smoke 1회는 이미 소비됐다. 원 A 6개와 model/ref/SDK는 변경하지 않는다.

첫 smoke `61baa74aca9648a8b0c9472579fdaff4`는 actual/policy/shell/native 1, timeout false, REAPED, 111.39초로 끝났다. 원인 `Render node identity changed: rgb`는 같은 실제 Node wrapper/path와 증가한 compute generation을 NodeType 임시 wrapper의 주소 문자열과 비교한 데 있다. 실제 semantic `node.get_type_name()` API를 사용하고 호출 가능 여부를 먼저 기록한다. 설치된 SDK의 topology_commands.py 867/869행과 graph_controller.py 297행에서 이 호출을 확인했다.

동일 원자료에서 scheduled `1/30`과 실제 ReferenceTime `33333333/1000000000`은 1ns 미만 양자화 차이가 있다. raw scheduler pair를 별도 필드로 보존하고, 비교용 scheduled는 실제 ReferenceTime의 고정 1GHz 정수 시계로 exact-Fraction FLOOR 변환한다. 반올림 epsilon이나 stale frame 허용으로 대체하지 않는다. 원 RGB/reference/dispatcher generation 증가·동일 wrapper/path/semantic type·동일 RP time·render 전후 물리 상태 불변 조건은 유지한다.

수정은 B capture/test 두 파일뿐이며 원 source와 freeze/HOST 근거를 보존한다. 준비 검토 B 2/2 이력은 다시 열지 않는다. 원 계획의 native integration 수리 조건을 적용하는 D 하위 검토는 비작성자 1회로 고정하고 남은 D 시간에 포함한다. 새 45분 예산으로 취급하지 않는다. HOST에서 의미 타입의 안정성, exact timestamp encoding, stale generation/clock rejection을 대조하고 수정된 B 지문·실패 run ID에 결속된 비작성자 PASS를 받은 뒤에만 smoke 2/2를 사용한다.

원 motion.ndjson의 첫 행에서 J2 속도 0.525834rad/s가 원 한계 0.5rad/s 및 현재 허용 0.501rad/s를 넘었다. 이 값을 숨기거나 cap·게인·판정을 바꾸지 않는다. API 수리 뒤 완전 smoke에서 유효 동역학 FAIL이면 큰 motion은 실행하지 않는다. 사용 가능한 실제 RTX 영상만 FAIL 상태와 함께 남긴다. 실물 보정·모터/CAN·설치·재부팅·학습·링 검증은 제외한다.
