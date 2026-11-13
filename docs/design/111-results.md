> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 111 결과 — 두 코드 결함 폐쇄, 실제 정지 검증 통과, 42초는 시간 여유 부족으로 미실행

2026-11-04 KST. 현재 정본은 이 문서와 `outputs/known-lifetime-controller-111/result.json`이다. 앞선 intake/current/검토에 쓰인 source0·native미사용 표시는 해당 시점 기록이며 수정하지 않았다.

- [관측] L2 R1 BLOCK → 마지막 R2 PASS10/0. 코드 L4 R1의 완성 명령 8003자 거절과 정상 canonical 부동소수 시각 거절을 원 바이트에서 재현하고 B2만 수리했다. 마지막 L4 R2 주/보조 모두 PASS10/0, 원 두 class는 각각 union1/open0/new0이다. B·통합 2/2 종결/noR3, C exact R1 PASS 유지/새 C 회차0이다. 같은 계열 비작성자 폴백의 공통편향은 남는다.
- [관측] 최종 HOST는 B18+C29=47 PASS, compile5/config1. source6 freeze `218ae912b843c6099594933bb1a25930f031ab5ba13cd45d080613e7f2e52350`, 최종 주 검토 `df4fa7d7b16cf1ee3dd42ac92ea00bed6af8d1b1c890627db7d4c06656219505`, 보조 `992a88fa638c50238720ef4dc61333356a72833ec236351c362f6554735057b0`. 게인64/16·cap·42초 program·모델·원 물리/시간 기준은 그대로다.
- [관측] 실제 root `--run --review-round 2`는 최종 PASS 뒤에도 native-approval가 없으면 통신/attempt 전에 exit2로 거절했다. 이후 기존 조건부 승인과 최신 계속 지시를 typed 권한으로 결속해 첫 원격 단일2700초를 한 번 소비했다. 최초 HELLO20초와 원remote기한을 유지했고 clock setter/UAC/네트워크 설정/실물CAN/급전/flash/모터/설치0이다. 로컬 sandbox의 Tailscale pipe 접근 거절은 원격 오프라인의 증거가 아니었으며 일반 사용자 외부 샌드박스 조회는 Running/대상online이었다.
- [관측] 실제 CLI는 05:23:46.695718→05:50:10.997243 UTC, 외부 캡처 경과1584.296초에 `FAILED_FETCHED`, exit2로 종결했다. 이 값은 로컬 preflight도 포함한 CLI 경과이며 원 native 기한의 재설정이 아니다. local SSH5개 모두 terminal/rawEOF/job active0, exit는0/0/0/1/0이다. remote controller 자식도 실패를 기록하고 종결했다. 회수 ZIP439파일/165,204,428 bytes, SHA `7dc14ccbce2cb3ae64d51c52f0521c528089bd733328534dfd3c96b34919ade1`을 보존했다. 단일 시도는 종결됐으며 남은 벽시계 시간을 재시도 권한으로 쓰지 않았다.

| 단계 | 실제 결과 | 독립 파일 재검산 |
|---|---|---|
| import | IMPORT_VERIFIED, 실제 SDK 자식 exit0 | source20/입력47·봉인23/직접 PID·CUDA/provider/11body·9movable 모두 재확인 |
| 정지 render_smoke | SMOKE_VERIFIED, 2초/241관측/21frame, SDK 자식 exit0 | 입력54·봉인74/모든 물리 checks=true, COM full6D 및 fixed-base root/전체9D 재확인 |
| 42초 motion | 준비 bundle 뒤 `Purpose launch headroom` 차단 | 입력135/원 FAILED·UNKNOWN 표시는 보존. 실행 시도·clock query·transport·native 회수 기록 부재와 실제 launch 소스 순서로 SDK 진입 전 차단을 확인 |

[관측] 로컬 `offline-observation.json`은 실제 remote Runtime을 로컬 시간축으로 위장하지 않고, 원 closed-return consumer와 원 process/provider/물리 소비자를 회수 바이트에 실행했다. import·정지 개별 accepted=true, 전체 native_outcome_accepted=false다. 정지의 모든 checks=true에 포함된 large_motion 항목은 이 2초 정지 프로그램에 대한 판정이며 42초 큰 동작의 수용이 아니다. 관절 정착·그리퍼·FK·속도/각도·바닥·중력 여유·nonzero COM·fixed-base root 기준은 완화하지 않았다. 최소 바닥 여유0.0174569m, 최대 중력 비0.9099958, COM reference fault0이다. 모델 질량/물성 가정은 실측으로 승격하지 않는다.

[관측] 원격 동일 호스트 기록에서 import 자식193.425초, 정지 자식240.680초가 확인됐다. 정지 자식 종료 시 잔여1873.171초로, 원 motion headroom1680초를 지키며 추가 준비에 쓸 여유는193.171초였다. 이후 준비·proof 재검산을 거쳐 실제 launch gate가 거절했다. 완성된 motion 준비가 실행 가능성을 보장하지 않는 실제 사례다.

[관측] 별도 로컬 profile은 원 pure verifier를 변경하지 않았다. workspace 전체 검산3회 누적80.591초/관측기 벽시계114.453초(약70.4%), full 8192 sample·6241 path/원 FK·중력 계산의 반복을 확인했다. 실제 C의 prepare/snapshot/smoke proof/consume에 동일 전체 검산이 반복된다. [추론] 정적 계산/기존 proof 반복이 headroom 소모의 유력 기여 요인이다. [미지] 원격 함수별 정확한 비용 분해는 계측하지 않았으므로 로컬 profile을 원격 profile로 부르지 않는다.

정지 프레임으로만 만든 `stationary-2s-verified.mp4`는 21frame/10fps의2.1초 인코딩이다. 실제 시뮬 시간은2초이며 큰 동작 영상이 아니다. first/mid/last 및 원 PNG hash·실제 렌더 지표를 확인한다.

원10831/1098/1106=45 source와 CAD/MP10 tracked22, 이전 실패·닫힌 회차·원장·raw/restoration/109/110 source-exhaustion은 그대로다. 이번 code 두 class의 다음 distinctunion2 충분 임계도 유지한다. 실제 성능/headroom 실패는 새 관측으로 남기며 독립 판정 없이 새 class·source 소진을 선언하지 않는다. 원 정착15·velocity-only 소진, PD/포화 UNKNOWN, moving-root 독립교정 NOT_DONE, 링 보류/실물 미검증을 유지한다.

다음 후보는 [112 정적 검산 선행·재사용 제안](112-static-workspace-preflight-proposal.md)이다. 111 통합 회차를 재개하거나 기한/한도를 늘리는 수리가 아니다. 새 source·검토·원격 권한은 아직0이며 새 범위/예산의 명시 결정이 필요하다. 원 111 source/권한/시도·회수자료는 수정하지 않는다. 외부 게시·push0.
