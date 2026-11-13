> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 061 — 중력 보상·자세 유지·접촉의 분리 진단

사용자 2026-10-29 「자 다음 검증 진행해」에 따라060 다음 중력/접촉 단계로 진행한다. 047의 게인/solver 재시도와 28checkpoint 수용을 재개하지 않는다. 새 가설은 native 중력 보상과 실제 LINK/COM 기반 계산 토크의 일치 여부 및 짧은 중력 평형 유지다. 기존 root/source/provenance 접근은 이미060에서 새 경계로 수용됐으며 old047 worker는 실행하지 않는다.

코딩 M급, 새 src/simulation/gravity_session9파일+계획1, outputs/isaac-gravity-v1 소유. 04:29~05:14UTC 총45분, L2/L4 각max2 비작성자 정적 검토. 외부hook이전차단 재시도/우회없음 same-familyfallback 한계 명시. .dev/CAD/BOM/047~060source/output은읽기전용. 이전provenance7EXHAUSTED/physical6EXHAUSTED/eligibility2+다음동종독립실측작성자수용1충분임계·first-fault이력유지, 새이름으로reset하지않는다. 예산내class착지/소진미소진판정요구.

060 source9를새namespace로복사한다. providers/physics와baseline clock·4facet/root수용·모듈동일성·metadata/GPU·종료코드·해시/PID·실행순서는보존한다. 원0603예약/nested원장SHA를새061원장에그대로결속한다. 새 audit900/diagnosis300/connection600 각max1, freshness300,실패도소진/추가수리재실행없음. baseline10step/11row 완료·수용뒤에 같은process/state에서중력분리진단을추가한다. 기존 baseline scene.usda/관측은gravity0자료로유지하며새중력실행은script+별도gravity-report로기록한다. baseline PASS를중력PASS로확대하지않는다.

새robot.py는gravity-report.json(terminal7번째필수hashartifact)producer와순수root소비부를소유한다. 실제동일Labview.set_gravity(carb.Float3(0,0,-9.81))로backend중력만변경하고get_gravity readback·7링크및probe실제gravityenabled·kp/kd0·동일effortcap을기록한다. USD기본중력0과실제backendoverride를구분한다. 새scene/뷰/reset/play/teleport/q/qd쓰기/solver/gain조정없음. live물성/형상/필터/재료는baseline자산 그대로다.

240step/2초(120Hz),241상태를모두관측한다. 각step직전현재native get_dof_gravity_compensation_forces를DOF이름순서로읽어cap[3,6,5,2,2,1]내clamp하고set_dof_efforts로보낸다. kp/kd0이므로PD토크없음. 명령readback/이전actualLINK/COM·jointframe에서별도로계산한중력토크와native값을모두보존한다. actual링크를expectedFK로대체하지않는다. 포화·토크불일치(최대1e-3Nm)는진단실패이며cap/gain증가나계산시간fallback을하지않는다. 이nativefeedforward는제품제어채택이아닌원인분리용이다.

관측row는q/qd/7LINK/probe·이전step명령native/math/readback·접촉원행렬/활성접촉·gravity/drive상태·native시계3snapshot을담는다. baseline최종row와새row0의q/qd/LINK/probe/절대Labstep/native시간을결속한다. 기존실제nativeowner와같은getter를검증하고새PhysXpostsubscription count0부터시작해240step/float32callback/실제engine증가2초·읽기불변·연속성을검증한다. finally구독해제와CC060최초오류우선순위를유지한다. 실패도부분row/최초오류/cleanup오류를보존한다.

root는동일cachedrobot의순수함수로별도report의run/job/PID/owner/241row/closed필드·DOF순서·fullcontactmapping/힘재구성/전체frame(FK·7LINK·fixed+6joint양끝·부호축)·massCOM원천·실제gravity/drive readback·clock/명령전후관계를검증한다. root기준토크를producer선언에서받지않고actualposes+검증된질량COM에서재계산한다. contact검사는기존canonical의모든행렬/인덱스/카운트/활성접촉재구성기준을새phaseindex에적용하며10으로위장하지않는다.

동역학판정은별도로산출한다: 2초전체q오차≤0.5°/qd≤1°/s, native↔math최대1e-3Nm, 명령미포화, 원치않는robot비인접/arm-floor힘≤1e-3N, probe낙하≥0.05m·1초이후z=.025±.002m·바닥양성힘>0.1N. Base-floor는장착면으로별도집계한다. tensor readback명령은측정모터토크가아니다. 구조자료유효라도동역학실패면GRAVITY_DIAGNOSTIC_FAILED/localnonzero(실제workerexit0과구분); API/자료불완전은FAILED/INVALID_EVIDENCE다. 성공해도047/28checkpoint·56.5s전체동작·강화학습/실물수용으로승격하지않는다.

호스트: 기존06018시험보존+실제collector mock/첫gravityAPI실패·동시cleanup예외/토크부호·회전COM/DOF순서/명령readback/240시계·probe양성/행렬재구성/필드누락·재해시root변조·有限자료의동역학FAIL과완료구분. AST/whitespace/L4후실제실행한다. actual원자료와host모형/정적독립검토를구분하고프로세스·lock종료확인·인계·scopecommit으로종결한다. 임의튜닝/재실행으로성공까지반복하지않는다.

실물보정/모터/CAN/flash/구매/새설치/재부팅/학습없음. 질량·관성가정·링보류유지. 공식API참고: https://docs.isaacsim.omniverse.nvidia.com/6.2.0/py/source/extensions/isaacsim.core.experimental.prims/docs/index.html / https://docs.omniverse.nvidia.com/kit/docs/omni_physics/107.3/extensions/runtime/source/omni.physics.tensors/docs/api/python.html . 설치버전실측이우선이다.
