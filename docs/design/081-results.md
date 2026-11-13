> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 081 결과 — 독립 PD 관성 기준 시험과 로봇 정착 검증

2026-10-30. 실제 robot 수용 상태: **STATIONARY_PASS_LARGE_MOTION_DYNAMICS_FAILED**. reference 관측 상태: **REFERENCE_SEMANTICS_VERIFIED**. 로봇 단독PD와 포화의 식별 상태는 계속 **NOT_DIRECTLY_MEASURED / UNKNOWN**이다.

## 실행과 검토

| 목적 | Run ID | Root 판정 | 실제/정책 종료 | native초 |
|---|---|---|---|---:|
| render_smoke | 820508f73221475c82cfc510f3fd3df3 | SMOKE_VERIFIED | 0/0 | 132.76599999982864 |
| import | 9e154122d1074c6396b3ff1778c5cf58 | IMPORT_VERIFIED | 0/0 | 173.89100000006147 |
| motion | cbbdd7e6874c4deabe4e7a37b9250121 | LATEST_SCENE_DYNAMICS_FAILED | 0/0 | 546.280999999959 |

사용자 새45분 승인, 한국12:34:44~13:19:44(UTC03:34:44~04:19:44). L2R1/L4R1 비작성자review079 9 MET/0 UNMET, source15 및080 R2 semantic9 바이트 동일, 새HOST215 PASS. 이는 실제 관측·물리 통과와 별도다. 같은 계열 폴백의 공통 편향은 잔여 위험이다. 최종 증거 검토는 L4-R2.json의 범위만 따른다.

## 기준물에서 확인한 PD와 한계

별도 force/acceleration1DOF 기준물은 robot과 무연결이고 충돌 형상이 없다. 각각 rotor 질량1kg, 실제 관성 약0.2kgm², COM=축, 넓은 한계·마찰/armature0이다. robot 원래 physicsstep를 공유해240스텝/두 기준물480관측행을 취득하며 별도 시간 전진이나q/qd복원은 하지 않는다. 각 velocity endpoint·실제 issued 명령·robot 원시clock·raw inertia/COM를 root에서 독립 결속했다.

외부명령0인 PD-only 구간에서는 실제 I·Δv/Δt가 독립 단독PD 토크다. force 방식은64/16의 힘 식, acceleration 방식은 동일 숫자의 가속도 식에 기준물 관성을 적용해 단위를 구분했다. 후단 상태 기반 수요가 한계를 넘고, 관성 토크가 같은 부호로 cap에 근접하는 표본만 아래 한계 관측에 센다. 이는 독립 기준물의 결과이며 robot 포화 증거가 아니다.

| 기준물 | PD-only 표본 | 관성 토크 최소(Nm) | 최대(Nm) | cap(Nm) | 수요 초과·cap 근접 표본 |
|---|---:|---:|---:|---:|---:|
| force | 48 | 0.0099999906 | 0.0099999906 | 0.01 | 48 |
| acceleration | 48 | 0.0099999906 | 0.0099999906 | 0.01 | 48 |

분석 입력 run: cbbdd7e6874c4deabe4e7a37b9250121; 원 report SHA 3e5a71a9fd0a49f1cd310c5f16e97eae36e82d6ec3547cf28e78181b0381e923.

외부only는 실제 총기여와 명령을, combined는 사전 가산 예측을 대조한다. combined=balance−readback은 여전히 조건부 residual이고 robot의 단독PD·포화를 직접 분리한 측정으로 승격하지 않는다. reference의 관측 상태와 오류는 reference-diagnostics.json에 따로 보존한다.

## 로봇의 제동과 정착

원게인64/16·acceleration drive·cap·52초 경로·120Hz·정착0.5도/1도_s·1초hold를 유지했다. 원래 force command/incoming6D/projected를 구분하며 net/cap 초과를 포화로 해석하지 않았다. pose/속도·중력·바닥·FK·그리퍼·완주·원시영상 판정은 원 root와 같다. process 종료0은 물리 PASS가 아니다.

완주=True, 6240step/6241상태/521frame. 최대 정착 오차 **2.515214도**, 잔류속도 **5.128379도/s**.

| 원래 정착 구간 | 끝까지 미정착 축 | 최악 끝 오차(도) | 최악 끝 속도(도/s) |
|---|---|---:|---:|
| raise_settle | J2, J3, J5 | 1.326638 | 5.128379 |
| sweep_left_settle | J1 | 2.240833 | 3.561657 |
| sweep_right_settle | J1 | 1.266172 | 2.066659 |
| reach_high_right_settle | J2, J3, J5 | 2.325703 | 5.086876 |
| sweep_high_left_settle | J1, J2 | 0.820435 | 1.281188 |
| return_safe_settle | J1, J2, J3, J4, J5 | 2.515214 | 4.568149 |

Root checks: `{"settling": false, "gripper_sync": true, "canonical_fk": true, "native_render": true, "complete_program": true, "joint_limits_and_velocity": true, "floor_clearance": true, "gravity_margin": true, "large_motion": true}`.

## 원인 판별의 범위

기준물에서 PD-only 응답·cap·외부only/combined의 API 의미가 맞는지 확인하는 새 증거다. 로봇에서는 중력 보상·다관절 결합·반력·한계/마찰 기여가 섞이므로 순 관절력−명령만으로 단독PD를 확정하지 않는다. 현재 자료로 정착 실패가 토크 포화 때문이라고 확정하거나 포화를 배제하지 않았다.

wrench-origin-audit.json은 실제2초 정지 자료에 대해 body/COM principal/world 좌표 및 COM 기준점 이동의6개 고정 후보를 대조한 진단이다. 여러 관절에 한 표현을 적용했을 때 중력 기준과 일치하지 않으므로 이 단순 보정을 채택하지 않았다. 후보 비교는 수용 판정 수리나 실제 robot PD 측정을 대신하지 않는다. COM0 기준물은 비영COM 로봇의 wrench 기준점을 식별하지 못한다. 후속 후보는 로봇에 적용 가능한 완전 힘·모멘트/관성 평형과 구속 기여를 별도 검증하는 것이며 이번에는 미실행이다.

기존079/080 원장·실패·수리, caller native 폐쇄, settling15 미폐쇄, provenance7/physical6/eligibility2와velocity-only 가설EXHAUSTED를 초기화하지 않았다. 새로운 장치/도메인의 소진을 주장하지 않는다.

## 영상·물성·실물 경계

영상은 sealed 실제 nativePNG만 원속도/요약으로 인코딩해 full decode 및 첫/중/끝을 확인한다. 포그 숨김, 실제TCP marker/trail만 유지한다. reference 기준물은 카메라 밖이므로 영상은 robot 동작이며 기준물 자체의 시각 영상이 아니다. Drive는영상만저장·크기/MIME/부모재조회하며 원시JSON은로컬이다. 전달 결과는drive-delivery.json과video/provenance.json을 따른다.

질량/관성 가정, 자기충돌OFF(겹치는proxy한계)/바닥충돌ON, 링보류. 실물보정/모터/CAN/플래시/설치/재부팅/구매/학습 NOT_RUN. 실물 토크·안전·강화학습 준비 완료로 해석하지 않는다.

정본: outputs/isaac-pd-isolation-run-v1/result.json·reference-analysis.json·reference-diagnostics.json·torque-braking-diagnostics.json·tracking-comparison.json·원retrieved·원장·source freeze·L4·manifest. 전체45분준수여부는최종budget.json의실제closeout시각으로판정한다.

robot 파라미터 관측 521개가 initial과모두같음=True, jointfriction0=True, armature0=True. 이는샘플된설정값이며구속충격량/robot단독PD 측정이아니다.

077과 step/time/q/qd/target/선택velocity 6241행의정확대조=True. 전체SDK상태·PD힘동일확증으로확대하지않는다.

비작성자 review079 L4R2 PASS9/0: 고정1DOF PD-only native관측과증거정합성수용이며robot PD/포화·물리정착수용이아니다. 최종인계/manifest/Git저장은검토후기계대조한다.

원속도 영상 (비공개 링크 제외) · 3배속 영상 (비공개 링크 제외). 크기/MIME/부모재조회,remoteSHA/공개공유접근은미검증이다.

[082 후속 제안](082-robot-force-balance-proposal.md)은제안만저장했으며구현/실제시험/새예산은미승인·미실행이다.
