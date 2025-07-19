#pragma once
#include "pico/stdlib.h"

struct Digest {
    double    timestamp;
    uint8_t   byte_val;
    bool      dir;
};

extern const Digest digests[];
extern const size_t NUM_DIGESTS;
