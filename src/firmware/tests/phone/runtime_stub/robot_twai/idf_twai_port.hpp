#pragma once
// Explicit host dependency: the actual runtime composes the existing wire fake.
// This header is on the stub test include path only, never target CMake.
namespace robot_can {class IdfTwaiPort:public BootFake{};}
