# 052 SDK 단일 수치 제공자와 계약 기반 연결

> 최종 처분: **BLOCK / EXHAUSTED, 아래 명령은 실행하지 않는다.** 독립 A/B 검토에서 code snapshot 재읽기, 제공자 경로 canonicalization, 접촉 aggregate 재구성, source 관성 oracle에 결함이 확인됐다. 기존 반례 일부는 차단했으나 전체 후보는 수용하지 않는다. provenance7/frame6 EXHAUSTED 및 eligibility2/다음1 충분 임계를 유지한다. 실제 SDK 진단0/로봇 연결0이며 남은 실행·R2 수리 출하는 동결했다. 다음 권위 경계는 별도053 계획이며 이 source를 고치거나 실행하지 않는다.

SDK NumPy2.3.1/SciPy1.17을 먼저 초기화하고 FFT/Rotation을 실제 검사한다. SimulationApp 생성 후에만 기존 학습 prefix를 검색 경로 끝에 추가한다. 파일 설치/삭제·재부팅은 하지 않는다.

```powershell
& ./src/simulation/contract_v3/launch.ps1 -Role test
& ./src/simulation/contract_v3/launch.ps1 -Role prepare -Stage sdk_preflight
& ./src/simulation/contract_v3/launch.ps1 -Role run -RunDir <SDK진단 run 절대경로>
& ./src/simulation/contract_v3/launch.ps1 -Role prepare -Stage robot_connection
& ./src/simulation/contract_v3/launch.ps1 -Role run -RunDir <로봇연결 run 절대경로>
& ./src/simulation/contract_v3/launch.ps1 -Role verify -RunDir <해당 run 절대경로>
```

두 단계는 각각 최대1회이며 시작 실패도 소비한다. 같은 단계 재실행은 성공/실패 모두 거절한다. SDK 진단이 실제 종료·제공자·동일 입력 검증을 통과해야 로봇 단계가 가능하다. 원래050의 조건부 두번째 실행은 제공하지 않는다. 전송 오류 때 새 실행을 시작하지 않고 기존 원자료를 회수한다. Python 파일 직접 실행/import는 지원하지 않는다.

source 의무 목록 static/bodies/trace/contact를 생산부와 소비부가 모두 정확히 순회한다. 실제 접촉 view의 인덱스/단위/용량과 마지막 sample을 저장·검사한다. 중력0/무명령10step·11행의 모델 연결 시험이며 물성은 가정이다. 실물 보정·모터/CAN·플래시·구매·학습·링검증은 하지 않는다.

최종 결과는 outputs/isaac-contract-v3/delivery.json과 비작성자 검토를 따른다. 기존047~050 BLOCK·physical4/provenance5 EXHAUSTED·eligibility2/다음1 충분 임계는 보존하며 이 준비 코드의 존재를 실제 연결 성공으로 표현하지 않는다.
