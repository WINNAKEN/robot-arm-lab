> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 078 결과 — 계측 연결 오류 수리, 실제 계측 재검증 대기

2026-10-30. **구동 토크·제동 응답의 실제 계측은 아직 완료하지 못했다. 정착 실패 원인도 미판정이다.** 실물 보정·모터/CAN 운전·설치·재부팅·구매·학습은 하지 않았다. 원 물리 기준·게인·cap·경로·물성 가정·포그 숨김·링 보류는 유지했다.

## 확인한 API와 구현

설치된 Tensor API 소스를 읽어 사본과 SHA `0da2ff6f94a8e5afffce6460f7b97b2f09d0423a3813149498cb88e96f60a3b6`를 저장했다. 외부 actuation 명령, 운동축 projected joint effort, child-joint-frame incoming6D를 구분해 수집·매핑하는 소스를 구현했다. 두 힘 표현의 일관성은 내부 매핑 검사이며 독립 힘 교정이나 isolated PD 토크 측정이 아니다. PD 단독 토크·포화·유일 원인은 검증되지 않으면 UNKNOWN으로 남긴다.

HOST187 및 L2/L4R1을 통과했지만, 실제 scene 호출자의 변수 연결은 당시 fake getter 시험과 검토에서 빠졌다.

## 실제 실행과 실패

| 목적 | ID | 결과 |
|---|---|---|
| 가져오기 | 0933ca2606dd46718b4bd41a0f533a22 | IMPORT_VERIFIED, actual0/policy0/REAPED |
| 정지 계측 | 92ba24528a8642739a3e50edb9c3ffbb | COLLECTOR NameError, actual1/policy1/REAPED/noTimeout, 96.672초 |
| 큰 동작·제동 | 없음 | NOT_RUN — 정지 계측 게이트 실패 |

오류는 `scene.py`의 per-step `torque.observe(..., step, ff)` 호출에서 발생했다. `ff`는 내부 command 함수의 지역변수이고, 바깥 loop는 `target, proof, remaining`을 받는다. 첫 양의 스텝 뒤 호출 인수를 평가하다 실패했으므로, SDK force getter가 실패했다거나 정착 물리 기준을 위반했다고 해석하지 않는다. SDK 앱은 실제 시작됐으며 원 root의 sdk_connected:false는 이 실행의 수용 실패 플래그다.

완료 상태 기록은 step0·native PNG1개뿐이다. prime은 solver 관측이 아니고 실제 양의 힘 관측은0개다. 제동 영상은 없으며 초기 프레임을 반복해 동작 영상으로 만들지 않았다. 원 failure.txt·terminal·exit·native step trace·journal·PNG·sidecar·동결 R1 input은 그대로 보존한다.

## 수정과 검토

활성 수정본은 호출 인수를 현재 명령 증명인 `proof['native']`로 연결했다. 제어식·힘 getter·게인·cap·판정 기준은 바꾸지 않았다.

- 원 동결 소스의 NameError를 호스트에서 재현했다.
- 실제 전체 호출 AST를 실제 caller 변수 환경에서 평가해 올바른9DOF 명령이 전달됨을 확인했다.
- 바깥 함수의 미정의 ff 참조가 사라졌고 재시도·영값 대체가 없음을 검사했다.
- 연결 회귀4 PASS, 관련 torque35 재검사 PASS. 최초 연결 시험 자체의 AST 인수 개수 오기를7개로 고친 뒤 통과했다.
- 비작성자 L4R2 9 MET/0 UNMET. R1 fake-getter 시험과 검토가 실제 caller scope를 놓친 한계를 인정했다.

이 결과는 **소스·HOST 수리 수용**이며 수정본 native 재검증은 NOT_RUN이다. 새 관측부 caller 결함1건의 source 수리와 native 폐쇄 대기를 구분한다. 기존 velocity 단독 수리 가설 소진·정착15개·과거7/6 이력을 지우지 않는다.

## 실행 경계와 다음 단계

원 계획078은 native 각 목적1회·전체45분·시작900초 여유를 정했다. 실패도 정지1/1로 소비됐다. 원장을 초기화하거나 source/config를 바꿔 같은 실행을 추가 발사하지 않았다. 사용자에게 수정본과 재검토 결과를 제시하고 **새45분 실행 단위**에서 가져오기→정지 힘 계측→동일52초 제동 계측·영상까지 이어갈지 선택을 요청했다.

실제 힘·제동 측정의 성공, 토크 포화, 감쇠·관절 결합 원인, 정착 개선은 아직 주장할 수 없다. 수정된14source는 source-freeze-r2.json, 원 native 실패는 R1 freeze와 각 run input으로 구분한다. 최종 정본은 outputs/isaac-torque-observer-v1/result.json·L4-R2.json·connection-host.json·원 retrieved 및 artifact-manifest다.

사용자가 「새45분으로계속」을 명시 승인했다. 새 실행은 계획079/별도 torque_observer_run·isaac-torque-run-v1에서 진행한다. 078 원장·원 실패는 변경하지 않으며 078 수정본 자체의 native 재검증 상태는 NOT_RUN으로 보존한다.
