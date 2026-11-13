> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 079 결과 — 실제 관절 힘·제동 응답 관측

2026-10-30. 사용자 승인 새 45분 단위. **수용 상태: STATIONARY_PASS_LARGE_MOTION_DYNAMICS_FAILED**. 원 078 실패와 원장은 변경하지 않았다.

## 실제 실행

| 목적 | Run ID | Root 판정 | 실제/정책 종료 | 회수 |
|---|---|---|---|---|
| render_smoke | 238e0a3cbe224dfca7f616cab812683a | SMOKE_VERIFIED | 0/0 | REAPED |
| motion | 9b9da2e4e7ed4db58bd2b77b7c862d2e | LATEST_SCENE_DYNAMICS_FAILED | 0/0 | REAPED |
| import | c91314503fc441d3b3caf4a2fc8ef121 | IMPORT_VERIFIED | 0/0 | REAPED |

HOST191 PASS, L2R1/L4R1 source 수용. 078 R2와 semantic 8파일 바이트 동일; caller는 현재 proof[native]를 전달한다. 원 제어·경로·게인64/16·cap·정착0.5도/1도/s·1초 hold를 유지했다. 실제 정지 PASS 뒤에만 큰 동작을 시작했다.

## 계측의 의미와 한계

외부 actuation 명령, 관절 운동축 projected net effort, child-joint-frame incoming 6D를 따로 기록했다. 실제 USD child/axis 및 native 이름으로 9DOF/11링크를 매핑하며, 시간·binary32 명령 readback·내부 projection 일관성을 각 양의 스텝에서 독립 root가 검사한다. step0/prime은 solver 측정으로 세지 않는다.

설치 Tensor API SHA 0da2ff6f94a8e5afffce6460f7b97b2f09d0423a3813149498cb88e96f60a3b6 및 Articulation 소스를 고정했다. [NVIDIA Tensor API 설명](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/109.0/extensions/runtime/source/omni.physics.tensors/docs/api/python.html)은 정의 참고이며 설치본 pin이 실제 실행 원천이다.

projected는 **내부 순 관절 힘/토크**이며 isolated PD drive torque가 아니다. 외부 명령과 다르다는 사실만으로 PD 기여·모터 토크를 분리할 수 없다. incoming과의 투영 일치는 같은 backend 내부 일관성이며 독립 힘 교정이 아니다. net/cap 비율은 포화 증거가 아니다.

| 축 | 순 운동축 토크 최솟값(Nm) | 최댓값(Nm) | 외부 명령 최대 절댓값(Nm) |
|---|---:|---:|---:|
| J1 | -0.182872 | 0.300416 | 0.000080 |
| J2 | -1.455073 | 1.861406 | 5.460003 |
| J3 | -2.306875 | -0.391043 | 3.633546 |
| J4 | -0.157931 | 0.254621 | 0.308017 |
| J5 | -0.881434 | -0.297853 | 0.887897 |
| J6 | -0.016218 | 0.016094 | 0.015012 |

실제 양의 힘 관측: 6240개. isolated PD=NOT_AVAILABLE; saturation=NOT_DETERMINABLE_FROM_NET_PROJECTION; unique cause=INCONCLUSIVE_REQUIRES_DECOMPOSITION_OR_CONTROLLED_COUNTERFACTUAL.

## 제동과 정착

감속 후반부터 원래 1초 hold 끝까지 관측한다. 마지막 표본까지 위치·속도 기준을 연속 만족하는 suffix만 정착 시간으로 보고한다. 끝에서 위반하면 CENSORED_NOT_SETTLED로 남기며 정착 시간을 늘리지 않는다. net work는 순 관절 일이고 모터 단독 일이 아니다.

| 정착 구간 | 끝까지 미정착 축 | 최악 끝 오차(도) | 최악 끝 속도(도/s) |
|---|---|---:|---:|
| raise_settle | J2, J3, J5 | 1.326638 | 5.128379 |
| sweep_left_settle | J1 | 2.240833 | 3.561657 |
| sweep_right_settle | J1 | 1.266172 | 2.066659 |
| reach_high_right_settle | J2, J3, J5 | 2.325703 | 5.086876 |
| sweep_high_left_settle | J1, J2 | 0.820435 | 1.281188 |
| return_safe_settle | J1, J2, J3, J4, J5 | 2.515214 | 4.568149 |

경로 완료=True; 6240스텝/6241상태/521영상 프레임. 최대 정착 오차 2.515214도, 잔류속도 5.128379도/s.

Root 물리 checks: `{"settling": false, "gripper_sync": true, "canonical_fk": true, "native_render": true, "complete_program": true, "joint_limits_and_velocity": true, "floor_clearance": true, "gravity_margin": true, "large_motion": true}`. process exit0은 물리 PASS가 아니다. 같은 제어의 077 비교는 tracking-comparison.json에 있으며 이 관측 추가를 제어 개선으로 주장하지 않는다.

## 폐쇄·보류와 영상

078 caller 오류의 source 수용과 079 native 계측 확인은 별도 계보다. 기존 velocity-only 정착 해결 가설 EXHAUSTED, provenance7/physical6/eligibility2 및 기존 phase-joint15 증거를 초기화하지 않는다. 정착 실패의 유일 원인은 아직 확정하지 못했으며, PD 단독 기여를 분리할 수 있는 경로 또는 통제된 반례 시험이 추가로 필요하다.

실물 보정·모터/CAN 운전·설치·재부팅·구매·학습 NOT_RUN. 질량/관성 가정, 자기충돌 OFF(겹치는 proxy 한계), 바닥충돌 ON, 링 보류, 포그 invisible 유지. 실물 안전/토크 인증이 아니다.

영상은 sealed 실제 native PNG만 인코딩하며 원속도와 3배속을 구분한다. 실제 영상·Drive 메타데이터 및 비작성자 L4R2 결과는 result.json의 결속 기록을 따른다. 내부 provenance JSON은 로컬에만 보존한다.

정본: outputs/isaac-torque-run-v1/result.json, torque-braking-diagnostics.json, tracking-comparison.json, 각 run의 원 retrieved, remote-ledger-closeout.json, source-freeze-r1.json 및 artifact-manifest.json. 전체 45분 준수 여부는 budget.json의 실제 closeout 시각으로 판정한다.

아카이브 helper 재사용 제한: closeout.py의 purpose 선택은 단일 시도 자료용이다. 이번 smoke 예비 슬롯은 미사용이므로 판정 영향이 없다. 복수 정지 시도 단위에 그대로 재사용하지 말고 accepted receipt에 선택을 결속해야 한다. SDK 실행/검증 root의 예산·원장·수용 규칙과 별개인 보고 helper 한계다.

비작성자 review079 L4R2: 9 MET/0 UNMET PASS. 실제 계측 caller 폐쇄 및 실패/영상 증거의 정합성 판정이며 물리 정착 PASS가 아니다. 최종 행정 저장과 manifest는 검토 후 다시 생성한다.

원속도 영상 (비공개 링크 제외) · 3배속 영상 (비공개 링크 제외). 크기/MIME/부모를 재조회했으며 remote SHA와 공개 공유 접근은 검증하지 않았다.
