# 개발과 기록

실제 하드웨어 없이 검토할 수 있는 변경부터 시작합니다. 비활성 기본값·조회 허용 목록·판정 기준을 임의로 완화하지 않습니다.

변경에는 문제, 수정한 이유, 확인 명령과 결과, 실제 장치 실행 여부, 남은 한계를 함께 적습니다. 중요한 결정과 실패/수정 과정은 `docs/development/JOURNAL.md`에 날짜와 함께 기록합니다.

```sh
python tools/check_public_release.py --write-manifest
c++ -std=c++17 -O2 src/bench/test_can_reader144.cpp -o /tmp/test_can_reader144
/tmp/test_can_reader144
python tools/check_public_release.py
```

manifest 갱신은 공개 후보 파일을 먼저 검사한 뒤 실행됩니다. 새 바이너리·외부 자료·캡처·네트워크 설정은 자동 허용되지 않습니다. 수정한 내용과 공개 파일 검사를 비작성자가 확인한 뒤 커밋합니다.

실제 CAN/TTL 명령, firmware flash, 모터 전원·Mode 변경, 보정/원점·이동은 별도 현품 확인과 명시된 시험 범위가 필요합니다. CI에서 장치에 연결하거나 실제 로봇을 동작시키지 않습니다.

장치 덤프·토큰·개인 사용자 경로·주문/메일·원시 로그를 issue나 PR에 첨부하지 않습니다. 외부 소스에는 정확한 라이선스와 출처를 함께 적습니다.
