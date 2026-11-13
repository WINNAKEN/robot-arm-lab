> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 036 — 최신 제어 소스 타깃 빌드 재검증

2026-10-26 사용자 요청: 체크리스트 저장 후 제어 준비 계속. 실물 보정/모터 운전 제외, 링 보류.

범위: 제품 소스 무수정. 기존 pinned SDK/스크립트로 inactive와 prepared ESP32-S3 타깃 compile/link를 순차 재실행하고, 현재 HTML/JS와 prepared ELF 내 바이트를 대조한다. 기존 runtime SDK stub 회귀로 미승인 실행 경계도 확인한다. WROOM 빌드/플래시/USB/장치/네트워크/실물 전원 접근 없음. 준비형 빌드를 운전 승인으로 해석하지 않는다.

L2 최대2/L4 최대2, 비작성자 검토. 기존 PA/terminal/startup/firstfault 소진 이력과 다음-instance 임계 유지. 제품 반례 수용 시 해당 원장에 따라 중단/처분, 자동 제품 수정 없음. 외부계열 검토는 기존 중앙 도구 차단/NOT_RUN 잔여 유지, 우회 없음.

절차: (1) L2 검토 (2) 기존 build-target.ps1 -Mode inactive/prepared -EvidenceName readiness036-각모드 (3) inspect-elf-assets.py로 현재 웹 자산 대조 (4) tests/phone/run-runtime.ps1 실행 후 원출력 복사 (5) 결과/범위/미검증 항목 기록 (6) L4 비작성자 확인 및 인계 갱신.

수용 기준: 두 빌드 exit0 및 source-before/after 일치; prepared 최종 ELF 현재 웹2개+NUL 일치; 실제 sdkconfig 하드웨어 승인 off; host runtime 회귀 PASS. 실패/미실행은 그대로 표시. 모든 생산 src/firmware 파일의 작업 전후 SHA256 동일. 과거035 controlled clock 수용을 wall-time/실물로 확장하지 않는다.

부대 문서: docs/specs/bench-no-can-checklist.md. BOM에는 사용자 보고인 모터/드라이브 도착과 CAN 부품 배송 대기를 반영하되 외장 안테나 옵션 실물 검증·구매 상세는 추정하지 않는다.

증거 정본: `.dev/target-readiness-evidence/disposition.md`. 산출물은 PC에서 생성한 미플래시 빌드다.
