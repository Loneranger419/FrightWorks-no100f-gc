#include "runtime_product.h"

namespace RuntimeProduct {

const Descriptor& Active() noexcept {
    static constexpr Descriptor descriptor{
        Kind::BaseGame,
        "FrightWorks: Night of 100 Frights",
    };
    return descriptor;
}

} // namespace RuntimeProduct
