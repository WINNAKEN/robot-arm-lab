#include "phone_http.hpp"
#include "robot_twai/idf_twai_port.hpp"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "bootloader_random.h"
#include <cstdio>
#include <cstring>
#include <limits>
namespace robot_phone {
namespace {
constexpr bool hardware_approved=false;
static_assert(!hardware_approved,"prepared runtime never approves hardware");
void random_secret(Secret& out)noexcept{std::array<unsigned char,16> raw{};
esp_fill_random(raw.data(),raw.size());
constexpr char hex[]="0123456789abcdef";
for(unsigned i=0;i<raw.size();++i){out[2*i]=hex[raw[i]>>4];
out[2*i+1]=hex[raw[i]&15];
}
out[32]='\0';
}
Time random_id()noexcept{Time value=0;
do{esp_fill_random(&value,sizeof(value));
}
while(value==0||value==std::numeric_limits<Time>::max());
return value;
}
Seed make_seed()noexcept{Seed s;
s.boot=random_id();
random_secret(s.pairing);
for(unsigned i=0;i<2;++i){do{random_secret(s.credentials[i]);
}
while(equal_secret({s.credentials[i].data(),32},{s.pairing.data(),32})||(i==1&&equal_secret({s.credentials[0].data(),32},{s.credentials[1].data(),32})));
do{s.principals[i]=random_id();
}
while(i==1&&s.principals[1]==s.principals[0]);
}
return s;
}
robot_boot::Profile prepared_profile(Time boot)noexcept{robot_boot::Profile p;
p.run.gate.boot=boot;
p.run.gate.profile=1;
p.run.selected_axis=1;
p.run.enable_policy=robot_run::EnablePolicy::SingleSelected;
p.hardware_identity_approved=hardware_approved;
p.run.normal_approved=hardware_approved;
p.run.post_maintenance_enable_seed_approved=hardware_approved;
p.run.stop.response_bounds_approved=hardware_approved;
p.run.stop.position_tolerance_approved=hardware_approved;
p.run.stop.heartbeat_1000_readback_confirmed=hardware_approved;
return p;
}
class RuntimeBridge final:public Bridge {
public:
 explicit RuntimeBridge(const Seed& s)noexcept:seed(s){}
 bool initialize()noexcept{lock=xSemaphoreCreateMutex();
 if(!lock)return false;
 for(unsigned i=0;i<2;++i){commands[i]=xQueueCreate(1,sizeof(Envelope));
 results[i]=xQueueCreate(1,sizeof(Result));
 if(!commands[i]||!results[i])return false;
 }
 return true;
 }
 Time now()const noexcept override{return static_cast<Time>(esp_timer_get_time()/1000);
 }
 bool exchange(const Envelope& e,Result& out)noexcept override{const unsigned i=e.listener==Listener::Stop?1:0;
 if(xQueueSend(commands[i],&e,0)!=pdTRUE)return false;
 const auto started=now();
 for(;;){const auto n=now();
 if(n<started||n-started>=50)return false;
 Result r;
 if(xQueueReceive(results[i],&r,pdMS_TO_TICKS(50-(n-started)))!=pdTRUE)return false;
 if(r.job==e.job){out=r;
 return true;
 }/* Drain a late earlier answer without reusing its identity. */}
 }
 Snapshot copied_snapshot()noexcept override{Snapshot copy;
 if(xSemaphoreTake(lock,pdMS_TO_TICKS(2))==pdTRUE){copy=snapshot;
 xSemaphoreGive(lock);
 }
 return copy;
 }
 bool status_authorized(const Secret& c,Time at)noexcept override{bool accepted=false;
 if(xSemaphoreTake(lock,pdMS_TO_TICKS(2))!=pdTRUE)return false;
 for(unsigned i=0;i<2;++i)if((snapshot.paired_mask&(1u<<i))!=0&&equal_secret({c.data(),32},{seed.credentials[i].data(),32})){if(!status_seen[i]||(at>=status_last[i]&&at-status_last[i]>=200)){accepted=true;
 status_seen[i]=true;
 status_last[i]=at;
 }
 break;
 }
 xSemaphoreGive(lock);
 return accepted;
 }
 void publish(const Snapshot& value)noexcept{if(xSemaphoreTake(lock,0)==pdTRUE){snapshot=value;
 xSemaphoreGive(lock);
 }
 }
 Seed seed;
 QueueHandle_t commands[2]{},results[2]{};
 SemaphoreHandle_t lock{nullptr};
 Snapshot snapshot{};
 Time status_last[2]{};
 bool status_seen[2]{};
};
struct Runtime {robot_can::IdfTwaiPort port{};
Seed seed;
robot_boot::Profile profile;
Owner owner;
RuntimeBridge bridge;
HttpServer normal{},stop{};
Runtime(const Seed& s,const robot_boot::Profile& p):seed(s),profile(p),owner(port,profile,seed),bridge(seed){normal.bridge=stop.bridge=&bridge;
stop.listener=Listener::Stop;
}
};
Runtime* runtime=nullptr;
void pump(Runtime& r,std::array<Time,2>& pending_jobs)noexcept{for(int i=1;i>=0;--i){Envelope e;
if(xQueueReceive(r.bridge.commands[i],&e,0)==pdTRUE){if(pending_jobs[i]!=0||!r.owner.enqueue(e)){Result result;
result.job=e.job;
result.error=Error::Busy;
xQueueOverwrite(r.bridge.results[i],&result);
}
else pending_jobs[i]=e.job;
}
}
r.owner.tick();
for(unsigned i=0;i<2;++i)if(pending_jobs[i]!=0){Result result;
if(r.owner.take_result(i?Listener::Stop:Listener::Normal,pending_jobs[i],result)){xQueueOverwrite(r.bridge.results[i],&result);
pending_jobs[i]=0;
}
}
r.bridge.publish(r.owner.snapshot());
}
void control_task(void* context){auto& r=*static_cast<Runtime*>(context);
r.owner.begin();
r.bridge.publish(r.owner.snapshot());
std::array<Time,2> pending_jobs{};
TickType_t wake=xTaskGetTickCount();
for(;;){pump(r,pending_jobs);
vTaskDelayUntil(&wake,pdMS_TO_TICKS(1));
}
}
bool wifi_start(const Secret& password)noexcept{
 if(nvs_flash_init()!=ESP_OK||esp_netif_init()!=ESP_OK||esp_event_loop_create_default()!=ESP_OK)return false;
 if(!esp_netif_create_default_wifi_ap())return false;
 wifi_init_config_t config=WIFI_INIT_CONFIG_DEFAULT();
 if(esp_wifi_init(&config)!=ESP_OK)return false;
 wifi_config_t ap{};
 constexpr char ssid[]="robot-arm-preparation";
 std::memcpy(ap.ap.ssid,ssid,sizeof(ssid));
 ap.ap.ssid_len=sizeof(ssid)-1;
 std::memcpy(ap.ap.password,password.data(),32);
 ap.ap.channel=1;
 ap.ap.max_connection=2;
 ap.ap.authmode=WIFI_AUTH_WPA2_PSK;
 ap.ap.pmf_cfg.required=true;
 return esp_wifi_set_mode(WIFI_MODE_AP)==ESP_OK&&esp_wifi_set_config(WIFI_IF_AP,&ap)==ESP_OK&&esp_wifi_start()==ESP_OK;
}
}
void start_prepared_runtime()noexcept{
 // Compile/link reachable composition. This entry is never executed on host.
 // RF/ADC are still untouched here. Enable the documented early entropy source
 // for every credential draw, then disable it before any Wi-Fi initialization.
 bootloader_random_enable();
 const auto seed=make_seed();
 Secret password;
 random_secret(password);
 bootloader_random_disable();
 static Runtime instance(seed,prepared_profile(seed.boot));
 runtime=&instance;
 if(!runtime->bridge.initialize())return;
 // Deliberate once-per-boot physical serial onboarding, never routine/status logs.
 std::printf("PREPARED HARDWARE UNAPPROVED\nSoftAP=robot-arm-preparation WPA2=%s\nPairing=%s\n",password.data(),seed.pairing.data());
 if(xTaskCreate(control_task,"robot_owner",12288,runtime,10,nullptr)!=pdPASS)return;
 if(!wifi_start(password))return;
 if(start_http(runtime->normal)!=ESP_OK)return;
 if(start_http(runtime->stop)!=ESP_OK){httpd_stop(runtime->normal.handle);
 runtime->normal.handle=nullptr;
 }
}
} // namespace robot_phone
