> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 075 후보 — 계산 표현 수리, 기준 유지

074의 원 FAILED와 실행 횟수는 유지한다. 추가 SDK 실행은 아직 없다.

실측 초기화는 engine0·초기q/qd0·양의초기단계0·PRE/POST 실제행 결속을 만족했다. 2초 producer정착PASS, 속도위반0, 바닥 최소17.4566mm였다. 첫 root 실패는 손끝 투영계산의 quaternion norm 처리 불일치였다. producer는 norm≈1인 float32를 정규화하지 않았고 root는2/norm²를 사용했다. 첫오차1.0424e−8m/최대3.3204e−8m, 기존기준1e−8m는 유지한다.

`outputs/isaac-gravity-init-v1/projection-candidate/scene.py`는 회전계수를2/norm²로 계산하는 후보를 포함한다. 실제241상태/2651body회전에서root수학과동일, 중력참조차이최대2.66e−15, zero/NaN/nonunit거절HOST. 기존finite/unit범위조건은 유지한다. active제어소스에미적용·SDK미실행이다.

그 계산필드만 원bodypose에서 재계산한 DERIVED_DIAGNOSTIC은 다음 gain검사에서 멈췄다. angular Kp=64.00000762939453/Kd=16.000001907348633, linear64/16exact이다. 각각float32 1ULP차이로 SDK USD각도변환→tensor경로와 부합한다. 로컬NumPy2.5.1 재현은 설치SDK2.3.1 실행증거가아니다. 원1e−6기준·rawreadback을그대로보존하며64/16으로관측을바꿔통과시키지않는다.

후속후보는 view준비후 첫양의step이전에 동일목표64/16을tensor setter로설정하고 원기준으로readback검증하는 것이다. 이는 새gain튜닝이 아니라 USD각도왕복을피하는표현교정제안이며 비작성자검토/새실행수용이필요하다. 해당블록도candidate에만추가했다. HOST정규화시험은 그블록의native실행을증명하지않는다.

사용자시각수정: fog는로봇을가려다음렌더기본invisible로변경했다(active scene.py의MakeInvisible1호출,물리API/제어기준무변경·compile확인). 원074영상은수정전포그가보이는진단영상이며다시렌더하지않았다. ABB유형반구는향후선택형간단경계로검토하고,미검증반경을실제도달영역으로표시하지않는다.

실물보정·운전·설치·재부팅·학습은제외,질량관성가정/링보류유지. 074 import1/1·smoke1/1소비,motion0/1은원판정FAILED로미허가다.
