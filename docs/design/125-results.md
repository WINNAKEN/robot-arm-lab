> 개발 이력: 작성 당시의 계획·결과입니다. 현재 상태는 [STATUS](../STATUS.md)를 확인하세요. 원시 로그와 로컬 경로 일부는 공개본에서 제외했습니다.

# 125 결과 — 참고 영상 전달 / v4 가져오기 실패

2026-11-07 KST. 실제42초 Isaac 영상(v3 참고본) (비공개 링크 제외), Drive 폴더 (비공개 링크 제외). 화면상 REFERENCE URDFv3/notv4 표시는새v4와혼동을막기위해추가했다. 421frames/42.1s/201559B; 전체decode/처음중간끝시각검사및Drive원격바이트SHA4964e61446620d2b614131a4f592bd060546d9df58c80915abdc7b651ede8489 일치. 34초정착J3/J5 FAIL은유지했다. 이영상은116실제동작기록이며v4검증결과가아니다.

125수리·HOST뒤 L4R2 main9905d577…/lens688db032… PASS8/0,sourceF35498e4b…/50핀으로actualprepare했다. 새runf3bdb19d83ea4615af27ddb17150c6fc,SDK38180/6.2.0-rc.14,고정기간407811.953→410511.953/2700s,GO1/newSDK1/retry0. 운송childREAPED exit0·활성0/timeoutfalse; nativeSDKREAPED/consumerexit2/결과FAIL. 종료408120.453,원125마커와grant/기간불변. 추가SDK0. 별도Root읽기조회2회는pipelineSSH1과분리계수한다.

회수report importFAIL,hold/small/large NOT_RUN,completed_steps0/RGB0/새v4MP40. native.py593의fresh_stage:context.new_stage()뒤old_roots의layer.identifier에서Boost.Python.ArgumentError였다. 새root/session선언후이지만Clear전실패했다. fresh-stage.json은before/after_new census와서로다른익명layerIDs/clock0를보존했다. 실제새장면에/Render와기본camera등이있다는것도이번census에서확인됐으며,지난123미관측prim목록을소급확정하지않는다.

공식OpenUSD25.11 [object model](https://openusd.org/25.11/api/_usd__page__object_model.html)과[Python wrapper](https://raw.githubusercontent.com/PixarAnimationStudios/OpenUSD/v25.11/pxr/usd/sdf/wrapLayer.cpp)에따라약한oldlayerhandle수명문제를우선가설로잡았다. Root126수리후보는switch전FindOrOpenstrongfactory pin/정확identity확인/old내용hash를보존하며old/newguard와함수밖바이트를유지한다. 실제pxr없음/설치0,HOST수명모델에서원실패재현과weakFind음성검출을포함한29건PASS,독립검토중이다. 이는아직SDK원인폐쇄나실제v4수용이아니다.

영상추가요청과함께별도125sanitized결과JSON도보내려했으나자동승인검토가영상외내부결과/대상폴더를승인범위밖으로판단해거절했다. 해당추가업로드는제외했고로컬delivery/에보존했다. 우회0/재시도0. 기존v3MP4업로드와원격바이트검증은완료상태다.

게인64/16·simulationcap12/7·velocity·0.5deg/1deg_s/34s·URDFv4원본불변. 실물CAN/RS485·포트·급전·flash·설치·네트워크/시계변경0. 124Gitutility절차BLOCK/퇴역및원HEAD302aad7… 불변. 정본outputs/mp18-video-run-125/{runtime-final.json,native-result.json,run-result.json,transport.json},reference-v3/Drive-delivery.json,delivery/result-upload-blocked.json.
