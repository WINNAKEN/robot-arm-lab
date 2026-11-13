// Actual compiled Owner/Boot/Run/Gate, not the031 reference model.
static bool boot_slot(AngleFixture& f){
 if(f.p.ps.tx_pending||f.p.size)return false;
 for(unsigned a=0;a<2;++a){std::array<Time,3> t{};unsigned count=0;
  for(unsigned i=0;i<f.p.sent_count;++i){const auto& x=f.p.sent[i];if(x.frame.id==a+1&&x.frame.data[0]==0x31&&x.at<=f.p.received_diag[a][1]){
   if(count<3)t[count++]=x.at;else{t[0]=t[1];t[1]=t[2];t[2]=x.at;}}}
  if(count!=3||t[1]<t[0]+140||t[2]<t[1]+140)return false;
  for(const auto at:t)if(f.p.now<at||f.p.now-at>=385)return false;
  for(const auto at:f.p.received_diag[a])if(f.p.now<at||f.p.now-at>=385)return false;
 }return true;
}
static void prepare(AngleFixture& f){
 f.state(static_cast<unsigned>(robot_boot::State::NeedsMaintenance));f.accepted(phone::Op::Maintenance);
 f.renewing=true;f.renewed=f.p.now;f.accepted(phone::Op::Unloaded);f.accepted(phone::Op::DisableAll);
 f.state(static_cast<unsigned>(robot_boot::State::ReadyDisabled));f.accepted(phone::Op::FinishMaintenance);
 f.lease=0;f.accepted(phone::Op::Drive);f.accepted(phone::Op::EnableSelected);
 f.state(static_cast<unsigned>(robot_boot::State::Granted));f.delay(600);
 unsigned n=0;while(!boot_slot(f)&&n++<800)f.step();CHECK(boot_slot(f));
 f.renewing=false;
}
static phone::Wire combined(AngleFixture& f){auto w=f.message(phone::Op::HandoffAcquire);w.unloaded=false;w.ticket=0;return w;}
static phone::Result receipt(AngleFixture& f,Time id,Time phase=0){auto w=f.message(phone::Op::HandoffResult);w.unloaded=false;w.ticket=id;if(phase)w.phase=phase;return f.wire(w);}
static int transfer_tests(){
 for(unsigned axis:{1u,2u})for(bool measured:{false,true}){
  AngleFixture f(axis,measured);prepare(f);const auto w=combined(f);const auto bootgen=w.phase;
  const auto accepted=f.wire(w);CHECK(accepted.error==phone::Error::None);
  CHECK(accepted.transfer_id==w.request&&accepted.transfer_state==phone::TransferState::Pending&&accepted.lease==0);
  CHECK(accepted.pending_until<=accepted.accepted_at+700);
  CHECK(accepted.pending_until>f.p.now);
  for(unsigned n=0;n<650&&f.owner.transfer_attempts()==0;++n)f.step();
  CHECK(f.owner.transfer_attempts()==1);const auto r=receipt(f,w.request,bootgen);
  CHECK(r.error==phone::Error::None&&r.transfer_state==phone::TransferState::Granted&&r.lease!=0);
  CHECK(r.grant_at<r.pending_until&&r.lease_until==r.grant_at+800&&r.sequence_floor==1);
  CHECK(r.transfer_generation==bootgen+2&&f.p.moves==0);
  const auto until=r.lease_until;f.delay(110);const auto again=receipt(f,w.request,bootgen);
  CHECK(again.lease==r.lease&&again.lease_until==until&&f.owner.transfer_attempts()==1);
  // Wrong credential cannot read or use the cross-generation Stop exception.
  phone::Envelope pair;pair.pairing=true;pair.credential=seed().pairing;const auto second=f.transact(pair);CHECK(second.paired);
  auto q=f.message(phone::Op::HandoffResult);q.ticket=w.request;q.unloaded=false;
  phone::Envelope e;e.credential=second.credential;e.wire=q;CHECK(f.transact(e).error==phone::Error::Denied);
  auto scoped=f.message(phone::Op::Stop);scoped.phase=bootgen;scoped.ticket=w.request;
  e.listener=phone::Listener::Stop;e.wire=scoped;
  CHECK(f.transact(e).error==phone::Error::Phase&&f.owner.snapshot().stop_at==0);
  scoped.phase=bootgen+3;CHECK(f.wire(scoped).error==phone::Error::Phase&&f.owner.snapshot().stop_at==0);
  auto bad=q;bad.ticket++;CHECK(f.wire(bad).error==phone::Error::Denied);
  f.lease=r.lease;f.seq=1;f.accepted(phone::Op::Renew);CHECK(f.owner.transfer_attempts()==1);
  // Explicit current Stop closes the receipt and never generates movement.
  f.accepted(phone::Op::Stop);const auto stopped=f.owner.snapshot();
  const auto closed=receipt(f,w.request,bootgen);CHECK(closed.lease==0&&closed.transfer_state!=phone::TransferState::Granted);
  CHECK(f.owner.snapshot().stop_at==stopped.stop_at&&f.p.moves==0);
 }
 for(unsigned mismatch=0;mismatch<4;++mismatch){
  AngleFixture f;prepare(f);const auto w=combined(f);CHECK(f.wire(w).error==phone::Error::None);
  auto stop=f.message(phone::Op::Stop);stop.phase=w.phase;stop.ticket=w.request;
  if(mismatch==1)++stop.ticket;if(mismatch==2)++stop.boot;if(mismatch==3)stop.axis=2;
  const auto result=f.wire(stop);
  if(mismatch==0){CHECK(result.error==phone::Error::None);CHECK(f.owner.snapshot().stop_at!=0);f.delay(500);CHECK(f.owner.transfer_attempts()==0&&f.p.moves==0);}
  else{CHECK(result.error==phone::Error::Phase);CHECK(f.owner.snapshot().stop_at==0);}
 }
 {AngleFixture f;prepare(f);const auto w=combined(f);
  phone::Envelope normal;normal.job=++f.job;normal.enqueued_at=f.p.now;normal.credential=f.credential;normal.wire=w;CHECK(f.owner.enqueue(normal));
  phone::Envelope stop;stop.job=++f.job;stop.enqueued_at=f.p.now;stop.credential=f.credential;stop.listener=phone::Listener::Stop;stop.wire=f.message(phone::Op::Stop);stop.wire.ticket=w.request;CHECK(f.owner.enqueue(stop));
  f.owner.tick();CHECK(f.owner.snapshot().stop_at!=0&&f.owner.transfer_attempts()==0);}
 {AngleFixture f;prepare(f);const auto w=combined(f);CHECK(f.wire(w).error==phone::Error::None);f.p.auto_reply=false;
  f.delay(800);CHECK(f.owner.transfer_attempts()==0&&f.owner.snapshot().stop_at!=0);const auto first=f.owner.snapshot();
  receipt(f,w.request,w.phase);CHECK(f.owner.snapshot().stop_at==first.stop_at&&f.owner.snapshot().fault_at==first.fault_at);}
 phone::Wire parsed;
 CHECK(phone::parse("v1|11|1|7|7|handoff-acquire|3|0|1|0|0",parsed)&&parsed.op==phone::Op::HandoffAcquire);
 CHECK(phone::parse("v1|11|3|8|8|handoff-result|0|7|1|0|0",parsed)&&parsed.op==phone::Op::HandoffResult);
 CHECK(!phone::parse("v1|11|3|8|8|handoff-result|0|7|1|0|1",parsed));
 std::printf("TRANSFER actual Owner/Boot/Run/Gate PASS assertions=%u; no hardware\n",assertions);return 0;
}
