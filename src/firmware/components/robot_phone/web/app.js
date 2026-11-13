/* Actual target client; no credentials persisted and no speculative command retry. */
class PhoneControl {
  #lastStopOutcome=null;
  constructor(send, now = () => Date.now()) {
    this.send=send; this.now=now; this.credential=''; this.snapshot=null;
    this.seq=0n; this.lease='0'; this.ticket='0'; this.authority='';
    this.hidden=false; this.received=0; this.renewAt=0; this.busy=false;
    this.epoch=0; this.sessionEpoch=0; this.lastResult=null;
    this.handoff=null; this.angleRevision=0; this.angleBusy=false; this.angleToken=null;
    this.stopBinding=null; this.pollIssued=0; this.pollApplied=0;
  }
  get lastStopOutcome() { return this.#lastStopOutcome; }
  #observeLastTerminal(s) {
    if(s.phase!==4)return;
    for(const k of ['stop_verified','manual_power_cut_required'])if(typeof s[k]!=='boolean')throw Error('invalid terminal flag');
    for(const k of ['core_stop_verified','queue_stop_late'])if(s[k]!==undefined&&typeof s[k]!=='boolean')throw Error('invalid optional terminal flag');
    for(const k of ['selected_axis','core_state','core_fault','adapter_fault'])if(!Number.isInteger(s[k])||s[k]<0||s[k]>(k==='selected_axis'?65535:4294967295))throw Error('invalid terminal diagnostic');
    const previous=this.#lastStopOutcome;
    if(previous&&previous.boot===s.boot&&(BigInt(s.at)<BigInt(previous.at)||BigInt(s.generation)<BigInt(previous.generation)))throw Error('terminal observation reversed');
    // Whitelist primitives. Never retain a credential, lease or command identity.
    const record={};
    for(const k of ['boot','generation','at','stop_at','fault_at','selected_axis','core_state','core_fault','adapter_fault','stop_verified','manual_power_cut_required'])record[k]=s[k];
    for(const k of ['core_stop_verified','queue_stop_late'])record[k]=s[k]===undefined?null:s[k];
    this.#lastStopOutcome=Object.freeze(record);
  }
  lastStopOutcomeText() {
    const r=this.#lastStopOutcome;if(!r)return '종료 관측 기록 없음';
    const flag=v=>v===null?'미보고':String(v);
    return `과거 관측 · 현재 안전 상태를 뜻하지 않음\n부팅 ${r.boot} / generation ${r.generation} / 축 ${r.selected_axis}\n서버 시각 ${r.at} ms (해당 부팅 기준)\nstop_verified=${r.stop_verified} / core_stop_verified=${flag(r.core_stop_verified)}\nmanual_power_cut_required=${r.manual_power_cut_required}\n${r.manual_power_cut_required?'마지막 관측에서 수동 전원 차단 필요로 보고됨':'마지막 관측의 수동 차단 필요 보고: false'}\ncore fault=${r.core_fault} @ ${r.fault_at} / adapter fault=${r.adapter_fault}\nstop_at=${r.stop_at} / queue_stop_late=${flag(r.queue_stop_late)}`;
  }
  statusCredential() { return this.credential||this.stopBinding?.credential||''; }
  canStop() { return !!this.stopBinding||!!(this.credential&&this.snapshot); }
  stopRecoveryOnly() {
    const b=this.stopBinding;
    return !!b&&(b.session!==this.sessionEpoch||b.credential!==this.credential||(!this.handoff&&this.authority!=='normal'));
  }
  observeStopTerminal(s,b) {
    // Only poll calls this after authenticated, ordered status consumption.
    // Capturing the exact object before dispatch excludes pre-binding replies.
    if(!b||b!==this.stopBinding)return;
    if(s.boot!==b.boot||(s.selected_axis===b.axis&&s.phase===4&&BigInt(s.generation)>=BigInt(b.generation)))this.stopBinding=null;
  }
  async stop() {
    const b=this.stopBinding,s=this.snapshot;
    if(!this.canStop())throw Error('inactive/stale');
    const credential=b?b.credential:this.credential;
    const boot=b?b.boot:s.boot,generation=b?b.generation:s.generation,axis=b?b.axis:s.selected_axis;
    this.clear();const epoch=this.epoch;this.seq+=1n;
    const body=['v1',boot,generation,this.seq.toString(),this.seq.toString(),'stop','0',b?b.id:'0',String(axis),'0','0'].join('|');
    const r=await this.send('http://192.168.4.1:8081/api/stop',{method:'POST',headers:{'Content-Type':'text/plain','X-Session-Credential':credential},body});
    if(r.wire_error!==0||r.core_error!==0)throw Error(`rejected wire=${r.wire_error} core=${r.core_error}`);
    // ACK is not terminal evidence. Neither failures nor replies consume the key.
    if(this.epoch===epoch&&(!b||b===this.stopBinding))this.lastResult=r;
    return r;
  }
  get handoffIntent() { return this.handoff!==null; }
  cancelAngle() { this.angleRevision+=1; this.ticket='0'; }
  invalidateAuthority() {
    this.lease=this.ticket='0'; this.authority=''; this.epoch+=1; this.cancelAngle();
  }
  cancelHandoff() { this.handoff=null; }
  clear() { this.invalidateAuthority(); this.cancelHandoff(); }
  visible(value) { this.hidden=!value; if(this.hidden)this.clear(); }
  disconnect() { this.clear(); this.sessionEpoch+=1; this.credential=''; this.snapshot=null; }
  fresh() { return !!this.snapshot&&!this.hidden&&this.now()-this.received<600; }
  handoffCurrent(h=this.handoff) {
    const s=this.snapshot;
    return !!h&&h===this.handoff&&this.fresh()&&this.now()<h.until&&
      h.session===this.sessionEpoch&&h.credential===this.credential&&
      h.boot===s.boot&&h.axis===s.selected_axis&&s.phase<=2;
  }
  update(s) {
    for(const key of ['boot','generation','at','lease_owner','lease_until','config_oldest_at','fault_at','stop_at']) {
      if(typeof s[key]!=='string'||!/^\d+$/.test(s[key]))throw Error('invalid uint64 snapshot');
      if(BigInt(s[key])>18446744073709551615n)throw Error('uint64 overflow');
    }
    const previous=this.snapshot;
    if(previous&&s.boot===previous.boot&&BigInt(s.at)<BigInt(previous.at))throw Error('clock reversed');
    const namespaceChanged=previous&&(s.boot!==previous.boot||s.generation!==previous.generation);
    const phaseChanged=previous&&s.phase!==previous.phase;
    if(namespaceChanged||phaseChanged) {
      const h=this.handoff;
      const expected=h&&h.boot===s.boot&&h.axis===s.selected_axis&&
        h.session===this.sessionEpoch&&h.credential===this.credential&&this.now()<h.until&&
        s.boot===previous.boot&&s.generation!==previous.generation&&
        ((h.phase===0&&(s.phase===1||s.phase===2))||(h.phase===1&&s.phase===2));
      this.invalidateAuthority();
      if(expected)h.phase=s.phase; else this.cancelHandoff();
      if(namespaceChanged)this.seq=0n;
    }
    if(previous&&previous.selected_axis!==s.selected_axis)this.clear();
    if(previous&&(previous.angle_joint!==s.angle_joint||previous.angle_available!==s.angle_available))this.cancelAngle();
    this.snapshot=s;
    if(!previous||s.at!==previous.at||s.boot!==previous.boot)this.received=this.now();
    if(s.phase>=3||s.core_fault!==0||(s.adapter_fault!==0&&s.adapter_fault!==undefined))this.clear();
    if(this.handoff&&!this.handoffCurrent())this.clear();
  }
  async pair(pairing) {
    this.disconnect(); const session=this.sessionEpoch;
    const r=await this.send('/api/session',{method:'POST',headers:{'X-Pairing-Credential':pairing},body:''});
    if(session!==this.sessionEpoch)return;
    if(r.wire_error!==0||typeof r.credential!=='string'||! /^[a-f0-9]{32}$/.test(r.credential))throw Error('pairing denied');
    this.credential=r.credential;
  }
  async poll() {
    const binding=this.stopBinding,credential=this.statusCredential();
    if(!credential||this.hidden)return;
    const session=this.sessionEpoch,serial=++this.pollIssued;
    let s;
    try {
      s=await this.send('/api/status',{method:'GET',headers:{'X-Session-Credential':credential}});
      if(session!==this.sessionEpoch||credential!==this.statusCredential()||serial<this.pollApplied)return;
      this.pollApplied=serial;this.update(s);this.#observeLastTerminal(s);this.observeStopTerminal(s,binding);
    } catch(e) {
      if(session===this.sessionEpoch&&credential===this.statusCredential()&&serial>=this.pollApplied)this.disconnect();
      throw e;
    }
    // Command owns its response's epoch/error scope; status errors must not
    // re-clear a newer control context after a cancelled Acquire rejects late.
    if(this.handoffCurrent()&&this.handoff.mode==='transfer'&&s.phase===2&&this.handoff.ack&&!this.busy&&!this.angleBusy) {
      await this.command('handoff-result',{handoffContext:this.handoff});
    } else if(this.handoffCurrent()&&this.handoff.mode!=='transfer'&&s.phase===2&&s.ready&&!this.busy&&!this.angleBusy) {
      this.cancelHandoff(); await this.command('acquire');
    }
  }
  async command(op,extra={}) {
    if(op==='stop')return this.stop();
    if(this.stopRecoveryOnly())throw Error('정지 결과 확인 중 · 이동 권한 없음');
    if(this.angleBusy&&op!=='stop'&&extra.angleContext!==this.angleToken)throw Error('상대각도 처리 중');
    if(this.handoff&&op!=='stop'&&!(['handoff','handoff-acquire','handoff-result'].includes(op)&&extra.handoffContext===this.handoff))throw Error('운전 인계 처리 중');
    if(!this.credential||!this.snapshot||(op!=='stop'&&(!this.fresh()||this.busy)))throw Error('inactive/stale');
    if(op!=='stop'&&this.snapshot.phase>=3)throw Error('terminal');
    const s=this.snapshot,epoch=this.epoch,session=this.sessionEpoch,credential=this.credential;
    const angle=extra.angleContext,handoff=extra.handoffContext;
    const current=()=>this.fresh()&&this.epoch===epoch&&this.sessionEpoch===session&&
      this.credential===credential&&this.snapshot&&this.snapshot.boot===s.boot&&this.snapshot.generation===s.generation;
    const angleCurrent=()=>!angle||this.angleContextCurrent(angle);
    this.seq+=1n;
    if(op==='handoff-acquire'){
      if(this.stopBinding)throw Error('unresolved Stop identity');
      handoff.id=this.seq.toString();
      this.stopBinding=Object.freeze({id:handoff.id,boot:s.boot,generation:s.generation,axis:s.selected_axis,session:this.sessionEpoch,credential:this.credential});
    }
    let body;
    if(op==='joint-step') {
      this.angleInput(extra.angle,extra.unit);
      if(!this.angleCanStart()||extra.joint!==s.angle_joint)throw Error('각도 보정/운전 권한 미승인');
      body=['v2',s.boot,s.generation,this.seq.toString(),this.seq.toString(),op,this.lease,this.ticket,String(s.selected_axis),String(extra.joint),extra.unit,extra.angle].join('|');
    } else body=['v1',s.boot,s.generation,this.seq.toString(),this.seq.toString(),op,this.lease,(op==='handoff-result'?handoff.id:this.ticket),String(s.selected_axis),String(extra.direction||0),extra.unloaded?'1':'0'].join('|');
    if(op!=='stop')this.busy=true;
    const sentAt=this.now();
    try {
      const path=op==='stop'?'http://192.168.4.1:8081/api/stop':'/api/command';
      const r=await this.send(path,{method:'POST',headers:{'Content-Type':'text/plain','X-Session-Credential':credential},body});
      if(r.wire_error!==0||r.core_error!==0)throw Error(`rejected wire=${r.wire_error} core=${r.core_error}`);
      if(op==='handoff-acquire'||op==='handoff-result') {
        if(!this.handoffCurrent(handoff))return r;
        const uint=value=>typeof value==='string'&&/^\d+$/.test(value)&&BigInt(value)<18446744073709551615n;
        if(!uint(r.transfer_id)||r.transfer_id!==handoff.id)throw Error('invalid transfer receipt');
        if(op==='handoff-acquire'){
          if(r.transfer_state!==1)throw Error('transfer not pending');
          this.invalidateAuthority();handoff.ack=true;this.lastResult=r;return r;
        }
        if(r.transfer_state===1)return r;
        if(r.transfer_state!==2)throw Error('transfer ended');
        for(const field of ['transfer_generation','lease','lease_until','accepted_at','sequence_floor','grant_at','pending_until'])if(!uint(r[field]))throw Error('invalid transfer uint64');
        const elapsed=this.now()-sentAt,remaining=BigInt(r.lease_until)-BigInt(r.accepted_at);
        if(this.snapshot.phase!==2||r.transfer_generation!==this.snapshot.generation||
           BigInt(r.transfer_generation)!==BigInt(handoff.generation)+2n||r.lease==='0'||
           BigInt(r.sequence_floor)<1n||BigInt(r.sequence_floor)>=18446744073709551614n||
           BigInt(r.grant_at)>=BigInt(r.pending_until)||!Number.isFinite(elapsed)||elapsed<0||
           remaining-BigInt(Math.ceil(elapsed))<=100n)throw Error('expired transfer receipt');
        // 100ms reserves the next50ms pulse plus a <50ms command dispatch.
        this.invalidateAuthority();this.seq=this.seq>BigInt(r.sequence_floor)?this.seq:BigInt(r.sequence_floor);
        this.lease=r.lease;this.authority='normal';this.renewAt=this.now()-200;
        this.lastResult=r;this.cancelHandoff();return r;
      }
      // Old responses cannot restore authority or erase a newer context.
      if(!current()||!angleCurrent())return r;
      this.lastResult=r;
      if(['maintenance','drive','acquire'].includes(op)) {
        this.lease=r.lease; this.authority=op==='acquire'?'normal':'boot'; this.renewAt=this.now();
      }
      if(op==='ticket')this.ticket=r.ticket;
      if(op==='move'||op==='joint-step')this.ticket='0';
      if(['finish-maintenance','release','stop','handoff'].includes(op))this.invalidateAuthority();
      return r;
    } catch(e) {
      if((['handoff','handoff-acquire','handoff-result'].includes(op)&&handoff&&this.handoff===handoff)||(current()&&angleCurrent()))this.clear();
      throw e;
    } finally {
      // Stop has its own lane and never releases an outstanding normal request.
      if(op!=='stop')this.busy=false;
    }
  }
  async handoffAndAcquire() {
    if(!this.fresh()||this.snapshot.phase!==0||this.busy||this.angleBusy||this.handoff||this.stopBinding)throw Error('handoff unavailable');
    const s=this.snapshot;
    this.handoff={boot:s.boot,axis:s.selected_axis,phase:0,session:this.sessionEpoch,credential:this.credential,until:this.now()+700};
    await this.command('handoff',{handoffContext:this.handoff});
  }
  async transferAndAcquire() {
    if(!this.fresh()||this.snapshot.phase!==0||this.busy||this.angleBusy||this.handoff||this.stopBinding)throw Error('handoff unavailable');
    const s=this.snapshot;
    this.handoff={mode:'transfer',id:'0',ack:false,generation:s.generation,boot:s.boot,axis:s.selected_axis,phase:0,session:this.sessionEpoch,credential:this.credential,until:this.now()+1147};
    await this.command('handoff-acquire',{handoffContext:this.handoff});
  }
  async move(direction) {
    if(this.angleBusy)throw Error('상대각도 처리 중');
    if(this.authority!=='normal'||this.lease==='0')throw Error('acquire explicitly first');
    await this.command('arm'); if(!this.fresh()||this.authority!=='normal')throw Error('cancelled');
    await this.command('ticket'); if(!this.fresh()||this.authority!=='normal')throw Error('cancelled');
    await this.command('move',{direction});
  }
  angleInput(raw,unit) {
    if(typeof raw!=='string'||!/^\-?(?:0|[1-9]\d{0,5})(?:\.\d{1,18})?$/.test(raw)||!Number.isFinite(Number(raw))||Number(raw)===0||!['deg','rad'].includes(unit))throw Error('0이 아닌 십진수와 deg/rad 단위를 입력하세요');
  }
  angleCanStart() {
    const s=this.snapshot;
    return this.fresh()&&s.phase===2&&s.ready===true&&s.angle_available===true&&
      Number.isInteger(s.angle_joint)&&s.angle_joint>=1&&s.angle_joint<=6&&[1,2].includes(s.selected_axis)&&this.authority==='normal'&&this.lease!=='0';
  }
  angleContextCurrent(context) {
    const s=this.snapshot;
    return this.fresh()&&s.phase===2&&this.authority==='normal'&&
      context.revision===this.angleRevision&&this.epoch===context.epoch&&this.lease===context.lease&&
      s.boot===context.boot&&s.generation===context.generation&&s.selected_axis===context.axis&&s.angle_joint===context.joint&&s.angle_available===true;
  }
  angleFence(context,ready=true) {
    if(!this.angleContextCurrent(context)||(ready&&!this.angleCanStart()))throw Error('상대각도 요청 취소됨 (이미 전송한 요청은 별도 정지 확인 필요)');
  }
  async moveAngle(raw,unit) {
    this.angleInput(raw,unit);
    if(this.busy||this.angleBusy||this.handoff||!this.angleCanStart())throw Error('보정/제어권/이동 준비 상태를 확인하세요');
    const s=this.snapshot,context={epoch:this.epoch,revision:this.angleRevision,lease:this.lease,boot:s.boot,generation:s.generation,axis:s.selected_axis,joint:s.angle_joint};
    this.angleBusy=true; this.angleToken=context;
    try {
      await this.command('arm',{angleContext:context});this.angleFence(context);
      await this.command('ticket',{angleContext:context});this.angleFence(context);
      await this.command('joint-step',{angleContext:context,joint:context.joint,angle:raw,unit});
      this.angleFence(context,false);
    } catch(e) {
      this.cancelAngle(); throw e;
    } finally {
      this.angleBusy=false; this.angleToken=null;
    }
  }
  async pulse() {
    if(!this.fresh()){this.clear();return;}
    if(this.handoff&&!this.handoffCurrent()){this.clear();return;}
    if(this.authority&&this.lease!=='0'&&!this.busy&&!this.angleBusy&&!this.handoff&&this.now()-this.renewAt>=200) {
      this.renewAt=this.now(); await this.command(this.authority==='normal'?'renew':'maintenance-renew');
    }
  }
}
if(typeof module!=='undefined') module.exports={PhoneControl};
if(typeof document!=='undefined') {
  const $=id=>document.getElementById(id);
  const control=new PhoneControl(async(path, options)=>{const response=await fetch(path,{...options,cache:'no-store',credentials:'omit'});if(!response.ok)throw Error(`HTTP ${response.status}`);return response.json();});
  const fail=e=>{$('message').textContent=String(e.message || e);render();};
  const run=fn=>async()=>{try{await fn();render();}catch(e){fail(e);}};
  $('pair').onclick=run(()=>control.pair($('pairing').value.trim()).then(()=>{$('pairing').value='';return control.poll();}));
  document.querySelectorAll('[data-op]').forEach(button=>button.onclick=run(()=>control.command(button.dataset.op,{unloaded:button.dataset.op==='unloaded'})));
  $('handoff').onclick=run(()=>control.transferAndAcquire());$('positive').onclick=run(()=>control.move(0));$('negative').onclick=run(()=>control.move(1));
  $('angle-send').onclick=run(()=>control.moveAngle($('angle-input').value,$('angle-unit').value));
  function render(){const s=control.snapshot;const active=control.fresh()&&!!control.credential;document.querySelectorAll('[data-motion]').forEach(b=>b.disabled=!active||control.stopRecoveryOnly()||control.busy||control.angleBusy||control.handoffIntent||s.phase>=3);$('stop').disabled=!control.canStop();
    $('angle-send').disabled=control.busy||control.angleBusy||!control.angleCanStart();
    $('angle-state').textContent=s?.angle_available?`관절 J${s.angle_joint} · ${s.ready?'상대 이동 준비 완료':'이동 중/확인 중'}`:'실물 보정 미승인 · 숫자 이동 불가';
    $('last-stop-outcome').textContent=control.lastStopOutcomeText();
    if(!s){$('status').textContent='연결 없음 · 권한 없음';return;}
    const phase=['부팅/유지보수','운전 확인','운전','정지 중','종료'][s.phase];
    const positions=s.positions.slice(0,s.axis_count).map((p,i)=>`축 ${s.axis_count===1?s.selected_axis:i+1}: ${p.valid?`${p.value} counts / ${BigInt(s.at)-BigInt(p.at)} ms 전`:'위치 미확인'}`).join('\n');
    const config=s.config_oldest_at==='0'?'미확인':`${BigInt(s.at)-BigInt(s.config_oldest_at)} ms 전`;
    $('status').textContent=`${phase} / generation ${s.generation}\ncore state ${s.core_state} · fault ${s.core_fault} @ ${s.fault_at}\n선택축 ${s.selected_axis} (변경 불가)\n${positions}\n설정 가장 오래된 실제 읽기: ${config}\n권한 소유자 ${s.lease_owner} / 만료 ${s.lease_until}\nstop_verified=${s.stop_verified}\nmanual_power_cut_required=${s.manual_power_cut_required}\nStop queue late=${s.queue_stop_late} / adapter fault=${s.adapter_fault} / core_stop_verified=${s.core_stop_verified}\n${control.stopRecoveryOnly()?'정지 상태 확인 중 · 이동 비활성':active?'상태 수신 중':'이동 비활성 · 최종 수신 상태'}`;
    if(control.lastResult)$('message').textContent=`queued=${control.lastResult.queued}, core accepted at=${control.lastResult.accepted_at}, wire=${control.lastResult.wire_error}, core=${control.lastResult.core_error}`;
  }
  document.addEventListener('visibilitychange',()=>{control.visible(!document.hidden);render();});
  window.addEventListener('offline',()=>{control.disconnect();render();});
  setInterval(()=>{if(!document.hidden)control.poll().then(render).catch(fail);},250);
  setInterval(()=>{control.pulse().then(render).catch(fail);},50);render();
}
