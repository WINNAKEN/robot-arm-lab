> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 094 결과 — 고정 기저 COM 수용 / 큰 동작 39.5초 부분 실행·미수용

2026-10-31. **기저 COM 불일치는 이번 고정 기저 정지 시험에서 재현되지 않았고 원 검사를 통과했다.** 큰 동작은52초 중39.5초 체크포인트까지 기록됐지만600초 작업 한도 초과로 종료됐다. 34초 phase endpoint의 J3/J5 위치 오차 미달도 이미 관측됐다. 전체52초 완료·전체 물리 수용을 선언하지 않는다. 실물CAN/급전/flash/모터/보정은 모두NOT_RUN·hardware_approved=false다.

## 수리·검토·지연 활성화

093의 순서 오류를 고쳐 stopped timeline에서 정확한 Scope의 typed PhysX 자기충돌 attr에 false를 작성·읽기 확인한 뒤 after snapshot을 저장한다. 정책 증명은 존재/타입/작성 상태/시간샘플/variability/custom/value를 확인하고 허용 속성 하나만 제거한 다음 나머지 USD 전체 불변을 검사한다. 원 Newton2속성·API 목록 수리도 유지했다.

L2R1·L4R1 PASS9/0, HOST18그룹439건·비작성자 독립196건, 실제USD 양성/음성 통과다. Source17/하네스23·보호1380경로를 검토했다. 실제USD 준비 검사는 SimulationApp/물리 실행이 아니며 미등록 UI metadata 경고를 원stderr에 보존했다. 같은 계열 비작성자 폴백의 공통 편향은 남는다.

사용자가 승인한 대로 검토 전에 예산을 시작하지 않았다. deadline0의 실제 prepare 거부도 확인했다. 검토된 활성화 프로그램이 최초prepare직전 **10:53:26.73Z~11:38:26.73Z**(KST19:53:26~20:38:26)의45분을 한 번만 만들었다. 새 발사는11:23:26.73Z마감이다. 코드16파일의 바이트는 검토본과 같고 config의deadline_unix 숫자 토큰 하나만 바꿨다. source-freeze-r1은 검토템플릿, config-before-budget·runtime-budget·execution-freeze·activation은 생성된 실행 설정과 원 해시의 정본이다. 템플릿17개 전체가 실행 중에도 바이트 불변이었다고 표시하지 않는다.

## 정지 시험 — 수용

import `6073914cdbb944f3bb96bec622c488cb` IMPORT_VERIFIED 후 정지 `0ae8cd52721a4c12b0fee82364ce83c7`는 **SMOKE_VERIFIED**였다. 실제 fixed_base=true, Root=Base, 원차원 M9×9/C9/G9, 동역학 raw20/수용20/query오류0이다. World COM 위치 차분과 실제 속도의 최대잔차는 x/y/z 모두0m/s, 실제 root속도도0이었다. 허용오차를 넓히거나 속도를0으로 대신 채우지 않았다. 명시 PhysX OFF·Newton OFF·원 정착/한계/FK/바닥/중력 기준이 통과했다. 240step·21PNG·2.1초 영상 전체decode도 통과했다.

Root API를 fixed joint 조상으로 옮긴 뒤 고정9항 파싱과 COM 일관성을 관측한 것이다. 과거 floating15의 moving-root 의미 교정을 완료하거나 원 불일치의 유일 원인을 증명한 것으로 확대하지 않는다. PD 센서 교정/로봇 포화 판정도 여전히 UNKNOWN이다.

## 큰 동작 — 시간 초과·중간 정착 미달

모션 `229f9cb6bfde453396261327f3a79e50`은 정지 수용 후 한 번만 발사됐다. 원 exit는 actual child1 / policy124 / TIMEOUT / REAPED / timed_out=true, Native감시 벽시계605.390초(600초대기 후 종료·회수 포함)다. 원본 terminal.json/report.json은 없으며 생성하거나 성공으로 바꾸지 않았다. parent recovery는 성공 native seal이 아닌 실패 스냅샷이다.

검증 가능한 부분 체크포인트는39.5초·4741관측·396PNG다. 전체52초 중 이후12.5초는 이 체크포인트 자료로 수용할 수 없고, 추가 journal 꼬리를 사용하지 않았다. raw q의 확인된 범위에서 J1~J6 excursion은 약120.24°/55.51°/46.56°/50.96°/36.62°/105.42°다. 실제로 큰6축 동작이 수행됐지만 완주와 물리 수용은 별개다.

기록된 정착5개 중 initial/raise/sweep_left/sweep_right는 통과했다. reach_high_right_settle의34초 phase endpoint에서 절대 위치오차가 J3 0.584715°, J5 0.520335°로 원0.5° 기준을 넘었다. 해당 행의 절대 속도0.814251°/s·0.740712°/s는 원1°/s 이하이므로 이 두 실패를 속도 실패로 바꾸어 표현하지 않는다. 실제 checkpoint 함수는 endpoint 한 행의 abs(q-target)/abs(qd)를 계산하며 window_s0.5 동안의 최댓값이나 지속 안정성을 측정한 것이 아니다. 남은 전체 체크포인트는 미검증이다. 기존 정착15실패·velocity-only EXHAUSTED를 지우거나 이번 부분자료로 폐쇄하지 않는다.

Native child 시작부터 첫 PNG까지 약4분45초, 첫~마지막 부분 프레임 사이 약5분17초가 걸렸다(정확값은remote-final.json·exit.json). 따라서600초 한도는 SDK/장면/사전검증과 경로 수행을 함께 포함해 완주 전에 소진됐다. 구간별 비용의 유일 원인이나 최적화 효과는 아직 측정하지 않았다.

## 부분 영상과 종료

`encode-partial.py`는 원PID/job 체인·실패 parent snapshot821파일 해시·396PNG의CRC/크기/IEND·4741행의 연속 journal/checkpoint 대응을 검증한 뒤 별도 **PARTIAL** 영상만 만들었다. 640×480/10fps/396frame/39.6초이며 전체decode PASS다. 이 PASS는 인코딩 무결성이며 완주·정착·물리 수용이 아니다. 원retrieved는 수정하지 않았다. 최초 스크립트의 SDK record에run_id를 가정한 오류는 job_hash/providerPID로 바로잡았으며 시뮬레이션 재실행은 없다. 마지막12.5초를 전부 미실행이라고 단정하던 파생 필드도 ‘체크포인트 이후 미검증’으로 정정하고 최초 파생본을 보존했다.

실제 원 PNG0/198/395를 직접 확인했다. 로봇이 보이며 서로 다른 자세이고 포그는 없다. ActualTCP trail의 widths primvar 경고는 원로그에 남아 있으며 시각화 경고를 물리 실패나 성공의 근거로 바꾸지 않는다.

원장 import1/정지1/motion1, 추가발사0이다. remote-final은 원기록 worker/native6PID가 모두 없고 lock=false임을 확인한다. 호스트 전체의 다른 사용자 앱이 없다는 뜻은 아니다. 최종 비작성자 L4R2는 원자료/부분영상·완료/미완료 구분을 감사하며 review/L4-r2.json을 따른다. 전체 목표의52초 완주·정착 수용은 미완료다. 후속095는 시간 한도를 명시적으로 조정한 관측 재실행 제안일 뿐 자동 실행하지 않는다.

원 실패·소진/임계·물성가정·링보류·포그숨김·자기충돌OFF/바닥ON·moving-root 교정미완료·로봇PD/포화UNKNOWN·CAD/URDF/BOM/펌웨어 무변경을 유지한다. 외부 업로드·설치·재부팅·전원정책 변경·구매·학습도 없었다.
