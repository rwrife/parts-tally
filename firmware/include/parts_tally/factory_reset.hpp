#pragma once
#include <cstdint>

#include "parts_tally/interfaces.hpp"
namespace parts_tally {
enum class ResetProgress { idle, holding, warning, erased, failed };
enum class ButtonAction { idle, reset_holding, reset_warning, factory_erased, reset_failed, tare };
class FactoryResetGesture {
 public:
  explicit FactoryResetGesture(IStorage& storage) : storage_(storage) {}
  ResetProgress update(bool pressed, std::uint64_t now_ms) {
    if (done_) return result_;
    if (!pressed) {
      started_ = false;
      return ResetProgress::idle;
    }
    if (!started_) {
      started_ = true;
      start_ms_ = now_ms;
      return ResetProgress::holding;
    }
    const auto held = now_ms - start_ms_;
    if (held >= 10000) {
      done_ = true;
      result_ = storage_.erase_all() ? ResetProgress::erased : ResetProgress::failed;
      return result_;
    }
    return held >= 7000 ? ResetProgress::warning : ResetProgress::holding;
  }

 private:
  IStorage& storage_;
  bool started_{}, done_{};
  std::uint64_t start_ms_{};
  ResetProgress result_{ResetProgress::idle};
};

class ButtonPolicy {
 public:
  explicit ButtonPolicy(IStorage& storage) : reset_(storage) {}

  void begin(bool pressed, std::uint64_t now_ms) {
    boot_armed_ = pressed;
    previous_ = pressed;
    pressed_ms_ = now_ms;
    if (pressed) reset_.update(true, now_ms);
  }

  ButtonAction update(bool pressed, std::uint64_t now_ms) {
    if (pressed && !previous_) pressed_ms_ = now_ms;
    if (boot_armed_) {
      const ResetProgress progress = reset_.update(pressed, now_ms);
      if (!pressed) boot_armed_ = false;
      previous_ = pressed;
      if (progress == ResetProgress::erased) return ButtonAction::factory_erased;
      if (progress == ResetProgress::failed) return ButtonAction::reset_failed;
      if (progress == ResetProgress::warning) return ButtonAction::reset_warning;
      if (progress == ResetProgress::holding) return ButtonAction::reset_holding;
      return now_ms - pressed_ms_ < 2000 ? ButtonAction::tare : ButtonAction::idle;
    }
    const bool short_release = !pressed && previous_ && now_ms - pressed_ms_ < 2000;
    previous_ = pressed;
    return short_release ? ButtonAction::tare : ButtonAction::idle;
  }

 private:
  FactoryResetGesture reset_;
  bool boot_armed_{}, previous_{};
  std::uint64_t pressed_ms_{};
};
}  // namespace parts_tally
