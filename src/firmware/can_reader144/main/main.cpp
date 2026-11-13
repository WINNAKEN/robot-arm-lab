#include "flow.hpp"
#include "driver/twai.h"
#include "driver/usb_serial_jtag.h"
#include "esp_app_desc.h"
#include "esp_idf_version.h"
#include "esp_timer.h"
#include "esp_random.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <cstdio>
#include <cstring>
using namespace reader144;
#if ESP_IDF_VERSION != ESP_IDF_VERSION_VAL(5,5,6)
#error "Reader144 requires existing ESP-IDF5.5.6"
#endif
static_assert(CONFIG_FREERTOS_HZ==1000,"Reader144 requires millisecond RTOS ticks");
namespace {
bool fault=false;
uint32_t tx_attempts=0;
bool installed=false;
uint32_t boot_a=0,boot_b=0,info_sequence=0;
void output(const char* s) {
    const size_t n=std::strlen(s);
    usb_serial_jtag_write_bytes(s,n,pdMS_TO_TICKS(100));
}
void info() {
    const auto* app=esp_app_get_description();
    char s[768],elf[65];
    for(unsigned i=0;i<32;++i) std::snprintf(elf+i*2,3,"%02x",app->app_elf_sha256[i]);
    std::snprintf(s,sizeof(s),"{\"app\":\"%s\",\"version\":\"%s\",\"idf\":\"%s\",\"elf_sha256\":\"%s\",\"state\":\"%s\",\"CAN_started\":%s,\"driver_installed\":%s,\"tx_attempts\":%lu,\"allowed\":[\"31\",\"32\",\"F1\",\"3A\"],\"motor_power_control\":false,\"boot_id\":\"%08lx%08lx\",\"uptime_ms\":%llu,\"info_seq\":%lu}\n",
        app->project_name,app->version,app->idf_ver,elf,fault?"FAULT_LATCHED":"IDLE",
        fault?"null":"false",fault?"null":(installed?"true":"false"),static_cast<unsigned long>(tx_attempts),
        static_cast<unsigned long>(boot_a),static_cast<unsigned long>(boot_b),
        static_cast<unsigned long long>(esp_timer_get_time()/1000),static_cast<unsigned long>(++info_sequence));
    output(s);
}
struct Backend {
    bool install(uint32_t rate) {
        twai_general_config_t g=TWAI_GENERAL_CONFIG_DEFAULT(GPIO_NUM_15,GPIO_NUM_16,TWAI_MODE_NORMAL);
        g.tx_queue_len=0;g.rx_queue_len=8;
        twai_timing_config_t t=TWAI_TIMING_CONFIG_500KBITS();
        if(rate==125000) t=TWAI_TIMING_CONFIG_125KBITS();
        else if(rate==250000) t=TWAI_TIMING_CONFIG_250KBITS();
        else if(rate==1000000) t=TWAI_TIMING_CONFIG_1MBITS();
        const twai_filter_config_t f=TWAI_FILTER_CONFIG_ACCEPT_ALL();
        const auto e=twai_driver_install(&g,&t,&f);
        if(e==ESP_OK) installed=true;
        return e==ESP_OK;
    }
    bool start() { return twai_start()==ESP_OK; }
    bool transmit(const Frame& f,bool single,uint32_t ms) {
        twai_message_t m{};m.identifier=f.id;m.data_length_code=f.dlc;
        m.flags=single?TWAI_MSG_FLAG_SS:0;
        for(unsigned i=0;i<f.dlc;++i) m.data[i]=f.data[i];
        return twai_transmit(&m,pdMS_TO_TICKS(ms))==ESP_OK;
    }
    Rx receive(Frame& f,uint32_t ms) {
        twai_message_t m{};
        const auto e=twai_receive(&m,pdMS_TO_TICKS(ms));
        if(e==ESP_ERR_TIMEOUT) return Rx::Timeout;
        if(e!=ESP_OK) return Rx::Error;
        f.id=static_cast<uint16_t>(m.identifier);f.ext=m.extd;f.rtr=m.rtr;f.dlc=m.data_length_code;
        for(unsigned i=0;i<8;++i) f.data[i]=m.data[i];
        return Rx::Frame;
    }
    uint64_t now_ms() {return static_cast<uint64_t>(esp_timer_get_time()/1000);}
    bool stop() {return twai_stop()==ESP_OK;}
    bool uninstall() {
        const auto e=twai_driver_uninstall();
        if(e==ESP_OK) installed=false;
        return e==ESP_OK;
    }
};
}
extern "C" void app_main() {
    usb_serial_jtag_driver_config_t cfg=USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();cfg.rx_buffer_size=256;cfg.tx_buffer_size=1024;
    if(usb_serial_jtag_driver_install(&cfg)!=ESP_OK) return;
    boot_a=esp_random();boot_b=esp_random();
    // No CAN driver or CAN GPIO setup is performed during boot/idle.
    info();
    Lines lines;Backend backend;
    while(true) {
        uint8_t bytes[64];
        const int n=usb_serial_jtag_read_bytes(bytes,sizeof(bytes),pdMS_TO_TICKS(50));
        for(int i=0;i<n;++i) {
            const auto event=lines.push(bytes[i]);
            if(event==Lines::None) continue;
            if(event==Lines::Rejected) {output("{\"status\":\"DENIED_LINE\"}\n");continue;}
            const auto q=parse(lines.line());
            if(q.kind==Kind::Info) {info();continue;}
            if(q.kind!=Kind::Read) {output("{\"status\":\"DENIED\"}\n");continue;}
            const auto r=run(backend,q,fault,tx_attempts);
            char s[280];size_t p=static_cast<size_t>(std::snprintf(s,sizeof(s),
                "{\"status\":\"%s\",\"id\":%u,\"op\":%u,\"rejected\":%lu,\"data\":[",
                name(r.status),q.id,q.op,static_cast<unsigned long>(r.rejected)));
            if(r.status==Status::Ok) for(unsigned j=0;j<r.frame.dlc;++j)
                p+=static_cast<size_t>(std::snprintf(s+p,sizeof(s)-p,"%s%u",j?",":"",r.frame.data[j]));
            std::snprintf(s+p,sizeof(s)-p,"]}\n");output(s);
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
}
