// NO100F diagnostic: RenderWare's immediate-mode "...Instance.csl" pipeline node body (0x801895E8), reimplemented
// natively with logging. The game's code is three instructions: r0 = *(r4) (the data block RxPipelineExecute was
// handed); *(r13 - 0x6B18) = r0; return 1. The render node (0x80189758) then reads that block, and on the
// cutscene-skip path it is garbage. This logs the block, its caller chain and its first words whenever it does not
// look like a sane Im3D stash, so the producer can be found. Behaviour is identical to the original.
#include <cstdint>
#include "abi_bridge.h"
#include "memory.h"
#include "hle_stubs.h"
#include "ppc_runtime.h"
#include "runtime_log.h"

namespace {
bool InRam(uint32_t a) { return a >= 0x80000000u && a < 0x81800000u; }
}

extern "C" void No100f_ImmInstanceNode(CpuContext* ctx) {
    const uint32_t params = ctx->gpr[4];
    const uint32_t block = InRam(params) ? Memory::Read32(params) : 0;
    Memory::Write32(ctx->gpr[13] - 0x6B18u, block);
    ctx->gpr[3] = 1;

    // Every call (first 80): who ran the pipeline, and the fields the render node reads (+0x30 prim, +0x34 indices,
    // +0x38 count) next to the transform fields (+0 u16 numVerts, +4 verts).
    static int calls = 0;
    if (calls++ < 80 && InRam(block)) {
        uint32_t chain[4] = {};
        uint32_t frame = ctx->gpr[1];
        for (int depth = 0; depth < 4; ++depth) {
            const uint32_t next = InRam(frame) ? Memory::Read32(frame) : 0;
            if (!InRam(next)) break;
            chain[depth] = Memory::Read32(next + 4);
            frame = next;
        }
        RT_LOGF(RT_TAG_GX, "[im3d] #%d block=%08X n=%u verts=%08X prim=%08X idx=%08X cnt=%08X | callers %08X %08X %08X %08X\n",
                calls, block, Memory::Read32(block) >> 16, Memory::Read32(block + 4), Memory::Read32(block + 0x30),
                Memory::Read32(block + 0x34), Memory::Read32(block + 0x38), chain[0], chain[1], chain[2], chain[3]);
    }
}
PPC_NATIVE_OVERRIDE_VOID(801895E8, No100f_ImmInstanceNode, (CpuContext* ctx), (ctx));
