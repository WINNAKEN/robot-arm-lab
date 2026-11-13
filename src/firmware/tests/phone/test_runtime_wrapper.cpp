#define ROBOT_BOOT_FIXTURE_ONLY
#include "../boot/test_boot.cpp"
#include "../../main/phone_runtime.cpp"
#include <functional>
#include <memory>
#include <vector>
std::uint64_t stub_time=0;std::function<void()> wait_tick;unsigned runtime_checks=0;
#define VERIFY(x) do{++runtime_checks;CHECK(x);}while(false)
struct StubQueue{size_t size;std::vector<unsigned char> bytes;bool full{false};};std::vector<std::unique_ptr<StubQueue>> queues;
QueueHandle_t xQueueCreate(unsigned capacity,size_t size){VERIFY(capacity==1);auto q=std::make_unique<StubQueue>();q->size=size;q->bytes.resize(size);auto* out=q.get();queues.push_back(std::move(q));return out;}
BaseType_t xQueueSend(QueueHandle_t q,const void* data,TickType_t timeout){VERIFY(timeout==0);if(q->full)return 0;std::memcpy(q->bytes.data(),data,q->size);q->full=true;return pdTRUE;}
BaseType_t xQueueOverwrite(QueueHandle_t q,const void* data){std::memcpy(q->bytes.data(),data,q->size);q->full=true;return pdTRUE;}
BaseType_t xQueueReceive(QueueHandle_t q,void* data,TickType_t timeout){for(unsigned n=0;!q->full&&n<timeout;++n){if(wait_tick)wait_tick();else ++stub_time;}if(!q->full)return 0;std::memcpy(data,q->bytes.data(),q->size);q->full=false;return pdTRUE;}
SemaphoreHandle_t xSemaphoreCreateMutex(){static int lock=0;return &lock;}BaseType_t xSemaphoreTake(SemaphoreHandle_t,TickType_t){return pdTRUE;}BaseType_t xSemaphoreGive(SemaphoreHandle_t){return pdTRUE;}
TickType_t xTaskGetTickCount(){return static_cast<TickType_t>(stub_time);}void vTaskDelayUntil(TickType_t*,TickType_t){}
unsigned created_tasks=0;BaseType_t xTaskCreate(void(*fn)(void*),const char*,unsigned,void*,unsigned priority,void*){VERIFY(fn!=nullptr&&priority==10);++created_tasks;return pdPASS;}
std::int64_t esp_timer_get_time(){return static_cast<std::int64_t>(stub_time*1000);}
bool entropy=false,rf=false;unsigned rng_calls=0,entropy_enable=0,entropy_disable=0,wifi_calls=0,http_calls=0;
void bootloader_random_enable(){VERIFY(!rf&&!entropy);entropy=true;++entropy_enable;}void bootloader_random_disable(){VERIFY(entropy&&!rf);entropy=false;++entropy_disable;}
void esp_fill_random(void* out,size_t size){VERIFY(entropy||rf);++rng_calls;static unsigned draw=1;auto* bytes=static_cast<unsigned char*>(out);for(size_t i=0;i<size;++i)bytes[i]=static_cast<unsigned char>((draw+i*13)%251+1);++draw;}
esp_err_t nvs_flash_init(){VERIFY(!entropy);return ESP_OK;}esp_err_t esp_event_loop_create_default(){return ESP_OK;}esp_err_t esp_netif_init(){return ESP_OK;}void* esp_netif_create_default_wifi_ap(){static int ap=0;return &ap;}
esp_err_t esp_wifi_init(const wifi_init_config_t*){VERIFY(!entropy);++wifi_calls;return ESP_OK;}esp_err_t esp_wifi_set_mode(int mode){VERIFY(mode==WIFI_MODE_AP);return ESP_OK;}esp_err_t esp_wifi_set_config(int which,const wifi_config_t* config){VERIFY(which==WIFI_IF_AP&&config->ap.authmode==WIFI_AUTH_WPA2_PSK&&std::strlen(reinterpret_cast<const char*>(config->ap.password))==32);return ESP_OK;}esp_err_t esp_wifi_start(){VERIFY(!entropy);rf=true;return ESP_OK;}
namespace robot_phone{esp_err_t start_http(HttpServer&)noexcept{++http_calls;return ESP_OK;}}
esp_err_t httpd_stop(httpd_handle_t){return ESP_OK;}
namespace phone=robot_phone;
phone::Secret fixture_secret(char c){phone::Secret s{};for(unsigned i=0;i<32;++i)s[i]=c;return s;}
phone::Seed fixture_seed(){phone::Seed s;s.boot=11;s.pairing=fixture_secret('a');s.credentials={fixture_secret('b'),fixture_secret('c')};s.principals={101,202};return s;}
struct PumpFixture {
 phone::Runtime runtime{fixture_seed(),boot_profile()};std::array<Time,2> pending{};Time job=0,seq=0,lease=0,renewed=0;bool renewing=false;phone::Secret credential{};
 PumpFixture(){VERIFY(runtime.bridge.initialize());runtime.owner.begin();runtime.bridge.publish(runtime.owner.snapshot());stub_time=runtime.port.now;wait_tick=[this](){++runtime.port.now;stub_time=runtime.port.now;phone::pump(runtime,pending);};phone::Envelope e;e.pairing=true;e.credential=fixture_seed().pairing;auto r=send(e);VERIFY(r.paired);credential=r.credential;}
 ~PumpFixture(){wait_tick={};}
 phone::Result send(phone::Envelope e){e.job=++job;e.enqueued_at=runtime.port.now;phone::Result result;VERIFY(runtime.bridge.exchange(e,result));VERIFY(result.job==e.job);return result;}
 phone::Envelope envelope(phone::Op op){phone::Envelope e;e.credential=credential;e.listener=op==phone::Op::Stop?phone::Listener::Stop:phone::Listener::Normal;e.wire={11,runtime.owner.snapshot().generation,++seq,seq,lease,0,op,1,0,true};return e;}
 phone::Result command(phone::Op op){auto r=send(envelope(op));if(r.lease)lease=r.lease;return r;}
 void accepted(phone::Op op){const auto r=command(op);if(r.error!=phone::Error::None)std::fprintf(stderr,"PUMP op=%u wire=%u core=%u at=%llu\n",static_cast<unsigned>(op),static_cast<unsigned>(r.error),r.core_error,static_cast<unsigned long long>(runtime.port.now));VERIFY(r.error==phone::Error::None);}
 void step(){wait_tick();if(renewing&&runtime.port.now-renewed>=200){renewed=runtime.port.now;accepted(phone::Op::MaintenanceRenew);}}
 void delay(unsigned count){for(unsigned i=0;i<count;++i)step();}
 void state(robot_boot::State state){for(unsigned i=0;i<3000&&runtime.owner.snapshot().core_state!=static_cast<unsigned>(state);++i)step();VERIFY(runtime.owner.snapshot().core_state==static_cast<unsigned>(state));}
 void granted(){state(robot_boot::State::NeedsMaintenance);accepted(phone::Op::Maintenance);renewing=true;renewed=runtime.port.now;accepted(phone::Op::Unloaded);accepted(phone::Op::DisableAll);state(robot_boot::State::ReadyDisabled);accepted(phone::Op::FinishMaintenance);lease=0;accepted(phone::Op::Drive);accepted(phone::Op::EnableSelected);state(robot_boot::State::Granted);delay(600);renewing=false;}
};
int main(){
 {PumpFixture f;f.granted();const auto before=f.runtime.port.now;f.accepted(phone::Op::Handoff);VERIFY(f.runtime.owner.snapshot().phase==phone::Phase::RunChecking);VERIFY(f.pending[0]==0);VERIFY(f.runtime.port.now-before<50);std::printf("RUNTIME_PUMP actual deferred Handoff received job after %llu ms across ticks\n",static_cast<unsigned long long>(f.runtime.port.now-before));}
 {PumpFixture f;f.granted();auto handoff=f.envelope(phone::Op::Handoff);handoff.job=++f.job;handoff.enqueued_at=f.runtime.port.now;VERIFY(xQueueSend(f.runtime.bridge.commands[0],&handoff,0)==pdTRUE);wait_tick();const bool waiting=f.pending[0]!=0;if(waiting){auto stop=f.envelope(phone::Op::Stop);stop.job=++f.job;stop.enqueued_at=f.runtime.port.now;VERIFY(xQueueSend(f.runtime.bridge.commands[1],&stop,0)==pdTRUE);wait_tick();phone::Result result;VERIFY(xQueueReceive(f.runtime.bridge.results[0],&result,0)==pdTRUE&&result.job==handoff.job&&result.error==phone::Error::Denied);VERIFY(f.pending[0]==0);std::printf("RUNTIME_PUMP pending Handoff cancelled by independent Stop\n");}else VERIFY(f.runtime.owner.snapshot().phase==phone::Phase::RunChecking);}
 {PumpFixture f;phone::Result late;late.job=999;VERIFY(xQueueOverwrite(f.runtime.bridge.results[0],&late)==pdTRUE);auto result=f.command(phone::Op::Maintenance);VERIFY(result.job!=999);VERIFY(f.runtime.bridge.status_authorized(f.credential,1000));VERIFY(!f.runtime.bridge.status_authorized(f.credential,1199));VERIFY(f.runtime.bridge.status_authorized(f.credential,1200));}
 {PumpFixture f;f.granted();f.runtime.port.auto_reply=false;const auto before=f.runtime.port.now;auto result=f.command(phone::Op::Handoff);VERIFY(result.error==phone::Error::Busy);VERIFY(f.runtime.port.now-before==49);VERIFY(f.runtime.owner.snapshot().phase==phone::Phase::Boot&&f.pending[0]==0);std::printf("RUNTIME_PUMP no readiness immutable49ms deadline Busy no mint\n");}
 {PumpFixture f;auto old=f.envelope(phone::Op::Maintenance);old.job=++f.job;old.enqueued_at=f.runtime.port.now;wait_tick=[&](){++f.runtime.port.now;stub_time=f.runtime.port.now;};phone::Result result;VERIFY(!f.runtime.bridge.exchange(old,result));VERIFY(f.runtime.port.now-old.enqueued_at==50);phone::pump(f.runtime,f.pending);wait_tick=[&](){++f.runtime.port.now;stub_time=f.runtime.port.now;phone::pump(f.runtime,f.pending);};const auto next=f.command(phone::Op::Maintenance);VERIFY(next.job!=old.job);std::printf("RUNTIME_PUMP timeout50ms old Stale result drained never reused\n");}
 phone::start_prepared_runtime();VERIFY(entropy_enable==1&&entropy_disable==1&&rng_calls>=7&&wifi_calls==1&&http_calls==2&&created_tasks==1);VERIFY(!phone::runtime->profile.hardware_identity_approved&&!phone::runtime->profile.run.normal_approved);VERIFY(phone::runtime->port.resets==0&&phone::runtime->port.submits==0);
 std::printf("PASS actual production phone_runtime.cpp pump/startup stub checks=%u assertions=%u hardware/network=NOT_RUN\n",runtime_checks,assertions);
}
