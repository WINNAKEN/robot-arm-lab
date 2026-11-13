> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 085 — 15항/최종 저장 수리 검토 통과, 원격 연결 단계 중단

승인 구간: 2026-10-30 11:41:04~12:26:04 UTC(한국20:41:04~21:26:04). 새 prepare/launch는12:11:04UTC 이전만 허용한다. 기준·제어·물성 가정을 바꾸지 않았고 실물 보정·CAN·모터 운전은 하지 않았다.

## 수리와 실제 확인

084 source/output을 보존하고085 별도 source16/출력/원격 경로를 만들었다. 구형 초기화 시험 자료 생성기를 새 bounded audit·전체 journal 계약에 맞췄다. 기존 반례15개와 원자료/해시/건수 변조5개를 함께 검사한다. 실제 검증기에서 필수 필드를 생략하지 않는다.

15항 전체 M/C/G와 측정된 기저+관절 평균 가속도를 사용하고 교차항을 유지한다. 실제 fixed/floating flag, Base, root/link0, COM, pre/post clock의 대조를 수집한다. 이 경로의 실제 SDK 관측은 아래 연결 장애 때문에 아직 검증하지 못했다. HOST의 알려진 결합행렬·비영 기저 가속도·COM·순서 반례는 통과했지만, 실제 기저 운동 좌표 교정은 미완료이며 PD 토크·포화는 UNKNOWN이다.

원 native 단계 journal을 전부 보존하고 종료 audit는 해시·건수·bounded 초기 이벤트만 저장한다. 부모 종료 저장에 실패해도 handle/lock 정리를 각각 시도하고 nonzero를 유지한다. 실패 부모 snapshot은 FAILED·비수용·원 job/exit·전체 파일 해시로 검증하며 native terminal과 구분한다. 정상 terminal 계약이나 native1 거절 정책을 완화하지 않는다.

HOST 최종 **283개 PASS**. 원 출력은 `outputs/isaac-floating-balance-run-v1/host-run-r3.txt`, source/HOST 결속은 `source-freeze-r3.json` 및 `freeze-verification.json`이다. L2R1 PASS9/0. L4R1 BLOCK7/2에서 부모 진단 파일과 원 terminal inventory의 계약 누락을 수리했고, L4R2 PASS9/0 및 독립 recovery17/storage15 재실행을 확인했다. 동일 계열 폴백의 공통 편향 잔여는 유지한다.

R1 재현의 범위도 정정했다. upstream process를 stub 처리한 inventory 반례였으며, 실제 기존 process_contract는 native1을 먼저 거절한다. 이번 수정으로 native1을 수용하거나 기존 native0 후 물리 실패를 성공으로 바꾸지 않았다.

## 실제 실행 경계

import 준비 `d5fce4665ac5448da544c4cd89522c0d`의 로컬 발사1회는 `Remote create` 단계에서 실패했다. 상태 파일에 `FAILED/sdk_connected:false`와 이유를 보존했고, `validation-transport-failure.json`에도 원본을 보존했다. SDK child 시작 증거·native 결과·원격 원장은 확보하지 못했다. render_smoke·motion은 시작하지 않았다.

읽기 전용 SSH 조회는 연결 시간 초과였다. 11:51:48UTC Tailscale 조회에서는 이 PC Running/Online, 대상100.91.91.53 Offline, 마지막 접속10:10UTC였다. 1회 ping도 응답하지 않았다. `network-status.json` 및 `connection-failure.json`을 참조한다. 노트북 전원/절전/Tailscale 확인을 사용자에게 요청했으며 재부팅·네트워크 설정 변경·자동 SDK 재시도를 하지 않았다.

따라서 새 실제15항·종료 저장·정지·큰 동작 검증 및 영상/Drive 저장은 **미완료**다. 083의 기존 실패나 영상을085 결과로 바꾸지 않는다. 노트북 연결 복구 후에는 남은 시간과 목적별 원장/실행 흔적부터 확인해야 하며, 새 실행의900초 여유와 native 목적별1회 조건을 그대로 적용한다.

## 통신과 모터 변경

`085-can-arrival-preparation.md`에 도착품 기록·실제 코드의ID1/2 제한·Classical CAN·설정 후보와 기존 시험 정본을 정리했다. S3 보드의 다중 노드 연결 가능성과 현재2축 펌웨어의 범위를 구분했다. 이번에는 펌웨어 시험을 재실행하거나 승인false를 변경하지 않았다.

보유한40mm NEMA17 두 대는 사용자 보고 기준 J2/J3 시험용이다. 최종 큰 모터는 BOM상 NEMA23 대안과 확정 상태가 구분돼 있으며 현재 동결 URDF·가정 물성에 확정 사양으로 반영되지 않았다. CAD/URDF/BOM·그리퍼 모델은 변경하지 않았다.
