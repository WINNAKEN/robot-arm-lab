#include "phone_http.hpp"
#include "esp_timer.h"
#include "lwip/sockets.h"
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <new>
#include <limits>
extern const unsigned char web_index_start[] asm("_binary_index_html_start");
extern const unsigned char web_index_end[] asm("_binary_index_html_end");
extern const unsigned char web_app_start[] asm("_binary_app_js_start");
extern const unsigned char web_app_end[] asm("_binary_app_js_end");
namespace robot_phone {
namespace {
struct Connection {HeaderGuard guard{};
Time started{0};
bool finished{false};
};
Time clock_ms()noexcept{return static_cast<Time>(esp_timer_get_time()/1000);
}
void free_connection(void* ctx){delete static_cast<Connection*>(ctx);
}
bool deadline(Connection& c)noexcept{const auto n=clock_ms();
return n>=c.started&&n-c.started<250&&!c.finished;
}
int guarded_receive(httpd_handle_t hd,int fd,char* bytes,size_t size,int flags){
 auto* c=static_cast<Connection*>(httpd_sess_get_transport_ctx(hd,fd));
 if(!c||!deadline(*c))return HTTPD_SOCK_ERR_TIMEOUT;
 const auto n=recv(fd,bytes,size,flags);
 if(n<=0)return n==0?0:(errno==EAGAIN||errno==EWOULDBLOCK?HTTPD_SOCK_ERR_TIMEOUT:HTTPD_SOCK_ERR_FAIL);
 if(!deadline(*c))return HTTPD_SOCK_ERR_TIMEOUT;
 if(!c->guard.feed(bytes,static_cast<size_t>(n)))return HTTPD_SOCK_ERR_FAIL;
 return static_cast<int>(n);
}
esp_err_t opened(httpd_handle_t hd,int fd){
 timeval timeout{};
 timeout.tv_sec=0;
 timeout.tv_usec=100000;
 if(setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout))!=0||setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout))!=0)return ESP_FAIL;
 auto* c=new(std::nothrow) Connection;
 if(!c)return ESP_ERR_NO_MEM;
 c->started=clock_ms();
 httpd_sess_set_transport_ctx(hd,fd,c,free_connection);
 return httpd_sess_set_recv_override(hd,fd,guarded_receive);
}
bool header(httpd_req_t* r,const char* name,char* out,size_t capacity,bool required=true){const auto size=httpd_req_get_hdr_value_len(r,name);
if(size==0)return !required;
if(size>=capacity)return false;
return httpd_req_get_hdr_value_str(r,name,out,capacity)==ESP_OK;
}
void cors(httpd_req_t* r){httpd_resp_set_hdr(r,"Access-Control-Allow-Origin","http://192.168.4.1");
httpd_resp_set_hdr(r,"Access-Control-Allow-Methods","POST, OPTIONS");
httpd_resp_set_hdr(r,"Access-Control-Allow-Headers","Content-Type, X-Session-Credential");
httpd_resp_set_hdr(r,"Vary","Origin");
}
esp_err_t finish(httpd_req_t* r,const char* body,const char* type="application/json",const char* status="200 OK",size_t length=0){
 auto* c=static_cast<Connection*>(httpd_sess_get_transport_ctx(r->handle,httpd_req_to_sockfd(r)));
 if(c)c->finished=true;
 httpd_resp_set_status(r,status);
 httpd_resp_set_type(r,type);
 httpd_resp_set_hdr(r,"Connection","close");
 httpd_resp_set_hdr(r,"Cache-Control","no-store");
 const auto result=httpd_resp_send(r,body,length?static_cast<ssize_t>(length):HTTPD_RESP_USE_STRLEN);
 httpd_sess_trigger_close(r->handle,httpd_req_to_sockfd(r));
 return result;
}
esp_err_t reject(httpd_req_t* r,Error error,const char* status="400 Bad Request"){char text[80];
std::snprintf(text,sizeof(text),"{\"wire_error\":%u,\"core_error\":0}",static_cast<unsigned>(error));
return finish(r,text,"application/json",status);
}
esp_err_t handler(httpd_req_t* r){
 auto& server=*static_cast<HttpServer*>(r->user_ctx);
 auto* c=static_cast<Connection*>(httpd_sess_get_transport_ctx(r->handle,httpd_req_to_sockfd(r)));
 if(!c||!c->guard.complete()||!deadline(*c))return reject(r,Error::Timeout,"408 Request Timeout");
 char host[40]{},origin[64]{};
 if(!header(r,"Host",host,sizeof(host)))return reject(r,Error::Host);
 const bool page=r->method==HTTP_GET&&(std::strcmp(r->uri,"/")==0||std::strcmp(r->uri,"/app.js")==0);
 const bool status=r->method==HTTP_GET&&std::strcmp(r->uri,"/api/status")==0;
 if(std::string_view(host)!=(server.listener==Listener::Normal?"192.168.4.1":"192.168.4.1:8081"))return reject(r,Error::Host);
 if(server.listener==Listener::Normal&&page){if(r->content_len!=0)return reject(r,Error::Malformed);
 if(std::strcmp(r->uri,"/")==0)return finish(r,reinterpret_cast<const char*>(web_index_start),"text/html", "200 OK",static_cast<size_t>(web_index_end-web_index_start-1));
 return finish(r,reinterpret_cast<const char*>(web_app_start),"text/javascript","200 OK",static_cast<size_t>(web_app_end-web_app_start-1));
 }
 if(!header(r,"Origin",origin,sizeof(origin),!status)||(!status&&origin_host(server.listener,host,origin)!=Error::None)||(status&&origin[0]!='\0'&&std::string_view(origin)!="http://192.168.4.1"))return reject(r,Error::Origin);
 if(server.listener==Listener::Stop)cors(r);
 if(r->method==HTTP_OPTIONS){if(server.listener!=Listener::Stop||std::strcmp(r->uri,"/api/stop")!=0||r->content_len!=0)return reject(r,Error::Denied);
 char method[16]{},headers[128]{};
 if(!header(r,"Access-Control-Request-Method",method,sizeof(method))||std::strcmp(method,"POST")!=0||!header(r,"Access-Control-Request-Headers",headers,sizeof(headers)))return reject(r,Error::Denied);
 const std::string_view requested(headers);
 if(requested!="x-session-credential"&&requested!="content-type,x-session-credential"&&requested!="content-type, x-session-credential"&&requested!="x-session-credential,content-type"&&requested!="x-session-credential, content-type")return reject(r,Error::Denied);
 return finish(r,"", "text/plain","204 No Content");
 }
 Envelope e;
 e.listener=server.listener;
 e.enqueued_at=server.bridge->now();
 if(status&&server.listener==Listener::Normal){if(r->content_len!=0||!header(r,"X-Session-Credential",e.credential.data(),e.credential.size())||std::strlen(e.credential.data())!=32||!server.bridge->status_authorized(e.credential,e.enqueued_at))return reject(r,Error::Auth,"403 Forbidden");
  const auto s=server.bridge->copied_snapshot();
  char text[1800];
  char positions[320];
  std::snprintf(positions,sizeof(positions),"[{\"valid\":%s,\"value\":\"%lld\",\"at\":\"%llu\"},{\"valid\":%s,\"value\":\"%lld\",\"at\":\"%llu\"}]",s.positions[0].valid?"true":"false",static_cast<long long>(s.positions[0].value),static_cast<unsigned long long>(s.positions[0].at),s.positions[1].valid?"true":"false",static_cast<long long>(s.positions[1].value),static_cast<unsigned long long>(s.positions[1].at));
  std::snprintf(text,sizeof(text),"{\"boot\":\"%llu\",\"generation\":\"%llu\",\"at\":\"%llu\",\"phase\":%u,\"core_state\":%u,\"core_fault\":%u,\"fault_at\":\"%llu\",\"stop_at\":\"%llu\",\"selected_axis\":%u,\"axis_count\":%u,\"ready\":%s,\"lease_owner\":\"%llu\",\"lease_until\":\"%llu\",\"config_oldest_at\":\"%llu\",\"stop_verified\":%s,\"manual_power_cut_required\":%s,\"queue_stop_late\":%s,\"adapter_fault\":%u,\"core_stop_verified\":%s,\"positions\":%s,\"angle_available\":%s,\"angle_joint\":%u}",static_cast<unsigned long long>(s.boot),static_cast<unsigned long long>(s.generation),static_cast<unsigned long long>(s.at),static_cast<unsigned>(s.phase),s.core_state,s.core_fault,static_cast<unsigned long long>(s.fault_at),static_cast<unsigned long long>(s.stop_at),s.selected_axis,s.axis_count,s.ready?"true":"false",static_cast<unsigned long long>(s.lease_owner),static_cast<unsigned long long>(s.lease_until),static_cast<unsigned long long>(s.config_oldest_at),s.stop_verified?"true":"false",s.manual_power_cut_required?"true":"false",s.queue_stop_late?"true":"false",static_cast<unsigned>(s.adapter_fault),s.core_stop_verified?"true":"false",positions,s.angle_available?"true":"false",s.angle_joint);
  return finish(r,text);
 }
 const bool pairing=server.listener==Listener::Normal&&r->method==HTTP_POST&&std::strcmp(r->uri,"/api/session")==0;
 if(!pairing&&!(r->method==HTTP_POST&&((server.listener==Listener::Normal&&std::strcmp(r->uri,"/api/command")==0)||(server.listener==Listener::Stop&&std::strcmp(r->uri,"/api/stop")==0))))return reject(r,Error::Denied,"404 Not Found");
 e.pairing=pairing;
 if(!header(r,pairing?"X-Pairing-Credential":"X-Session-Credential",e.credential.data(),e.credential.size())||std::strlen(e.credential.data())!=32)return reject(r,Error::Auth,"403 Forbidden");
 if(pairing){if(r->content_len!=0)return reject(r,Error::Malformed);
 }
 else{char type[40]{};
 if(!header(r,"Content-Type",type,sizeof(type))||std::string_view(type)!="text/plain"||r->content_len==0||r->content_len>256)return reject(r,Error::Malformed);
 std::array<char,256> body{};
 size_t used=0;
 while(used<r->content_len){if(!deadline(*c))return reject(r,Error::Timeout,"408 Request Timeout");
 const int got=httpd_req_recv(r,body.data()+used,r->content_len-used);
 if(got<=0||!deadline(*c))return reject(r,Error::Timeout,"408 Request Timeout");
 used+=static_cast<size_t>(got);
 }
 if(!parse({body.data(),used},e.wire))return reject(r,Error::Malformed);
 if((server.listener==Listener::Stop)!=(e.wire.op==Op::Stop))return reject(r,Error::Denied);
 }
 if(server.next_job==std::numeric_limits<Time>::max())return reject(r,Error::Denied);
 e.job=server.next_job++;
 Result result;
 if(!server.bridge->exchange(e,result)||result.job!=e.job)return reject(r,Error::Timeout,"504 Gateway Timeout");
 char text[768];
 const int size=std::snprintf(text,sizeof(text),"{\"job\":\"%llu\",\"queued\":true,\"accepted_at\":\"%llu\",\"wire_error\":%u,\"core_error\":%u,\"lease\":\"%llu\",\"ticket\":\"%llu\",\"credential\":\"%s\",\"transfer_id\":\"%llu\",\"transfer_state\":%u,\"transfer_generation\":\"%llu\",\"pending_until\":\"%llu\",\"grant_at\":\"%llu\",\"lease_until\":\"%llu\",\"sequence_floor\":\"%llu\"}",static_cast<unsigned long long>(result.job),static_cast<unsigned long long>(result.accepted_at),static_cast<unsigned>(result.error),result.core_error,static_cast<unsigned long long>(result.lease),static_cast<unsigned long long>(result.ticket),result.paired?result.credential.data():"",static_cast<unsigned long long>(result.transfer_id),static_cast<unsigned>(result.transfer_state),static_cast<unsigned long long>(result.transfer_generation),static_cast<unsigned long long>(result.pending_until),static_cast<unsigned long long>(result.grant_at),static_cast<unsigned long long>(result.lease_until),static_cast<unsigned long long>(result.sequence_floor));
 if(size<0||static_cast<std::size_t>(size)>=sizeof(text))return reject(r,Error::Denied);
 return finish(r,text);
}
}
esp_err_t start_http(HttpServer& s)noexcept{
 httpd_config_t config=HTTPD_DEFAULT_CONFIG();
 config.server_port=s.listener==Listener::Normal?80:8081;
 config.ctrl_port=s.listener==Listener::Normal?32768:32769;
 config.max_open_sockets=s.listener==Listener::Normal?5:4;
 config.max_req_hdr_len=1024;
 config.max_uri_len=64;
 config.max_uri_handlers=6;
 config.stack_size=8192;
 config.task_priority=3;
 config.keep_alive_enable=false;
 config.open_fn=opened;
 auto result=httpd_start(&s.handle,&config);
 if(result!=ESP_OK)return result;
 const std::array<const char*,5> paths{{"/","/app.js","/api/status","/api/session","/api/command"}
 };
 if(s.listener==Listener::Normal){for(unsigned i=0;i<paths.size();++i){httpd_uri_t route{};
 route.uri=paths[i];
 route.method=i<3?HTTP_GET:HTTP_POST;
 route.handler=handler;
 route.user_ctx=&s;
 result=httpd_register_uri_handler(s.handle,&route);
 if(result!=ESP_OK){httpd_stop(s.handle);
 s.handle=nullptr;
 return result;
 }
 }
 }
 else{for(auto method:{HTTP_POST,HTTP_OPTIONS}){httpd_uri_t route{};
 route.uri="/api/stop";
 route.method=method;
 route.handler=handler;
 route.user_ctx=&s;
 result=httpd_register_uri_handler(s.handle,&route);
 if(result!=ESP_OK){httpd_stop(s.handle);
 s.handle=nullptr;
 return result;
 }
 }
 }
 return ESP_OK;
}
} // namespace robot_phone
