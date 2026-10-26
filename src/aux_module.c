#include "aux.h"

ISLA_NOINLINE uint32_t aux_cala1(uint32_t x) {
    return x * 3u + 1u;
}

ISLA_NOINLINE uint32_t aux_cala2(uint32_t x) {
    return x * 3u + 1u;
}

ISLA_NOINLINE uint32_t aux_cala3(uint32_t x) {
    return x * 3u + 1u;
}

ISLA_NOINLINE uint32_t aux_mix(uint32_t x) {
    return (x ^ 0x9E3779B9u) * 2654435761u + 7u;
}

uint32_t aux_no_usada(uint32_t x) {
    return x * 11u + 5u;
}
