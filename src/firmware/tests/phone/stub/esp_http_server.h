#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
#include <map>
#include <vector>
#include <functional>
using ssize_t=std::ptrdiff_t;using esp_err_t=int;using BaseType_t=int;
constexpr int ESP_OK=0,ESP_FAIL=-1,ESP_ERR_NO_MEM=257;
constexpr int HTTPD_SOCK_ERR_TIMEOUT=-3,HTTPD_SOCK_ERR_FAIL=-1;constexpr ssize_t HTTPD_RESP_USE_STRLEN=-1;
enum httpd_method_t{HTTP_GET,HTTP_POST,HTTP_OPTIONS};
struct StubServer;using httpd_handle_t=StubServer*;using httpd_free_ctx_fn_t=void(*)(void*);
using httpd_recv_func_t=int(*)(httpd_handle_t,int,char*,size_t,int);
struct httpd_req_t{httpd_handle_t handle{};void* user_ctx{};httpd_method_t method{};const char* uri{};size_t content_len{};int fd{};std::map<std::string,std::string> headers;std::string body,response,status,type;std::map<std::string,std::string> response_headers;size_t body_at{0};std::function<void()> on_body;std::vector<std::uint64_t> body_delays;unsigned body_reads{0};};
struct httpd_uri_t{const char* uri{};httpd_method_t method{};esp_err_t(*handler)(httpd_req_t*){};void* user_ctx{};};
struct httpd_config_t{unsigned task_priority{};size_t stack_size{},max_req_hdr_len{},max_uri_len{};std::uint16_t server_port{},ctrl_port{},max_open_sockets{},max_uri_handlers{};bool keep_alive_enable{};esp_err_t(*open_fn)(httpd_handle_t,int){};};
#define HTTPD_DEFAULT_CONFIG() {}
struct StubConnection{void* ctx{};httpd_free_ctx_fn_t free_ctx{};httpd_recv_func_t receive{};std::vector<std::string> fragments;size_t next{0};bool closed{false};std::vector<std::uint64_t> receive_delays;};
struct StubServer{httpd_config_t config{};std::vector<httpd_uri_t> routes;std::map<int,StubConnection> connections;};
esp_err_t httpd_start(httpd_handle_t*,const httpd_config_t*);
esp_err_t httpd_stop(httpd_handle_t);
esp_err_t httpd_register_uri_handler(httpd_handle_t,const httpd_uri_t*);
esp_err_t httpd_sess_set_recv_override(httpd_handle_t,int,httpd_recv_func_t);
void httpd_sess_set_transport_ctx(httpd_handle_t,int,void*,httpd_free_ctx_fn_t);
void* httpd_sess_get_transport_ctx(httpd_handle_t,int);
esp_err_t httpd_sess_trigger_close(httpd_handle_t,int);
int httpd_req_to_sockfd(httpd_req_t*);
size_t httpd_req_get_hdr_value_len(httpd_req_t*,const char*);
esp_err_t httpd_req_get_hdr_value_str(httpd_req_t*,const char*,char*,size_t);
esp_err_t httpd_resp_set_hdr(httpd_req_t*,const char*,const char*);
esp_err_t httpd_resp_set_status(httpd_req_t*,const char*);
esp_err_t httpd_resp_set_type(httpd_req_t*,const char*);
esp_err_t httpd_resp_send(httpd_req_t*,const char*,ssize_t);
int httpd_req_recv(httpd_req_t*,char*,size_t);
