# CAD 실제 회전 방향 대조

원본 v2를 저장하지 않고 SolidCraft CLI의 메모리 복사에서 `joint.drive`를 실행한다.
코어 FK와 세계좌표에 만들어진 CAD occurrence의 전체 rigid placement를 비교한다.
27자세와 각 자세에서 실제0복귀를 관측한다. 양/음 부호 모두 대조한다.

```powershell
py -B C:/projects/robot-arm-lab/src/native_direction/measure.py build --root C:/projects/robot-arm-lab --cli C:/tools/SolidCraft-0.18.2/solidcraft-0.18.2-windows-x64-portable/solidcraft-cli.exe
py -B C:/projects/robot-arm-lab/src/native_direction/measure.py verify --root C:/projects/robot-arm-lab --cli C:/tools/SolidCraft-0.18.2/solidcraft-0.18.2-windows-x64-portable/solidcraft-cli.exe
$env:ND_CLI = 'C:/tools/SolidCraft-0.18.2/solidcraft-0.18.2-windows-x64-portable/solidcraft-cli.exe'
py -B C:/projects/robot-arm-lab/src/native_direction/test_direction.py
```

실제 CLI는 폴더명과 달리0.20.0이다. 실행 파일과 모델/코어/승인 receipt 해시를 고정한다.
출력은 `outputs/native-direction-v1/current.json`의 run에 원문/명령/보고서/manifest를 보존한다.
공식 +1 대조가 다르면 **report BLOCK, current FAILED, build/verify exit1**이 정상적인 보수 판정이다.
전체 -1 대조는 원인 진단 가설이며 펌웨어/CAD/코어/모터 매핑을 자동 변경하지 않는다.
실제 방향 불일치를 기대대로 거절하는 회귀시험 PASS와 CAD 일치 PASS를 구분한다.
입력 복원만으로 이전 PASS를 사용하지 않고 명시적으로 다시 측정한다.

`component.list.transform`의 배열은 열 기준이므로 행 기준으로 전치한다.
이 해석은 CAD가 별도로 반환하는 joint.inspect의 세계 origin/z/x와 직접 교차검증한다.
최초 J1+5를 반대 방향으로 읽은 설명은 이 표기 혼동이었고, 실패한 초기 측정/정정 기록을 보존했다.

부모는 저장소 첫 읽기 전 BUILDING을 기록한다. 정상 Python/stdlib·온전한 entry script·유효한
절대 root/CLI와 단일 writer·쓰기 가능한 저장소가 신뢰 기반이다. 부모 자체 시작 불가/kill/
전원 손실/저장 불가에는 terminal marker 보장을 주장하지 않는다. CLI timeout은60초다.
스크립트가 남긴 원문 응답은 실제 solver의 occurrence 배치 증거이며, body vertex나 링 형상 검증이 아니다.
링 형상/충돌/강도·실물 방향/영점/감속비·CAN/Isaac 수용은 제외한다. 다른 CAD 리비전에는 일반화하지 않는다.
독립 수용 판정/이월 원장은 `.dev/native-direction-evidence/`를 따른다.
