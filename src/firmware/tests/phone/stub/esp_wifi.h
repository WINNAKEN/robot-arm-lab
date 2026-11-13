#pragma once
#include "esp_http_server.h"
struct wifi_init_config_t{int unused{};};
#define WIFI_INIT_CONFIG_DEFAULT() {}
struct wifi_config_t{struct{unsigned char ssid[32]{},password[64]{};unsigned ssid_len{},channel{},max_connection{},authmode{};struct{bool required{};}pmf_cfg;}ap;};
constexpr int WIFI_AUTH_WPA2_PSK=1,WIFI_MODE_AP=1,WIFI_IF_AP=1;
esp_err_t esp_wifi_init(const wifi_init_config_t*);esp_err_t esp_wifi_set_mode(int);esp_err_t esp_wifi_set_config(int,const wifi_config_t*);esp_err_t esp_wifi_start();
