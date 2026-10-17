#include "runtime_product.h"

namespace RuntimeProduct {

const Descriptor& Active() noexcept {
    static constexpr Descriptor descriptor{
        Kind::BaseGame,
        "Scooby-Doo: Refrightened",
    };
    return descriptor;
}

} // namespace RuntimeProduct
