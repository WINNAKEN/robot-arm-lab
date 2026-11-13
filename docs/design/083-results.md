> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 083 결과 — full6D 기준물 통과, 큰 동작은 시간 초과

종결 L4 R2는 9/0 PASS다. 수용 범위는 실행 절차·회수 자료·진단 영상과 주장 한계이며, 큰 동작의 공식 FAILED와 물리 미수용을 유지한다. 같은 계열 검토의 잔여 편향을 기록했다.

실제 Isaac 가져오기와 2초 정지 시험은 통과했다. **52초·521프레임 동작은 수집됐지만 큰 동작 실행은 공식 FAILED**다. 600초 watchdog 뒤 자식이 종료됐으며 최종 report.json/terminal.json이 없다. 실행 제한이나 수용 기준을 바꾸지 않았다.

| 항목 | 결과 |
|---|---|
| HOST / 계획·소스 검토 | 225 PASS / L2 R1 9·0, L4 R1 9·0 |
| 가져오기 | IMPORT_VERIFIED, 194.359초, actual/policy 0/0, REAPED |
| 2초 정지 | SMOKE_VERIFIED, 137.641초, actual/policy 0/0, REAPED |
| 비영 COM full6D | 정지 시험 원본에서 VERIFIED, 불일치0, 최대 성분 오차 1.82162e-5 |
| 기준물 PD-only | force/acceleration 각48표본, 약0.01N·m, 각48/48 cap 근처 — 로봇 실측 아님 |
| 로봇 M/C/G | M=(1,15,15), C=(1,15). 원9×9 계약에 UNSUPPORTED, 0대체·절단 없음 |
| 큰 동작 | actual1 / policy124 / TIMEOUT / REAPED. 종료·정리 포함605.203초 |
| 로봇 PD·포화·유일 원인 | UNKNOWN / UNKNOWN / INCONCLUSIVE |

큰 동작에서 원 journal 6241행, 마지막 시간52초, PNG521개를 회수했다. 원격 recovery ZIP의 SHA와 로컬 ZIP이 같고, 모든 추출 파일을 ZIP 원문과 대조했다. 각 프레임 PNG·RGBA 해시/CRC, freshness, 명령·시계·q/qd·자세의 원 journal 결속을 검사했다. **이는 누락된 native terminal 봉인을 대신하는 공식 실행 수용이 아니다.** 진단 영상만 허용하는 별도 증거다. 과거 실행에 report/terminal을 새로 만들지 않았다.

회수 구성요소를 대조한 파생 분석에서 full6D 기준물은 다시 통과했고 M15 관측520개는 미지원으로 남았다. 원 partial 체크포인트의 실패 관절·구간 쌍은15개, 최대 정착 오차2.515213582도·5.128378810도/초다. 시간/q/qd/목표6241행은081과 정확히 같다. 최종 보고서가 없으므로 이를 새 전체 물리 수용으로 승격하지 않는다. 제어 개선이나 정착 원인 확증도 아니다.

최종 저장 경계에서 init-boundary JSON은 VIEW_READY, 중간 tmp가 남았다. audit 최종 직렬화 경로를 조사할 근거이며 유일 원인을 확정한 것은 아니다. SDK runtime 경고와 TCP trail 폭 fallback 경고도 원 로그에 보존했다. 원격 시계·프로세스 조회는 SDK 추가 실행이 아니며 조회1회의30초 시간 초과도 native 결과와 구분했다.

실제 원속도52.1초/521프레임과 요약17.3초/173프레임 영상의 전체 디코딩 및 첫/중간/끝을 확인했다. 파일명은 FULL_CAPTURE_TIMEOUT-FAIL이다. 원속도 영상 (비공개 링크 제외), 요약 영상 (비공개 링크 제외)을 기존 Drive 날짜 폴더에 저장하고 크기·MIME·부모를 재조회했다. 원격 동영상 SHA와 공개 공유 권한은 확인하지 않았다. JSON은 로컬에만 남겼다.

원장 import/정지/motion 각1회, lock 해제. 082 이하 원자료·실패·class와 velocity-only EXHAUSTED를 보존한다. 마지막 저장 수리는 소스/HOST 범위에서 수용됐으며, 이번 timeout·15항 동역학 계약·로봇 정착은 미폐쇄다. 후속 [084 제안](084-floating-base-force-balance-proposal.md)은 미실행이다. 물성 가정·자기충돌OFF/바닥ON·링보류·포그숨김, 실물 보정·모터/CAN 운전·재부팅·설치·구매·학습 제외를 유지했다.
