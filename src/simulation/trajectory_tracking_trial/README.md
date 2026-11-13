# 077 — quintic 위치·속도 참조 일치

기존52초 위치 경로와 해석적 시간 미분을 함께 명령한다. 속도는binary32로 명시 인코딩하고 64bit참조·명령·실제tensor readback을 독립root에서 검사한다. 게인64/16·모든 제약·정규화·영시간 초기화·시간 코덱·포그 숨김은076과 같다. 실물 운전 없음. 상세와 예산은 docs/design/077-trajectory-velocity-tracking.md, 결과는 outputs/isaac-trajectory-tracking-v1/.
