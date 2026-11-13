#pragma once
#include <cstddef>
#include <_timeval.h>
constexpr int SOL_SOCKET=1,SO_RCVTIMEO=2,SO_SNDTIMEO=3;
int recv(int,char*,size_t,int);
int setsockopt(int,int,int,const void*,size_t);
