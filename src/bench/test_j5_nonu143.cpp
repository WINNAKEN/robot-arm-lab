#include "robot_diagnostic/execution.hpp"
#include <cstdio>
#include <cstdlib>
#include <initializer_list>

using namespace robot_diagnostic;
namespace {
unsigned assertions=0;
void check(bool ok,const char* message) {
    ++assertions;
    if(!ok){std::fprintf(stderr,"FAIL: %s\n",message);std::exit(1);}
}
Observed fixture(Board board,std::uint16_t axis=1) {
    Observed o{};o.board=board;o.protocol=Protocol::MakerbaseCan;
    o.hardware_revision="HOST_FIXTURE_ONLY";o.firmware_version="HOST_FIXTURE_ONLY";
    o.can_id=axis;o.bitrate=500000;o.tx_gpio=15;o.rx_gpio=16;
    o.wiring=o.power_on_motion_excluded=Check::Pass;
    return o;
}
}
int main() {
    static_assert(static_cast<int>(Board::Unknown)==0);
    static_assert(static_cast<int>(Board::WaveshareCanU)==1);
    static_assert(static_cast<int>(Board::Other)==2);
    static_assert(static_cast<int>(Board::WaveshareCan)==3);
    for(auto board:{Board::WaveshareCan,Board::WaveshareCanU})for(auto axis:{1,2}) {
        const auto p=prepare_profile(fixture(board,static_cast<std::uint16_t>(axis)),static_cast<std::uint16_t>(axis));
        check(p.readiness==Readiness::ReadyForReview,"both explicit model variants reach review with complete HOST fixture");
        check(p.missing==0&&p.mismatch==0,"no missing or mismatch for HOST fixture");
        check(!p.transport.hardware_approved,"review-ready never grants physical authority");
        check(p.transport.axis==axis,"axis retained");
        check(p.transport.board_confirmed&&p.transport.can_protocol_confirmed,"observation checks retained");
    }
    Observed actual_partial{};actual_partial.board=Board::WaveshareCan;
    const auto pending=prepare_profile(actual_partial,0);
    check(pending.readiness==Readiness::Pending,"user model alone stays pending");
    check(pending.missing!=0,"actual missing observations retained");
    check((pending.missing&BoardIssue)==0&&(pending.mismatch&BoardIssue)==0,"non-U is recognized explicitly");
    check(!pending.transport.board_confirmed&&!pending.transport.hardware_approved,"model alone cannot authorize hardware");
    for(auto board:{Board::Other,static_cast<Board>(255)}) {
        const auto p=prepare_profile(fixture(board),1);
        check(p.readiness==Readiness::Mismatch&&(p.mismatch&BoardIssue)!=0,"unsupported model rejected");
        check(!p.transport.hardware_approved,"unsupported model never authorized");
    }
    for(unsigned field=0;field<11;++field) {
        auto o=fixture(Board::WaveshareCan);std::uint16_t selected=1;
        switch(field) {
            case 0:selected=0;break;case 1:o.board=Board::Unknown;break;
            case 2:o.protocol=Protocol::Unknown;break;case 3:o.hardware_revision={};break;
            case 4:o.firmware_version={};break;case 5:o.can_id=0;break;
            case 6:o.bitrate=0;break;case 7:o.tx_gpio=-1;break;
            case 8:o.rx_gpio=-1;break;case 9:o.wiring=Check::Unknown;break;
            default:o.power_on_motion_excluded=Check::Unknown;
        }
        const auto p=prepare_profile(o,selected);
        check(p.readiness!=Readiness::ReadyForReview&&p.missing!=0,"missing real observations remain blocking");
        check(!p.transport.hardware_approved,"missing observation never authorized");
    }
    for(unsigned field=0;field<10;++field) {
        auto o=fixture(Board::WaveshareCan);std::uint16_t selected=1;
        switch(field) {
            case 0:selected=5;break;case 1:o.protocol=Protocol::Rs485;break;
            case 2:o.hardware_revision="bad\nrecord";break;case 3:o.firmware_version="bad\trecord";break;
            case 4:o.can_id=2;break;case 5:o.bitrate=250000;break;
            case 6:o.tx_gpio=17;break;case 7:o.rx_gpio=15;break;
            case 8:o.wiring=Check::Fail;break;default:o.power_on_motion_excluded=Check::Fail;
        }
        const auto p=prepare_profile(o,selected);
        check(p.readiness==Readiness::Mismatch&&p.mismatch!=0,"wrong real observations remain rejected");
        check(!p.transport.hardware_approved,"mismatch never authorized");
    }
    std::printf("{\"state\":\"HOST_PASS\",\"assertions\":%u,\"actual_hardware_IO\":0}\n",assertions);
}
