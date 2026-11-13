# 049 격리 커널 · 엔진 동역학 제어 후보

> 최종 처분: **BLOCK / EXHAUSTED, 아래 실행 명령은 재실행하지 않는다.** L4 R1에서 실제 local CLI의 미등록 `numpy.py` 선실행과 worker 실패 코드의 process exit 전파 누락을 수용했다. provenance accepted5 / EXHAUSTED, physical-frame accepted3 / EXHAUSTED를 유지한다. 실제 module/GPU는 통과했으나 native1은 `isaacsim` import 전제 실패로 시작 단계에서 중단됐고, CAD/물리/정착 관측은 없다. native1/2 소비 후 나머지 실행과 R2 수리 출하는 동결했다. 상세 원자료와 후속 경계는 `outputs/isaac-control-kernel-v1/HANDOFF.md`를 따른다.

기존047/048은 BLOCK/EXHAUSTED 이력으로 보존한다. 이 코드는 프로젝트 공유 import namespace를 없애고, 검증한 바이트를 명시 파일경로로 compile한 뒤 API capability로 연결한다. 프로젝트폴더를sys.path에추가하거나from setup/control/frames 같은프로젝트모듈검색을하지않는다. 설치prefix는읽기전용전체seal로확인한다.

결과는source SHA로고정된043 pre-play 모델자료/CAD/recipe와전체frame내용을비교한다. 7LINK·양쪽관절·COM/관성·7collider owner/localbasis/enabled·floor/probe 원자료를저장하고모든6781프레임을검사한다. snapshot self-hash나개수로연결성공을판정하지않는다. 원래0.5°/1°/s/28지점·120Hz/56.5초·동일토크cap을유지한다.

새후보는nativePD를0으로확인하고엔진M/g/c를관측해단일computed-torque명령을준다. 명령은±[3,6,5,2,2,1]Nm로제한하며관측토크는실제모터측정치가아닌시뮬레이션명령/readback이다. 실제반환행렬/보상벡터와이전상태를기록해식전체를재계산한다. Lab의playing-explicit-step계약을쓰고실제Lab/engine/callback/read-step시계로독점성을검사한다.

```powershell
py -B -m unittest src.simulation.isolated_control.test_kernel -v
py -B src/simulation/isolated_control/kernel.py prepare
py -B src/simulation/isolated_control/kernel.py module --run-dir <새run>
py -B src/simulation/isolated_control/kernel.py native --run-dir <같은run>
```

최종상태는output delivery/검토서를따른다. 코드작성/호스트검사가native·동작통과를의미하지않는다. 새authornative는global049원장max2/각600초이며실패도소비한다. 큰학습·실물보정/모터/CAN/플래시·구매·링검증은없고물성가정/weightsnull/physicalfalse를유지한다. 기존두EXHAUSTED및미폐쇄지적을초기화하지않는다.
