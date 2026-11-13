  if(line=="M"||line=="F"){
   bool slot=f.p.ps.tx_pending==0&&f.p.size==0;Time margin=400;
   for(unsigned a=0;a<2;++a){std::array<Time,3> times{};unsigned count=0;
    for(unsigned i=0;i<f.p.sent_count;++i){const auto& t=f.p.sent[i];if(t.frame.id==a+1&&t.frame.data[0]==0x31&&t.at<=f.p.received_diag[a][1]){if(count<3)times[count++]=t.at;else{times[0]=times[1];times[1]=times[2];times[2]=t.at;}}}
    slot=slot&&count==3&&times[1]>=times[0]+140&&times[2]>=times[1]+140;
    for(const auto t:times){if(f.p.now<t||f.p.now-t>=400)slot=false;else if(400-(f.p.now-t)<margin)margin=400-(f.p.now-t);}
    for(const auto t:f.p.received_diag[a]){if(!t||f.p.now<t||f.p.now-t>=400)slot=false;else if(400-(f.p.now-t)<margin)margin=400-(f.p.now-t);}
   }
   std::cout<<"{\"at\":\""<<f.p.now<<"\",\"moves\":"<<f.p.moves<<",\"transfer_attempts\":"<<f.owner.transfer_attempts()<<",\"operator_slot\":"<<(slot&&margin>=12?"true":"false")<<",\"margin\":"<<margin<<",\"paired_mask\":"<<unsigned(f.owner.snapshot().paired_mask)<<",\"calibration_measured\":"<<((f.calibration[0].measured||f.calibration[1].measured)?"true":"false")<<",\"frames\":[";
   for(unsigned i=0;line=="F"&&i<f.p.sent_count;++i){if(i)std::cout<<",";const auto& r=f.p.sent[i];std::cout<<"{\"at\":\""<<r.at<<"\",\"axis\":"<<r.frame.id<<",\"data\":[";for(unsigned j=0;j<r.frame.dlc;++j){if(j)std::cout<<",";std::cout<<unsigned(r.frame.data[j]);}std::cout<<"]}";}
   std::cout<<"]}"<<std::endl;return;
  }
