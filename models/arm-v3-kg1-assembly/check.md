# 외장 v3 + 그리퍼 KG1 조립 검사 요약 (assemble.py 가 씀 · 원본 = check.json)

- 붙인 면 = `flange` (J6 원점에서 축 방향 28.00 mm) · 돌림 0.0° · 플랜지 면 ↔ 받침 아랫면 틈 0.0 mm
- 검사 장치 all_ok = **True** · A_all_manifold_equal_mesh_positive True · A_interface_measured_equals_params True · A_tool_holes_match_gripper_and_ledger True · A_link6_x_is_j6_axis True · A_mount_rotation_proper True · A_independent_fk_mount_and_roll True · A_mount_face_contact_only True · controls_all_as_expected True · A_display_pose_gripper_free_of_arm True
- 양성 대조: C1_mounted_1mm_inside_overlaps True · C2_pushed_60_into_arm_hits True · C3_open_or_inverted_mesh_fails_manifold_key True · C4_below_floor_fails_floor_key True · C5_home_moved_to_elbow_hits_links_0_4 True · C6_j5_folded_180_arm_self_hits True · C7_free_interval_synthetic True · C8_independent_fk_catches_roll_and_face True · C9_roll_45_screws_miss_holes True · C10_shift_0_5_boss_hits_recess_wall True · C11_hole_measure_catches_angle_count_depth True
- 팔 나사 몸통 ↔ 링크 6(2 단계부터 플랜지 인서트 구멍에 들어가야 0): 0 쌍 · 최대 0 mm³
- 맞춤 쌍(설계상 틈 0) BASE ↔ LINK6_TOOL_RING: 원래 겹침 0.9168 mm³(두 STL 의 원 다각형 차) · 돌기를 반지름 0.05 mm 들여 잰 겹침 0.0003 mm³(판정에 씀)

## 갤러리 자세 (벌림 u = 0, 20, 47 · 손끝 사이 = 2u)

| 자세 | u | 팔과 겹침 | 최대 mm³ | 링크 0 ~ 4 와 가장 가까운 틈(근사) | 링크 5 와 틈(근사) | 그리퍼 최저 z(바닥 0) | 팔끼리 겹침 |
|---|---|---|---|---|---|---|---|
| display | 0 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_1 ↔ J6_MODULE) | 21.973 | 없음 |
| display | 20 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_1 ↔ J6_MODULE) | 19.538 | 없음 |
| display | 47 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_1 ↔ J6_MODULE) | 16.25 | 없음 |
| home | 0 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_2 ↔ J6_MODULE) | 280.0 | 없음 |
| home | 20 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_2 ↔ J6_MODULE) | 280.0 | 없음 |
| home | 47 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_2 ↔ J6_MODULE) | 280.0 | 없음 |
| reach-up | 0 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_2 ↔ J6_MODULE) | 660.466 | 없음 |
| reach-up | 20 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_2 ↔ J6_MODULE) | 660.466 | 없음 |
| reach-up | 47 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_2 ↔ J6_MODULE) | 660.466 | 없음 |
| pick | 0 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_1 ↔ J6_MODULE) | -65.733 ⚠ 바닥 여유 미달 | 없음 |
| pick | 20 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_1 ↔ J6_MODULE) | -65.733 ⚠ 바닥 여유 미달 | 없음 |
| pick | 47 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_1 ↔ J6_MODULE) | -65.733 ⚠ 바닥 여유 미달 | 없음 |
| side-reach | 0 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_3 ↔ J6_MODULE) | 20.807 | 없음 |
| side-reach | 20 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_3 ↔ J6_MODULE) | 22.428 | 없음 |
| side-reach | 47 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_3 ↔ J6_MODULE) | 23.008 | 없음 |
| wave | 0 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_2 ↔ J6_MODULE) | 492.653 | 없음 |
| wave | 20 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_2 ↔ J6_MODULE) | 492.653 | 없음 |
| wave | 47 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_2 ↔ J6_MODULE) | 492.653 | 없음 |
| zero | 0 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_2 ↔ J6_MODULE) | 115.0 | 없음 |
| zero | 20 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_2 ↔ J6_MODULE) | 115.0 | 없음 |
| zero | 47 | 없음 | 0.0 | 10 넘음 | 3.0 (ARM_SHANK_2 ↔ J6_MODULE) | 115.0 | 없음 |

## J5 쓸기 — 닿지 않는 구간(도 · -170 ~ 170 · 5° 간격 · 기준 자세의 J5 를 포함하는 구간 · 경계는 ±5° 정밀도)

| 기준 자세 | 팔만 | 그리퍼 닫힘 | 그리퍼 끝 벌림 | 닫힘 + 바닥 | 끝 벌림 + 바닥 | 그리퍼가 처음 팔에 닿는 각(닫힘 · 끝 벌림 · + / −) |
|---|---|---|---|---|---|---|
| display (J5 = 25) | [-110, 110] | [-110, 110] | [-110, 110] | [-110, 30] | [-110, 25] | 150 / -160 · 145 / -160 |
| home (J5 = 0) | [-110, 110] | [-110, 110] | [-110, 110] | [-110, 110] | [-110, 110] | 130 / -160 · 130 / -160 |

## J6 쓸기 (display 자세 · 15° 간격 한 바퀴)

- u0: 팔에 닿는 q6 = 없음 · 바닥 여유 미달 q6 = 없음 · 그리퍼 최저 z = 15.664 mm (q6 = 90)
- u47: 팔에 닿는 q6 = 없음 · 바닥 여유 미달 q6 = [-165, -150, -135, -120, -105, -90, -75, -60, 15, 30, 45, 60, 75, 90, 105, 120] · 그리퍼 최저 z = -9.087 mm (q6 = -135)

가장 가까운 틈은 표면 표본점(약 1.5 mm 간격) 사이 거리라 실제 틈보다 조금 클 수 있다 · 상자가 10 mm 안인 바디만 재므로 그보다 먼 것은 「넘음」. 겹침은 manifold 불리언으로 잰 부피다. 자세 사이 경로는 보지 않는다.
