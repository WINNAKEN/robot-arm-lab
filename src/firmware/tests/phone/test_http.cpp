#include "phone_http.hpp"
#include "esp_timer.h"
#include "lwip/sockets.h"
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <vector>
std::uint64_t stub_time=0;unsigned assertions=0,dispatches=0,socket_timeouts=0;std::vector<std::unique_ptr<StubServer>> servers;int next_fd=10;
#define CHECK(x) do{++assertions;if(!(x)){std::fprintf(stderr,"HTTP FAIL line %d: %s\n",__LINE__,#x);std::exit(1);}}while(false)
std::int64_t esp_timer_get_time(){return static_cast<std::int64_t>(stub_time*1000);}
esp_err_t httpd_start(httpd_handle_t* out,const httpd_config_t* config){auto s=std::make_unique<StubServer>();s->config=*config;*out=s.get();servers.push_back(std::move(s));return ESP_OK;}
esp_err_t httpd_stop(httpd_handle_t){return ESP_OK;}
esp_err_t httpd_register_uri_handler(httpd_handle_t h,const httpd_uri_t* r){h->routes.push_back(*r);return ESP_OK;}
esp_err_t httpd_sess_set_recv_override(httpd_handle_t h,int fd,httpd_recv_func_t f){h->connections[fd].receive=f;return ESP_OK;}
void httpd_sess_set_transport_ctx(httpd_handle_t h,int fd,void* ctx,httpd_free_ctx_fn_t f){h->connections[fd].ctx=ctx;h->connections[fd].free_ctx=f;}
void* httpd_sess_get_transport_ctx(httpd_handle_t h,int fd){return h->connections[fd].ctx;}
esp_err_t httpd_sess_trigger_close(httpd_handle_t h,int fd){h->connections[fd].closed=true;return ESP_OK;}
int httpd_req_to_sockfd(httpd_req_t* r){return r->fd;}
size_t httpd_req_get_hdr_value_len(httpd_req_t* r,const char* name){return r->headers[name].size();}
esp_err_t httpd_req_get_hdr_value_str(httpd_req_t* r,const char* name,char* out,size_t cap){auto s=r->headers[name];if(s.size()>=cap)return ESP_FAIL;std::memcpy(out,s.c_str(),s.size()+1);return ESP_OK;}
esp_err_t httpd_resp_set_hdr(httpd_req_t* r,const char* name,const char* value){r->response_headers[name]=value;return ESP_OK;}
esp_err_t httpd_resp_set_status(httpd_req_t* r,const char* s){r->status=s;return ESP_OK;}
esp_err_t httpd_resp_set_type(httpd_req_t* r,const char* s){r->type=s;return ESP_OK;}
esp_err_t httpd_resp_send(httpd_req_t* r,const char* text,ssize_t size){r->response.assign(text,size<0?std::strlen(text):static_cast<size_t>(size));return ESP_OK;}
int httpd_req_recv(httpd_req_t* r,char* text,size_t size){if(r->on_body){auto fn=std::move(r->on_body);r->on_body={};fn();}if(r->body_reads<r->body_delays.size())stub_time+=r->body_delays[r->body_reads++];const auto n=std::min({size,r->body.size()-r->body_at,size_t{8}});std::memcpy(text,r->body.data()+r->body_at,n);r->body_at+=n;return static_cast<int>(n);}
int recv(int fd,char* text,size_t size,int){for(auto& server:servers){auto found=server->connections.find(fd);if(found==server->connections.end())continue;auto& c=found->second;if(c.next>=c.fragments.size())return 0;if(c.next<c.receive_delays.size())stub_time+=c.receive_delays[c.next];auto& fragment=c.fragments[c.next++];CHECK(fragment.size()<=size);std::memcpy(text,fragment.data(),fragment.size());return static_cast<int>(fragment.size());}return -1;}
int setsockopt(int,int,int option,const void* value,size_t size){CHECK(option==SO_RCVTIMEO||option==SO_SNDTIMEO);CHECK(size==sizeof(timeval));const auto& timeout=*static_cast<const timeval*>(value);CHECK(timeout.tv_sec==0&&timeout.tv_usec==100000);++socket_timeouts;return 0;}
namespace phone=robot_phone;
struct TestBridge:phone::Bridge{unsigned normal=0,stop=0,status=0;phone::Wire last{};bool mismatch=false;std::function<void()> hold;phone::Time now()const noexcept override{return stub_time;}bool exchange(const phone::Envelope& e,phone::Result& r)noexcept override{last=e.wire;if(e.listener==phone::Listener::Stop)++stop;else ++normal;if(e.listener==phone::Listener::Normal&&hold){auto fn=std::move(hold);hold={};fn();}r.job=mismatch?e.job+1:e.job;r.accepted_at=stub_time;if(e.wire.op==phone::Op::HandoffResult){r.transfer_id=9007199254740993ULL;r.transfer_state=phone::TransferState::Granted;r.transfer_generation=3;r.pending_until=700;r.grant_at=435;r.lease_until=1235;r.sequence_floor=1;r.lease=9;}return true;}phone::Snapshot copied_snapshot()noexcept override{phone::Snapshot s;s.boot=9007199254740993ULL;s.generation=2;s.at=stub_time;s.axis_count=2;return s;}bool status_authorized(const phone::Secret& c,phone::Time)noexcept override{++status;return c[0]=='b';}};
struct Request{
 httpd_req_t r;phone::HttpServer& server;int fd;
 Request(phone::HttpServer& s,const char* uri,httpd_method_t method=HTTP_POST,std::string body="v1|11|1|1|1|stop|0|0|1|0|0"):server(s),fd(next_fd++){r.handle=s.handle;r.uri=uri;r.method=method;r.fd=fd;r.body=std::move(body);r.content_len=r.body.size();r.headers={{"Host",s.listener==phone::Listener::Normal?"192.168.4.1":"192.168.4.1:8081"},{"Origin","http://192.168.4.1"},{"Content-Type","text/plain"},{"X-Session-Credential",std::string(32,'b')}};CHECK(s.handle->config.open_fn(s.handle,fd)==ESP_OK);}
 ~Request(){auto& c=server.handle->connections[fd];if(c.ctx&&c.free_ctx)c.free_ctx(c.ctx);c.ctx=nullptr;}
 std::string raw()const{std::string raw=(r.method==HTTP_GET?"GET ":r.method==HTTP_OPTIONS?"OPTIONS ":"POST ");raw+=r.uri;raw+=" HTTP/1.1\r\n";for(const auto& header:r.headers)raw+=header.first+": "+header.second+"\r\n";raw+="Content-Length: "+std::to_string(r.content_len)+"\r\n\r\n";return raw;}
 bool receive(std::string input="",unsigned split=7){if(input.empty())input=raw();auto& c=server.handle->connections[fd];for(size_t i=0;i<input.size();i+=split)c.fragments.push_back(input.substr(i,split));char bytes[1024];while(c.next<c.fragments.size())if(c.receive(server.handle,fd,bytes,sizeof(bytes),0)<=0)return false;return true;}
 void dispatch(){for(const auto& route:server.handle->routes)if(route.method==r.method&&std::strcmp(route.uri,r.uri)==0){r.user_ctx=route.user_ctx;++dispatches;route.handler(&r);return;}CHECK(false);}
 void run(){CHECK(receive());dispatch();CHECK(server.handle->connections[fd].closed);CHECK(r.response_headers["Connection"]=="close");}
};
int main(){
 TestBridge bridge;phone::HttpServer normal{&bridge,phone::Listener::Normal},stop{&bridge,phone::Listener::Stop};CHECK(phone::start_http(normal)==ESP_OK&&phone::start_http(stop)==ESP_OK);CHECK(normal.handle!=stop.handle);CHECK(normal.handle->config.server_port==80&&stop.handle->config.server_port==8081);CHECK(normal.handle->config.ctrl_port!=stop.handle->config.ctrl_port);CHECK(normal.handle->config.max_open_sockets==5&&stop.handle->config.max_open_sockets==4);CHECK(normal.handle->config.task_priority==3&&stop.handle->config.task_priority==3);
 {Request request(normal,"/api/command",HTTP_POST,"v1|11|1|1|1|arm|0|0|1|0|0");request.run();CHECK(bridge.normal==1&&request.r.response.find("\"queued\":true")!=std::string::npos);}
 {Request request(stop,"/api/stop");request.run();CHECK(bridge.stop==1&&request.r.response_headers["Access-Control-Allow-Origin"]=="http://192.168.4.1");}
 for(bool swapped:{false,true}){Request request(swapped?stop:normal,swapped?"/api/stop":"/api/command");request.r.headers["Host"]=swapped?"192.168.4.1":"192.168.4.1:8081";const auto total=bridge.normal+bridge.stop;request.run();CHECK(request.r.response.find("\"wire_error\":3")!=std::string::npos&&bridge.normal+bridge.stop==total);}
 {Request request(stop,"/api/stop",HTTP_POST,"v1|11|1|1|1|move|0|0|1|0|0");const auto total=bridge.stop;request.run();CHECK(bridge.stop==total);}
 {Request request(normal,"/api/command");const auto total=bridge.normal;request.run();CHECK(bridge.normal==total);}
 {Request request(normal,"/api/status",HTTP_GET,"");request.r.headers.erase("Origin");request.run();CHECK(request.r.status=="200 OK"&&request.r.response.find("\"boot\":\"9007199254740993\"")!=std::string::npos);}
 {Request request(normal,"/api/status",HTTP_GET,"");request.r.headers["Origin"]="http://evil";request.run();CHECK(request.r.status=="400 Bad Request");}
 {Request request(stop,"/api/stop",HTTP_OPTIONS,"");request.r.headers["Access-Control-Request-Method"]="POST";request.r.headers["Access-Control-Request-Headers"]="content-type,x-session-credential";request.r.headers.erase("X-Session-Credential");request.run();CHECK(request.r.status=="204 No Content");}
 {Request request(stop,"/api/stop",HTTP_OPTIONS,"");request.r.headers["Access-Control-Request-Method"]="POST";request.r.headers["Access-Control-Request-Headers"]="x-session-credential";request.r.headers.erase("X-Session-Credential");request.run();CHECK(request.r.status=="204 No Content");}
 for(const char* origin:{"","null","http://192.168.4.1:8081","http://evil"}){Request request(stop,"/api/stop");request.r.headers["Origin"]=origin;request.run();CHECK(request.r.status=="400 Bad Request");}
 {Request request(normal,"/",HTTP_GET,"");request.run();CHECK(request.r.response.find("하드웨어 미승인")!=std::string::npos);}
 {Request request(normal,"/api/command",HTTP_POST,"v1|11|1|1|1|arm|0|0|1|0|0");request.run();const auto before=bridge.normal;request.dispatch();CHECK(request.r.status=="408 Request Timeout"&&bridge.normal==before);}
 for(const char* duplicate:{"host: evil\r\n","Origin: http://evil\r\n","X-Session-Credential: x\r\n","Content-Length: 25\r\n","Content-Type: text/plain\r\n","Transfer-Encoding: chunked\r\n"}){Request request(stop,"/api/stop");auto raw=request.raw();raw.insert(raw.size()-2,duplicate);const auto before=dispatches;CHECK(!request.receive(raw,1));CHECK(dispatches==before);}
 {Request ordinary(normal,"/api/command",HTTP_POST,"v1|11|1|1|1|arm|0|0|1|0|0");const auto before=bridge.stop;ordinary.r.on_body=[&](){Request observer(stop,"/api/stop");observer.run();CHECK(bridge.stop==before+1);};ordinary.run();CHECK(bridge.stop==before+1);}
 {Request ordinary(normal,"/api/command",HTTP_POST,"v1|11|1|1|1|arm|0|0|1|0|0");const auto before=bridge.stop;bridge.hold=[&](){Request observer(stop,"/api/stop");observer.run();CHECK(bridge.stop==before+1);};ordinary.run();CHECK(bridge.stop==before+1);}
 {Request request(normal,"/api/command",HTTP_POST,"v1|11|1|1|1|arm|0|0|1|0|0");CHECK(request.receive());request.r.body_delays={100,100,50};const auto before=bridge.normal;request.dispatch();CHECK(request.r.status=="408 Request Timeout"&&bridge.normal==before);}
 {Request request(stop,"/api/stop");auto& c=stop.handle->connections[request.fd];c.fragments={"POST /api/stop HTTP/1.1\r\n","Host: 192.168.4.1:8081\r\n\r\n"};c.receive_delays={125,125};char bytes[1024];CHECK(c.receive(stop.handle,request.fd,bytes,sizeof(bytes),0)>0);CHECK(c.receive(stop.handle,request.fd,bytes,sizeof(bytes),0)==HTTPD_SOCK_ERR_TIMEOUT);}
 {Request request(normal,"/api/command",HTTP_POST,"v1|11|1|1|1|arm|0|0|1|0|0");bridge.mismatch=true;request.run();CHECK(request.r.status=="504 Gateway Timeout");bridge.mismatch=false;Request next(normal,"/api/command",HTTP_POST,"v1|11|1|2|2|arm|0|0|1|0|0");next.run();CHECK(next.r.status=="200 OK");}
 {Request request(normal,"/api/command",HTTP_POST,"v2|11|1|1|1|joint-step|5|6|2|2|rad|-0.125");const auto before=bridge.normal;request.run();CHECK(bridge.normal==before+1);CHECK(bridge.last.op==phone::Op::JointStep&&bridge.last.axis==2&&bridge.last.joint==2&&bridge.last.radians&&bridge.last.angle==-0.125);}
 {Request request(stop,"/api/stop",HTTP_POST,"v2|11|1|1|1|joint-step|5|6|2|2|deg|1.25");const auto before=bridge.stop;request.run();CHECK(bridge.stop==before);}
 {Request request(normal,"/api/command",HTTP_POST,"v2|11|1|1|1|joint-step|5|6|1|1|deg|1e2");const auto before=bridge.normal;request.run();CHECK(bridge.normal==before);}
 {Request request(normal,"/api/status",HTTP_GET,"");request.run();CHECK(request.r.response.find("\"angle_available\":false")!=std::string::npos&&request.r.response.find("\"angle_joint\":0")!=std::string::npos);}
 {Request request(normal,"/api/command",HTTP_POST,"v1|11|3|1|1|handoff-result|0|7|1|0|0");request.run();CHECK(bridge.last.op==phone::Op::HandoffResult);CHECK(request.r.response.find("\"transfer_id\":\"9007199254740993\"")!=std::string::npos);CHECK(request.r.response.find("\"lease_until\":\"1235\"")!=std::string::npos);CHECK(request.r.response.find("\"sequence_floor\":\"1\"")!=std::string::npos);}
 CHECK(socket_timeouts>=40);std::printf("PASS actual production phone_http.cpp stub assertions=%u handler_dispatches=%u timeval_settings=%u network=NOT_RUN\n",assertions,dispatches,socket_timeouts);
}
