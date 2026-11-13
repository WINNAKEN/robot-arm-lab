#pragma once
#include <cstdlib>
#include <iostream>

inline unsigned check_count = 0;
inline void check(bool condition, const char* expression, const char* file, int line) {
    ++check_count;
    if (!condition) {
        std::cerr << file << ':' << line << " CHECK FAILED: " << expression << '\n';
        std::exit(1);
    }
}
#define CHECK(expression) check(static_cast<bool>(expression), #expression, __FILE__, __LINE__)
