// Exact fixture prefix extracted from unchanged historical tests by run.ps1.
// The old nested test-main macros are not composed into this new executable.
#include "angle_fixture.inc"
int main(int argc,char** argv){
 if(argc!=3)return 2;
 AngleFixture f(static_cast<unsigned>(std::stoul(argv[1])),std::strcmp(argv[2],"true")==0);
 f.state(static_cast<unsigned>(robot_boot::State::NeedsMaintenance));
 std::string line;
 while(std::getline(std::cin,line)){
  if(line=="S"){status(f);continue;}
  if(line.rfind("T ",0)==0){f.delay(static_cast<unsigned>(std::stoul(line.substr(2))));std::cout<<"{}"<<std::endl;continue;}
  if(line=="M"){std::cout<<"{\"moves\":"<<f.p.moves<<",\"violations\":"<<f.p.violations<<"}"<<std::endl;continue;}
  if(line=="R"){f.owner.revoke_joint_mapping();std::cout<<"{}"<<std::endl;continue;}
  if(line.rfind("C ",0)==0){
   phone::Wire w;if(!phone::parse(line.substr(2),w)){std::cout<<"{\"wire_error\":1,\"core_error\":0}"<<std::endl;continue;}
   f.favorable();const auto result=f.wire(w);
   std::cout<<"{\"wire_error\":"<<unsigned(result.error)<<",\"core_error\":"<<result.core_error
    <<",\"lease\":\""<<result.lease<<"\",\"ticket\":\""<<result.ticket<<"\",\"accepted_at\":\""<<result.accepted_at<<"\"}"<<std::endl;continue;
  }
  return 3;
 }
 return 0;
}
