#include "hle_stubs.h"
#include "memory.h"
#include "hle/controller_status_contract.h"
#include "hle/no100f_pad_actions.h"
#include "hle/no100f_xbox_layout.h"
#include "input_bindings.h"
#include "wii_remote_input.h"
#include "runtime_config.h"
#include "runtime_log.h"

#include <aurora/aurora.h>
#include <SDL3/SDL_gamepad.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>

#include <SDL3/SDL_gamepad.h>
#include <dolphin/pad.h>

namespace {

std::atomic<bool> g_rumbleEnabled{true};

// Original Xbox controls (hle/no100f_xbox_layout.h), applied to each controller's mapped buttons inside PADRead.
std::array<No100fXboxLayout::PortState, PAD_CHANMAX> g_xboxPorts;
bool g_xboxMenu = false;

u16 XboxLayoutFilter(u32 port, SDL_Gamepad* gamepad, u16 buttons) {
    if (port >= g_xboxPorts.size()) {
        return buttons;
    }
    return No100fXboxLayout::Filter(g_xboxPorts[port], buttons, g_xboxMenu,
                                    SDL_GetGamepadButton(gamepad, SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER),
                                    SDL_GetGamepadButton(gamepad, SDL_GAMEPAD_BUTTON_LEFT_SHOULDER));
}

bool NativeButtonHeld(SDL_Gamepad* gamepad, uint32_t nativeButton) {
    if (gamepad == nullptr || nativeButton == PAD_NATIVE_BUTTON_INVALID ||
        nativeButton >= SDL_GAMEPAD_BUTTON_COUNT) {
        return false;
    }
    return SDL_GetGamepadButton(gamepad, static_cast<SDL_GamepadButton>(nativeButton));
}

// A digital button bound to L or R has no analog travel of its own. On real
// hardware the click only engages at full depression, so report a full pull.
void FillTriggersHeldByButtons(PADStatus* statuses) {
    if (InputBindings::InputBlocked()) {
        return;
    }
    for (uint32_t port = 0; port < PAD_CHANMAX; ++port) {
        if (statuses[port].err != PAD_ERR_NONE) {
            continue;
        }
        const s32 index = PADGetIndexForPort(port);
        if (index < 0) {
            continue;
        }
        SDL_Gamepad* gamepad = PADGetSDLGamepadForIndex(static_cast<u32>(index));
        if (gamepad == nullptr) {
            continue;
        }
        const auto scan = [&](PADButtonMapping* mappings, u32 count) {
            if (mappings == nullptr) {
                return;
            }
            for (u32 i = 0; i < count; ++i) {
                const PADButtonMapping& mapping = mappings[i];
                if (mapping.padButton != PAD_TRIGGER_L && mapping.padButton != PAD_TRIGGER_R) {
                    continue;
                }
                if (!NativeButtonHeld(gamepad, mapping.nativeButton)) {
                    continue;
                }
                if (mapping.padButton == PAD_TRIGGER_L) {
                    statuses[port].triggerLeft = 255;
                } else {
                    statuses[port].triggerRight = 255;
                }
            }
        };
        u32 count = 0;
        scan(PADGetButtonMappings(port, &count), count);
        count = 0;
        scan(PADGetAltButtonMappings(port, &count), count);
    }
}

void WritePadStatus(uint32_t base, const PADStatus& status) {
    const auto guestStatus = PadStatusContract::Encode({
        status.button,
        status.stickX,
        status.stickY,
        status.substickX,
        status.substickY,
        status.triggerL,
        status.triggerR,
        status.analogA,
        status.analogB,
        status.err,
    });
    uint8_t* dst = Memory::GetPointer(base, guestStatus.size());
    std::memcpy(dst, guestStatus.data(), guestStatus.size());
}

} // namespace

extern "C" void PAD_HLE_SetRumbleEnabled(bool enabled)
{
    g_rumbleEnabled.store(enabled, std::memory_order_relaxed);
}

void No100fPad::XboxButtons(uint32_t port, bool& black, bool& white)
{
    black = white = false;
    if (port < g_xboxPorts.size()) {
        black = g_xboxPorts[port].black;
        white = g_xboxPorts[port].white;
    }
}

extern "C" uint32_t PAD__Init_HLE()
{
    return PADInit() ? 1u : 0u;
}
// Scooby-Doo! Unmasked (GameCube): PADInit is the game's pad API.
PPC_NATIVE_OVERRIDE(800012CC, PAD__Init_HLE, uint32_t, (), ());

// PADRead: gathers every GameCube pad source for the frame and writes the statuses to guest memory.
extern "C" uint32_t PAD__Read_HLE(uint32_t statusPtr)
{
    if (statusPtr == 0) {
        return 0;
    }

    PADStatus statuses[PAD_CHANMAX]{};
    // Keep looking for a Bluetooth Wii Remote that dropped out (or was turned on late).
    WiiRemoteInput::Poll();
    const bool xboxLayout = RuntimeConfigFile::XboxOriginalLayout();
    if (xboxLayout) {
        const uint32_t scenePtr = Memory::Read32(No100fXboxLayout::kScenePointer);
        const uint32_t sceneAddress = scenePtr + No100fXboxLayout::kSceneIdOffset;
        const uint32_t scene = scenePtr && Memory::Contains(sceneAddress, 4) ? Memory::Read32(sceneAddress) : 0;
        const uint32_t mode = Memory::Read32(No100fXboxLayout::kModeAddress);
        g_xboxMenu = No100fXboxLayout::IsMenuMode(mode) || No100fXboxLayout::IsMenuScene(scene);
        for (auto& port : g_xboxPorts) {
            port.black = port.white = false;
        }
    }
    uint32_t rumbleMask = xboxLayout ? PADReadWithGamepadButtonFilter(statuses, XboxLayoutFilter) : PADRead(statuses);
    // Wii Remotes reach the game through KPAD, not as GameCube pads. This also
    // applies while input is blocked (overlay open) so the port does not flip
    // between "connected" and "no controller" every time the overlay toggles.
    WiiRemoteInput::HideRemotesFromPad(statuses, PAD_CHANMAX);

    // On-screen button prompts follow the first connected controller (UserData/button_icons, tools/make-button-icons.py);
    // with the Xbox layout, gameplay uses the B/X-swapped set (style + 3).
    static int family = -1;
    if (static unsigned n = 0; n++ % 30 == 0) {
        int count = 0, style = -1;
        if (SDL_JoystickID* ids = SDL_GetGamepads(&count)) {
            if (count > 0) switch (SDL_GetGamepadTypeForID(ids[0])) {
                case SDL_GAMEPAD_TYPE_UNKNOWN: break;
                case SDL_GAMEPAD_TYPE_PS3: case SDL_GAMEPAD_TYPE_PS4: case SDL_GAMEPAD_TYPE_PS5: style = 1; break;
                case SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_PRO: case SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_LEFT:
                case SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_RIGHT: case SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_PAIR: style = 2; break;
                default: style = 0; break;
            }
            SDL_free(ids);
        }
        family = style;
    }
    aurora_set_button_icon_style(family >= 0 && xboxLayout && !g_xboxMenu ? family + 3 : family);
    FillTriggersHeldByButtons(statuses);
    InputBindings::Apply(statuses);
    if (uint16_t scripted = 0; WiiRemoteInput::ScriptedPadButtons(scripted)) {
        statuses[0].err = PAD_ERR_NONE;
        statuses[0].button |= scripted;
        if (scripted) { static int n = 0; if (n++ < 5) RT_LOGF(RT_TAG_OS, "[pad] PADRead scripted buttons 0x%04X\n", scripted); }
    }

    try {
        for (uint32_t i = 0; i < PAD_CHANMAX; ++i) {
            WritePadStatus(statusPtr + static_cast<uint32_t>(i * PadStatusContract::kGuestStatusSize),
                           statuses[i]);
        }
    } catch (const Memory::AccessViolation&) {
        return 0;
    }

    return rumbleMask;
}
// Scooby-Doo! Unmasked (GameCube): PADRead is the game's pad API.
PPC_NATIVE_OVERRIDE(8010CEE0, PAD__Read_HLE, uint32_t, (uint32_t statusPtr), (statusPtr));

extern "C" uint32_t PAD__Reset_HLE(uint32_t mask)
{
    return PADReset(mask) ? 1u : 0u;
}
// Scooby-Doo! Unmasked (GameCube): PADReset is the game's pad API.
PPC_NATIVE_OVERRIDE(8010CACC, PAD__Reset_HLE, uint32_t, (uint32_t mask), (mask));

extern "C" uint32_t PAD__Recalibrate_HLE(uint32_t mask)
{
    return PADRecalibrate(mask) ? 1u : 0u;
}
// Scooby-Doo! Unmasked (GameCube): PADRecalibrate is the game's pad API.
PPC_NATIVE_OVERRIDE(8010CBCC, PAD__Recalibrate_HLE, uint32_t, (uint32_t mask), (mask));

extern "C" void PAD__ControlMotor_HLE(int32_t chan, uint32_t command)
{
    if (command == PAD_MOTOR_RUMBLE && !g_rumbleEnabled.load(std::memory_order_relaxed)) {
        command = PAD_MOTOR_STOP;
    }
    PADControlMotor(chan, command);
}
// Scooby-Doo! Unmasked (GameCube): PADControlMotor is the game's pad API.
PPC_NATIVE_OVERRIDE_VOID(8010D28C, PAD__ControlMotor_HLE, (int32_t chan, uint32_t command), (chan, command));
