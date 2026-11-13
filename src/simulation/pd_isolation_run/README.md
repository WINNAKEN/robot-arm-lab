# 081 — 독립 관성 기준물로 PD 토크의 의미 확인

로봇의 제어·게인·cap·경로·물리 기준은079와 동일하다. 무연결1축 기준물 둘을 force/acceleration으로 사전 고정하고 같은 물리 스텝에서 관측한다. 외부명령0인 PD-only의 관성 토크만 단독PD 측정이며 combined와 robot PD는 식별되지 않으면 UNKNOWN이다. 오류는 원시 journal/prefix 및 별도 관측FAIL로 보존하고0대체하지 않는다. native각목적1회·전체45분·launch900초 여유, 실물 제외. 계획080과 outputs/isaac-pd-isolation-run-v1/ 참조.
