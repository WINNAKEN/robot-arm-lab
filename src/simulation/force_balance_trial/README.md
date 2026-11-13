# 082 — 비영COM full6D와 로봇 M/C/G 추정 대조

로봇 제어·게인·cap·경로·물리 기준은081과 동일하다. 기준물에만 중력을 끄고 COM0/Z와 비영COM/Y·Rz45의 전체 힘/모멘트를 독립 관성식으로 대조한다. 같은 원step의 robot M/C/G·전후속도는 readonly 수집하며 유한차분 역동역학 추정치다. combined/robot 단독PD와 포화는 미식별이면 UNKNOWN이다. 원시 journal/prefix·별도 관측FAIL을 보존하고0대체하지 않는다. native각목적1회·전체45분·launch900초 여유, 실물 제외. 계획082와 outputs/isaac-force-balance-v1/ 참조.
