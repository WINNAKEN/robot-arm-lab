# CAN 진단 기록 오프라인 보고서

저장된 088 main 형식 NDJSON과 기록용 프로필 JSON을 읽어 JSON/Markdown 보고서를 만든다. 포트·장치·CAN·네트워크에 연결하지 않는다. 비JSON 부팅 문구가 섞이면 원본을 보존한 채 별도 추출 파일을 준비해야 한다. parser는 비JSON을 조용히 버리지 않는다.

```powershell
python ./src/diagnostics/can_report/report.py --log SAVED_LOG.ndjson --profile OBSERVED_PROFILE.json --out NEW_OUTPUT_DIRECTORY
python ./src/diagnostics/can_report/test_report.py
```

`--out`은 아직 없는 폴더여야 한다. 합성 HOST 예시에만 `--synthetic-host`를 덧붙인다. 출처 표지는 장치 인증이나 물리 승인을 만들지 않는다. 각 입력 1MiB, 로그 130행 이하의 정확한 JSON 레코드만 받는다.

DISABLED는 기본 비활성 출력, LOG_REVIEW_ONLY는 저장 로그 검토, INCOMPLETE는 누락 자료, INVALID_INPUT은 형식/모순 오류다. rc0은 파일 보고서 작성 성공이다. 실제 통신 PASS나 하드웨어 실행 허가를 뜻하지 않는다. 관측 null/UNCONFIRMED와 진단 최초 오류를 보존하며 C++ prepare_profile을 실행한 것으로 표시하지 않는다.

Fault 로그의 시각 역행은 원값·원순서를 유지한 anomaly다. close 뒤 역행을 관측해도 앞선 Clock/Service 등의 최초 오류를 덮지 않는다. RX dequeue 시각은 선로 도착 시각이 아니다. 이벤트 표가 실제 TX/RX의 인과성, 물리 정지·무토크를 인증하지 않는다.

원 로그/기록 SHA와 현재 C++ 파서 호환 소스 SHA를 남긴다. 이것은 동일 파일·현재 선언과의 대조이며 로그의 실제 생성 장치·펌웨어 SHA를 증명하지 않는다. 모든 출력은 hardware_approved=false, 실제 CAN/RTOS 시험 NOT_RUN이다. 실물 시험은 기존 수령 체크리스트와 별도 승인을 따른다.
