# 043 — 중력·충돌 상태의 동일 6축 경로

기존042 코드를 변경하지 않는 별도 파이프라인이다. 같은56.5초/28checkpoint/120Hz 경로와 PD gain·총토크 상한을 유지한다. 중력−9.81m/s²,7개 AABB proxy·비인접 self-collision·바닥 충돌을 켠다. 직접 연결된6쌍만 명시적으로 제외한다.

가정 질량/COM과 이전 step의 actual LINK pose로 중력 보상 effort를 계산한다. 외부 effort와 PD drive residual cap의 합은 기존 총cap을 넘지 않는다. 이 값은 actuator 실측 토크가 아니다. 별도.1kg/.05m 낙하 Cube가 바닥에 안착하고 양의 접촉력이 발생하는지를 검사한다. 실제8×9 contact matrix와 상세 접촉 점/normal/force를 같은 step에서 읽어 집계·인덱스·capacity512를 검증한다.

`powershell -NoProfile -File src/simulation/contact_motion/driver.ps1`은 새043 run을 전송·실행·회수한다. author2회/각600초 유한 예산, 기존 Kit 세션이 있으면 시작하지 않는다. 실패를 통과할 때까지 반복하지 않는다. 이미 수집한 자료만 다시 검사하는 명령:

```powershell
py -B src/simulation/contact_motion/verify.py --run-dir outputs/isaac-contact-v1/runs/<GUID>/retrieved/<GUID>
py -B src/simulation/contact_motion/render.py --run-dir outputs/isaac-contact-v1/runs/<GUID>/retrieved/<GUID>
py -B -m unittest src.simulation.contact_motion.test_contact -v
```

결과는 GRAVITY_COLLISION_MOTION_PASS / DYNAMICS_FAILED / INVALID_EVIDENCE로 구분한다. 영상은 actual LINK 기록을3D로 재생하며 Isaac viewport 직접 녹화와 구분한다. 가정 질량·관성·재료·토크·한계는 실측값으로 승격하지 않는다. 실물 보정·모터·CAN·플래시·강화학습·링 검증은 수행하지 않는다. Proxy 충돌 통과는 실제 속 빈 CAD 표면·링·기계 간섭 인증이 아니다.
