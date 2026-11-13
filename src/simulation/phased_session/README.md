# 054 phased SDK session

설치 전체 감사를 SDK 없는 별도 프로세스(900s/1회)로 실행하고, 원본 정상 증거가 있는 경우에만 앱 관측(600s/1회)을 허용한다. 원053 원장/실패·가정과 source는 보존한다. 실제 wait code·timeout policy·remote shell·SSH·최상위 code를 별도로 기록한다. 호스트/정적 검토/native 결과는 서로 다른 증거다.

`launch.ps1 -Role test`, `-Role prepare -Purpose installation_audit`, `-Role run -RunDir <prepared absolute path>`, 조건부 `-Role prepare -Purpose app_observation`, `-Role run -RunDir <prepared absolute path>`, 읽기만 하는 `-Role verify -RunDir <absolute path>`.

실물 보정·모터/CAN·재부팅·설치·전역 변경·학습·링 검증은 하지 않는다. 현재 결과는 outputs/isaac-phased-v1/HANDOFF.md와 delivery.json을 따른다.
