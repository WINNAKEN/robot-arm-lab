> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 140 — 그리퍼 STS3215 TTL 식별 반영

2026-11-11 KST. 사용자그리퍼사진은상품상세화면이며 Feetech STS3215 12V30kg·cm TTL, ST-3215-C018로읽힌다. 실제명판·FW/핀방향/영점은미검증이다. J5/J6 CAN 사용자확인은그대로,그리퍼를TTL반이중버스로정리하고현재혼합버스준비안을추가한다.

S 문서단위: 이계획과 `docs/specs/gripper-ttl140.html` 2source, 근거/사실/PDF/검토는 `outputs/gripper-ttl-identification-140/`. 원138/139자료·모델·프로필·소스·설정무변경. 물리포트/급전/flash/송신/구동/구매/설치/원격/Git/Drive0. 새코드/드라이버추가·동작허가없음. 기존완료예산/라운드재개아님.

Root작성→비작성자문서L4, L2생략(document-only S), reviewer새내부1500s/closing180/L4max2/no5, 동일계열폴백의기존승인/잔여편향유지. 원139/138검토상태보존.

원문: Feetech ST-3215-C018 A/0 2023-07-20 제조사datasheet(공식작성PDF를RobotShop이호스팅) p3정격12V·30kg·cm stall·2.7A stall, p4 GND/Vcc/SignalTTL·halfduplex8N1·공장1Mbps, p8 high2–5V. Waveshare공식ST3215페이지는12V/7.4V형을구분하며12Vtypical·TTL전용드라이버경로/전압일치조건을안내한다. 원자료사이넓은전압범위/카운트분모가달라상한을설정값으로승격하지않고공칭12V와현품확인으로제한한다.

수용6: 1상품목록식별vs실물확인구분 2J5J6CAN/그립TTL경로분리·H/L/A/B에S직결금지 3TTL반이중/신호레벨인터페이스필요·ESP32GPIO직결비승인/컨트롤러2개필수아님 4그립12V전원·24V직결금지·G/V/S기능기준/USB전원대체금지 5CAN/MKS코드재사용불가·읽기부터/조립기구중립이동·연속회전·자동보정없음 6출력시각/정확핀/경계보존. TTL어댑터보유질문은답대기이며특정구매·핀배정·플래시명령은작성하지않는다.
