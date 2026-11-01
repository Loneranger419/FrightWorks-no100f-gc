#pragma once

#include "texture.hpp"
#include <optional>

namespace aurora::gfx::texture_replacement {
void initialize() noexcept;
void shutdown() noexcept;
void register_tlut(const GXTlutObj* obj, const void* data, GXTlutFmt format, uint16_t entries) noexcept;
void load_tlut(const GXTlutObj* obj, uint32_t idx) noexcept;
std::optional<TextureHandle> find_replacement(const GXTexObj_& obj) noexcept;
std::string build_texture_replacement_name(const GXTexObj_& obj) noexcept;
// Dev menu (F8): whether the replacement with this file name (no extension) has been drawn since start.
bool replacement_used(std::string_view name) noexcept;
// Dev menu (F8): forget them (new level); the next take_highlight_change returns true.
void reset_used() noexcept;
// Dev menu (F8): draw that replacement solid magenta ("" = off). take_highlight_change returns true once after
// it changed: the caller must drop its cached textures so find_replacement runs again.
void set_highlight(std::string_view name) noexcept;
bool take_highlight_change() noexcept;
// Dev menu (F8): whether this handle is the magenta highlight texture (never creates it).
bool is_highlight_handle(const TextureHandle& handle) noexcept;
// Dev menu (F8): texture log (gx.cpp, devmenu_texlog.csv): the scene its rows are tagged with, "" = off.
// texture_log_generation changes on every set, so the draw path re-reads the scene only then.
void set_texture_log_scene(std::string_view scene) noexcept;
std::string texture_log_scene() noexcept;
uint32_t texture_log_generation() noexcept;
// Button prompt set for the controller in use (0 xbox, 1 playstation, 2 nintendo, -1 the game's own GameCube icons).
// take_button_icon_style_change returns true once after it changed, so cached textures can be re-resolved.
void set_button_icon_style(int style) noexcept;
bool take_button_icon_style_change() noexcept;
int button_icon_style() noexcept;
} // namespace aurora::gfx::texture_replacement
