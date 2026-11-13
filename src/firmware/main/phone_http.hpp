#pragma once
#include "robot_phone/owner.hpp"
#include "esp_http_server.h"
namespace robot_phone {
// HTTP sees copies only; implementations must never call live core methods.
class Bridge {
public:
 virtual ~Bridge()=default;
 virtual Time now()const noexcept=0;
 virtual bool exchange(const Envelope& request,Result& result)noexcept=0;
 virtual Snapshot copied_snapshot()noexcept=0;
 virtual bool status_authorized(const Secret& credential,Time now)noexcept=0;
};
struct HttpServer {Bridge* bridge{nullptr};Listener listener{Listener::Normal};httpd_handle_t handle{nullptr};Time next_job{1};};
esp_err_t start_http(HttpServer& server)noexcept;
void start_prepared_runtime()noexcept;
} // namespace robot_phone
