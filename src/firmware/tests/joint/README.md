# 오프라인 각도 제어 진입 시험

```powershell
& src/firmware/tests/joint/run.ps1 -Mutations -Regressions
```

설치된 프로젝트 Zig로 strict C++17/-Wall/-Wextra/-Werror/-pedantic 빌드한다.
승인021 코어/기구학과025 receipt의 정확한 소스 해시를 검사하고, Python021의 실제 변환 함수로
126개 절대좌표 oracle을 만든다. 런타임에 이 Python 코드나 파일을 ESP32가 읽는 구조는 아니다.

기존 실제 run Fake/Fixture/51회귀를 포함한 TU에서 새 BenchRun::request_joint_step을 호출해
실제 Gate→MKS codec→Fake CanPort FD 바이트/완료/StopF7까지 검증한다. 두 축과 양음,
deg/rad·서로 다른 모터 방향/감속비·보정 오류·권한/티켓 오류·불변 복사·철회를 검사한다.
보정값은 시험 전용이며 실제 장착값이 아니다. 기존 boot/runtime/phone host 회귀도 별도 실행한다.

양성 실행 성공 후 단위변환 삭제/offset 삭제/미승인 보정 허용의 compiled 변형을 각각 빌드하고
exit1 + FAIL assertion으로 검출해야 한다. 컴파일 실패를 변형 검출로 세지 않는다.
출력은 `.dev/joint-control-evidence/build`의 명령/컴파일/실행 log와 해시 result다.
실제 장치·CAN·네트워크·플래시·SDK target 실행은 하지 않는다.
