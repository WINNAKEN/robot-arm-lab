> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 080 결과 — PD 기준 시험 소스 수리·가져오기 완료, 실제 PD 계측 대기

2026-10-30. **SOURCE_ACCEPTED_AND_IMPORT_VERIFIED_REFERENCE_NOT_RUN**. 실제 PD 단독 토크·포화·정착 원인 확인과 새 영상은 아직 완료하지 못했다. 실물 운전은 하지 않았다.

## 확인·구현한 것

079 실제 기록은9DOF 모두 acceleration drive다. 따라서64/16을Nm 단위의force-PD 식으로 해석하지 않았다. 기존 순 관절 힘에서 외부 명령을 뺀 조건부 residual이 남은cap을 넘은 표본은 J2 4203/6240, J3 2083/6240이다. 이는 분해 전제의 모순을 조사할 근거이며 실제PD 포화의 증거가 아니다. 원079 자료/영상/실패15쌍은 보존했다.

robot과무연결인force/acceleration 관성기준물2개의새observer를구현했다. 외부only/PD-only/combined/acceleration-PD/free를같은physicsstep에관측하고IΔv/dt로독립대조한다. 실제PD단독은외부명령0인기준물구간만해석하며combined와robot PD는미식별이면UNKNOWN이다. robot 제어·게인·cap·경로·물리기준은079와같다.

설계 의미는 [PhysX Articulations의 drive 및 incoming-force 정의](https://nvidia-omniverse.github.io/PhysX/physx/5.8.0/docs/Articulations.html)와 [설치본 계열의 Tensor API](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/108.0/extensions/runtime/source/omni.physics.tensors/docs/api/python.html)를 대조했다. 공식 설명은 관절력에 여러 내부 기여가 포함됨을 보여주며, 실제 설치본 API·관성 시험의 통과를 대신하지 않는다.

L4R1에서 세 결함을 발견했다: PD-only0신호의거짓통과/combined반례검사누락, 속도양끝·issued명령·robotclock의연속결속누락, reference오류가collector로전파되고원시prefix가영속보존되지않음. 수리후비영신호·combined.03Nm예측, 전후속도/원clock/명령동일성, rawinertia/COM, 즉시flush journal/부분getter원시값·별도관측FAIL을검증했다. 영값대체는없다.

HOST215 PASS(기존191+reference24). 비작성자 review079 L2R1 9/0, L4R1 BLOCK6/3→L4R2 PASS9/0. 이는source·HOST수용이며reference native수용이아니다. 최종계획SHA 1e3ba4cffcb8d97443169d566cc4619932e8e17a367310e3211feb9e63d4b354, active15source는R2 freeze에결속했다. L2R1 최초SHA오기는실제파일재독·재조회로동일R1대상을정정한기록이며예산추가라운드가아니다. 동일계열폴백의잔여편향을유지한다.

## 실제 실행과 미실행

가져오기62eeb65baa0f46d48fa741c3bf312884: **IMPORT_VERIFIED**, 실제0/정책0/REAPED/noTimeout,173.844초. 11body/9DOF/11collider, 가정질량4.3342kg 및SDK/provider/numeric/CUDA 연결검증PASS. 원장import1/정지0/큰동작0, lock=false.

2초정지+reference 및52초큰동작은 **NOT_RUN**. 기준물생성/실제토크계측·포화식별·새native PNG/영상·Drive업로드도NOT_RUN이다. import통과를기준물API/물리수용으로승격하지않는다.

계획080 전체45분은한국11:48:15~12:33:15이며,새prepare/launch는900초여유조건상12:18:15전에가능하다. 실제import수용완료가그뒤였으므로다음단계를발사하지않았다. 남은전체시간을이유로고정시작조건을완화하거나원장을지우지않았다. 사용자에게[별도081실행안](081-pd-isolation-execution-proposal.md)의새45분승인을요청했다. 현재미승인·미실행이며시간경과는승인이아니다.

과거caller폐쇄·물리정착15미폐쇄·provenance7/physical6/eligibility2·velocity-only가설EXHAUSTED를보존한다. 새로운장치/도메인의소진을주장하지않는다. 질량관성가정·자기충돌OFF/바닥ON·링보류·포그invisible 유지. 보정/모터/CAN/설치/재부팅/구매/학습NOT_RUN.

정본은outputs/isaac-pd-isolation-v1/의result.json·source-freeze-r1/r2·L2/L4기록·HOST·preserved079-semantics-audit.json·실제run의retrieved·remote-ledger-closeout.json·manifest다. 전체실제마감은budget.json에저장한다.
