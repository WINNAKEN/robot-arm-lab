#include "test_support.hpp"
void run_codec_tests();
void run_stop_tests();
int main() {
    run_codec_tests();
    run_stop_tests();
    std::cout << "HOST_CORE_PASS assertions=" << check_count << '\n';
    return 0;
}
