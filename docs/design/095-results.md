> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 095 결과 — 52초 완주 확인 / 정착 원기준 미달

2026-10-31. **52초 전체 동작을 한 번의 native 모션으로 완주했다.** 6240스텝·6241개 연속 관측·521PNG와 원봉인 전체 보고서를 검증했다. native 감시 시간은 778.359초로900초 안이고 종료0/REAPED/시간초과false다. 게인64/16·cap·물성·52초 경로·모든 수용 기준은 바꾸지 않았다. 전체 물리 수용은 정착 미달 때문에 **BLOCK / LATEST_SCENE_DYNAMICS_FAILED**다. 실물CAN/모터/급전/flash/보정은 NOT_RUN·hardware_approved=false다.

## 검토·시계

L2R1 PASS9/0. L4R1은 frozenUSD rawSHA/정확타입 소비 누락 F1로 BLOCK8/1이었다. 원 source17/harness27/HOST/근거67파일을 보존한 뒤 activate.context의 공유 typed gate와 실행기 --preflight를 수리했다. HOST20그룹523, 독립R1 253·R2 132 및 변조검사, L4R2 PASS9/0으로F1폐쇄다. 실제USD 원본·정책/API 양음성은 source 불변과 rawSHA로 결속했다. L4 2/2를 코드 수리에 썼으므로 **사후 정식 독립 runtime 검토 NOT_RUN**이며 추가R3는 없다. 아래 사후 검증은 작성자 기계검사/감사다. 동일계열 공통편향은 남는다.

검토 후 최초native직전45분을 한 번 활성화했다: 2026-10-31T12:37:51.473855+00:00~2026-10-31T13:22:51.473855+00:00. 실제 최초 원격 supervisor시작 2026-10-31T12:38:16.822007+00:00, 마지막 native종료 2026-10-31T13:02:25.272576+00:00. 모션 발사마감 2026-10-31T13:02:51.473855+00:00. import/정지600초·여유900초, 모션900초·여유1200초 유지. 검토16파일 바이트 동일이며 config.deadline_unix 숫자 토큰 하나만 활성화했다. 실행17핀·모든job입력 결속, 원094/보호2740경로·R1 67파일 불변이다. 원 시계/원장 삭제·재설정·추가native는 없다.

## native 관측과 원 판정

- import `f6ebdf16af4a45b6b1f00fa4c0e8fc5b` IMPORT_VERIFIED, native163.781초/종료0.
- 정지 `7d46dc1326184241b266254d8ba585d4` SMOKE_VERIFIED, native239.281초/240step/21PNG. 원COM·정착·한계·렌더 등 모두 통과.
- 모션 `fe9882c29e1b468eb2549205bbc4c993` 52초/6240step/6241obs/521PNG,7개 endpoint 중6PASS·1FAIL. 나머지 gripper/FK/native render/완주/한계·속도/바닥/중력 margin/큰 동작/fixed9 관측 검사는 모두PASS다. 34초 reach_high_right_settle에서만 다음 위치 미달이 남았다.

| 관절 | 절대 위치 오차 (기준≤0.5°) | 절대 속도 (기준≤1°/s) |
|---|---:|---:|
| J3 | 0.584715293° | 0.814251237°/s |
| J5 | 0.520334638° | 0.740711924°/s |

이는 phase endpoint 한 행의 절대오차이며 지속 정착창 최대값이 아니다. 44초·52초 endpoint는PASS다. 원15정착실패/velocity-only EXHAUSTED를 지우거나 이번 두 위치 미달을 속도 수리로 재분류하지 않는다.

정지 raw20/수용20, 모션 raw520/수용520·query오류0이다. 실제fixed_base=true/Root=Base/M9×9/C9/G9 전체 차원과 worldCOM 위치차분 대 native속도 잔차XYZ0을 재확인했다. rawroot속도0/finiteCOM속도0이며 대신 채운 값이 아니다. 원 tolerance 유지. 이는 고정 기저 관측 범위이며 moving-root 독립교정 NOT_DONE, PD/포화 UNKNOWN을 유지한다. 질량/COM/관성 가정과 링 보류도 그대로다.

## 원 회수 실패와 읽기 전용 복구

Native는 정상 종료했으나 후속 export의 별도SSH 기본120초 대기가 만료돼 최초 `validation.json`/`current.json`은 FAILED다. 이때 sdk_connected=false는 일반 예외 표기이며 실제SDK 미실행을 뜻하지 않는다. 원 transport는 nativeSSH return0/timed_outfalse다. 보고서/terminal/exit가 원격에 남아 있었으므로 **SDK/SimulationApp/물리 재실행 없이 stdlib ZIP/SCP로 기존1077파일만 복사**했다. 원봉인1070파일, PID/job 체인과 전체 원본 해시를 검증하고 원래 consumer에 다시 읽혀 별도 `recovered-validation.json`의 LATEST_SCENE_DYNAMICS_FAILED를 얻었다. 최초FAILED·원export한도·원기록은 덮지 않았다. 회수 경로 자체의120초 계약은 미수리이며, 어떤 구간 비용이 지배했는지의 독립 계측/판정도 없다. 새로운 core수리·라운드·native 실행은 이번 단위에서 하지 않는다.

## 영상·종료·남은 일

원521PNG의CRC/640×480/IEND·전체 연속 journal와 report의6241행 일치·모든frame sidecar q/qd/clock·7endpoint를 확인했다. 1배속52.1초/521frame·3배속17.3초 영상 전체decodePASS. 직접 native0/260/520 화면에서 로봇 표시·서로 다른 자세·바닥·포그숨김을 확인했다. 영상decodePASS는 전체 물리 수용이 아니다. 파일명 FAIL은 정착 원판정을 유지한다. provenance는 video/에 각run별로 있다.

원기록 native/worker6PID가 모두 없고 lockfalse, 원장3예약(import1/정지1/motion1)임을 읽었다. 호스트 전체 다른 앱의 부재를 뜻하지 않는다. 로컬 증거/영상만 저장했고 외부 업로드·실물CAN·설치/재부팅/전원정책 변경·튜닝은 없다. 다음 범위의 입력은 34초 J3/J5 위치 정착 원인과 export120초 회수 계약이다. 새승인·검토 없이 실행하거나 기준을 완화하지 않는다.

정본: outputs/isaac-complete-motion-095/result.json, native-audit-*.json, root-com-witness-*.json, 원runs/*/retrieved 및 최초/복구 validation, review/L4-r1.json·L4-r2.json. CodePASS와52초완주,전체물리BLOCK을 구분한다.
