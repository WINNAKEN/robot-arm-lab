> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 076 — float64 렌더 시간 코덱 수리

사용자의정규화/게인수리·기준무완화·정지PASS후큰6축·포그숨김요청을이어수행하는한정integration단위다.075import/정지PASS,첫motion은492step(4.1초)에서capturetime게이트실패actual1이며원자료·원장보존. 물리기준실패로재분류하거나075횟수를되돌리지않는다.075는별도결과로종결한다.

관측: rawscheduled41/10, 실제engine float64 4.1, GPUdispatcher/RP각4099999999/1e9, 3nodecounter모두증가. 기존exactFraction floor는4100000000을요구했다. 설치get_reduced_ref_time는gcd약분뿐이다. 실제binary64 4.1*1e9=4099999999.9999995를정수로내리는코덱과exactrational코덱의불일치다. 기존41프레임의float64변환은모두실제RefTime과일치한다.

capture.py는rawscheduledpair를보존하고 float64(n/d)→float64(*1e9)→int 순서로scheduled를인코딩한다. rawengine시각도기록하고float(rawfraction)와exactequal을요구한다. float64 hex도기록한다. root는독립적으로원pair에서binary64연산/hex/정수결과를재계산하고engine_before시각과0오차로결속한다. epsilon추가/1tick허용없음: 예상정수보다1tick이라도이전이면실패. 원3nodegeneration증가·동일wrapper/path/type·동일RP·render전후물리시각/상태불변·PNGproof·물리기준유지.

새소유src/simulation/render_time_trial/,outputs/isaac-render-time-v1/,별도076원장. 075source13복사본에서capture코덱/독립root검사/해당HOST와경로만수정. 모델/SDK/초기화/게인64/16/정규화/52초경로/threshold/포그숨김불변. L2/L4각max2, native import1/smoke1/motion1 각600초; 새한정단위M30분(시작2026-10-29 23:30:00UTC/종료2026-10-30 00:00:00UTC,기존075예산연장주장없음). 이내전송·회수·인계,600초미만남으면native시작금지. 전체요청이복수계획이되었으므로L급의유한별도단위로기록한다. 불지원시추가루프없음.

HOST는실제실패pair4.1/이전41frame/0.1초간격521시점/1tickstale/다른엔진float/hex변조/시간field위조를검사한다. 비작성자L4후freshimport→새정지수용→큰동작1회. 실제영상·원결과저장,derived진단은nativePASS아님. 실물/보정/설치/재부팅/구매/학습없음,링보류·물성가정유지.
