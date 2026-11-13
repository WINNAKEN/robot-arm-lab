#pragma once
#include "FreeRTOS.h"
TickType_t xTaskGetTickCount();void vTaskDelayUntil(TickType_t*,TickType_t);BaseType_t xTaskCreate(void(*)(void*),const char*,unsigned,void*,unsigned,void*);
