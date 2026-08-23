#pragma once

#include <Arduino.h>
#include <Preferences.h>
#include <Wire.h>
#include <nvs_flash.h>

#include <array>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

#include "parts_tally/interfaces.hpp"

namespace parts_tally {

class ArduinoClock final : public IClock {
 public:
  std::uint64_t monotonic_ms() const override { return millis(); }
};

class CarrierButton final : public IButton {
 public:
  void begin() { pinMode(pins::button, INPUT_PULLUP); }
  bool pressed() const override { return digitalRead(pins::button) == LOW; }
};

class ActiveLowRgb final : public IStatusIndicator {
 public:
  void begin() {
    pinMode(pins::rgb_red, OUTPUT);
    pinMode(pins::rgb_green, OUTPUT);
    pinMode(pins::rgb_blue, OUTPUT);
    set(false, false, false);
  }

  void set(bool red, bool green, bool blue) override {
    digitalWrite(pins::rgb_red, red ? LOW : HIGH);
    digitalWrite(pins::rgb_green, green ? LOW : HIGH);
    digitalWrite(pins::rgb_blue, blue ? LOW : HIGH);
  }
};

class Nau7802Adc final : public IAdcReader {
 public:
  static constexpr std::uint8_t address = 0x2A;

  explicit Nau7802Adc(std::int32_t overload_abs_code = 8000000)
      : overload_abs_code_(overload_abs_code) {}

  bool begin() {
    Wire.begin(pins::sda, pins::scl);
    Wire.setClock(400000);

    // NAU7802 Rev 2.6: reset, power digital/analog blocks, and wait for PUR.
    if (!write_register(kPuCtrl, kPuCtrlReset) || !write_register(kPuCtrl, 0) ||
        !set_bits(kPuCtrl, kPuCtrlPowerDigital | kPuCtrlPowerAnalog)) {
      connected_ = false;
      return false;
    }
    const std::uint32_t power_start = millis();
    while (millis() - power_start < 100) {
      std::uint8_t power{};
      if (read_register(kPuCtrl, power) && (power & kPuCtrlPowerReady)) {
        break;
      }
      delay(1);
    }

    std::uint8_t power{};
    if (!read_register(kPuCtrl, power) || !(power & kPuCtrlPowerReady)) {
      connected_ = false;
      return false;
    }

    // NAU7802 Rev. 2.6 CTRL1: PGA gain 128 and VLDO=010 (3.0 V).
    // CLK_CHP=0 keeps the internal oscillator. CTRL2 CRS=000 selects
    // 10 SPS and CHS=0 selects channel 1.
    if (!write_register(kCtrl1, kGain128 | kLdo3v0) ||
        !write_register(kCtrl2, kRate10SpsChannel1) || !set_bits(kPgaPower, kPgaCapEnable)) {
      connected_ = false;
      return false;
    }

    // Internal offset calibration; CALS self-clears and CAL_ERROR reports
    // failure. Calibration is bounded so a missing device cannot hang boot.
    if (!set_bits(kCtrl2, kCalibrationStart)) {
      connected_ = false;
      return false;
    }
    const std::uint32_t calibration_start = millis();
    do {
      std::uint8_t control{};
      if (!read_register(kCtrl2, control)) {
        connected_ = false;
        return false;
      }
      if ((control & kCalibrationStart) == 0) {
        connected_ = (control & kCalibrationError) == 0 && set_bits(kPuCtrl, kPuCtrlCycleStart);
        return connected_;
      }
      delay(1);
    } while (millis() - calibration_start < 1000);

    connected_ = false;
    return false;
  }

  bool read(AdcSample& sample) override {
    sample.monotonic_ms = millis();
    if (!connected_) {
      sample.fault = SensorFault::disconnected;
      return true;
    }

    std::uint8_t power{};
    if (!read_register(kPuCtrl, power)) {
      connected_ = false;
      sample.fault = SensorFault::disconnected;
      return true;
    }
    if ((power & kPuCtrlConversionReady) == 0) {
      return false;
    }

    std::array<std::uint8_t, 3> bytes{};
    if (!read_bytes(kAdcoB2, bytes.data(), bytes.size())) {
      connected_ = false;
      sample.fault = SensorFault::disconnected;
      return true;
    }

    std::int32_t code = (static_cast<std::int32_t>(bytes[0]) << 16) |
                        (static_cast<std::int32_t>(bytes[1]) << 8) | bytes[2];
    if (code & 0x00800000) {
      code |= static_cast<std::int32_t>(0xFF000000);
    }
    sample.code = code;
    if (code == -8388608 || code == 8388607) {
      sample.fault = SensorFault::saturated;
    } else if (code <= -overload_abs_code_ || code >= overload_abs_code_) {
      sample.fault = SensorFault::overload_indicated;
    } else {
      sample.fault = SensorFault::none;
    }
    return true;
  }

 private:
  static constexpr std::uint8_t kPuCtrl = 0x00;
  static constexpr std::uint8_t kCtrl1 = 0x01;
  static constexpr std::uint8_t kCtrl2 = 0x02;
  static constexpr std::uint8_t kAdcoB2 = 0x12;
  static constexpr std::uint8_t kPgaPower = 0x1B;

  static constexpr std::uint8_t kPuCtrlConversionReady = 1U << 5;
  static constexpr std::uint8_t kPuCtrlCycleStart = 1U << 4;
  static constexpr std::uint8_t kPuCtrlPowerReady = 1U << 3;
  static constexpr std::uint8_t kPuCtrlPowerDigital = 1U << 2;
  static constexpr std::uint8_t kPuCtrlPowerAnalog = 1U << 1;
  static constexpr std::uint8_t kPuCtrlReset = 1U;
  static constexpr std::uint8_t kGain128 = 0x07;
  static constexpr std::uint8_t kLdo3v0 = 0x02 << 3;
  static constexpr std::uint8_t kRate10SpsChannel1 = 0x00;
  static constexpr std::uint8_t kCalibrationStart = 1U << 2;
  static constexpr std::uint8_t kCalibrationError = 1U << 3;
  static constexpr std::uint8_t kPgaCapEnable = 1U << 7;

  bool write_register(std::uint8_t reg, std::uint8_t value) {
    Wire.beginTransmission(address);
    Wire.write(reg);
    Wire.write(value);
    return Wire.endTransmission() == 0;
  }

  bool read_register(std::uint8_t reg, std::uint8_t& value) { return read_bytes(reg, &value, 1); }

  bool read_bytes(std::uint8_t reg, std::uint8_t* output, std::size_t length) {
    Wire.beginTransmission(address);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) {
      return false;
    }
    const std::size_t received =
        Wire.requestFrom(static_cast<int>(address), static_cast<int>(length));
    if (received != length) {
      return false;
    }
    for (std::size_t index = 0; index < length; ++index) {
      output[index] = static_cast<std::uint8_t>(Wire.read());
    }
    return true;
  }

  bool set_bits(std::uint8_t reg, std::uint8_t mask) {
    std::uint8_t value{};
    return read_register(reg, value) && write_register(reg, value | mask);
  }

  std::int32_t overload_abs_code_;
  bool connected_{false};
};

class PreferencesStorage final : public IStorage {
 public:
  bool read(const std::string& key, std::vector<std::uint8_t>& value) override {
    Preferences preferences;
    if (!preferences.begin(kNamespace, true)) {
      return false;
    }
    const std::uint32_t active = preferences.getUInt(active_key(key).c_str(), 0);
    const bool success = read_slot(preferences, key, active, value) ||
                         read_slot(preferences, key, active ^ 1U, value);
    preferences.end();
    return success;
  }

  bool replace_atomically(const std::string& key, const std::vector<std::uint8_t>& value) override {
    Preferences preferences;
    if (!preferences.begin(kNamespace, false)) {
      return false;
    }
    const std::uint32_t active = preferences.getUInt(active_key(key).c_str(), 0);
    const std::uint32_t replacement = active ^ 1U;
    std::vector<std::uint8_t> record(sizeof(RecordHeader) + value.size());
    RecordHeader header{kMagic, checksum(value), static_cast<std::uint32_t>(value.size())};
    std::memcpy(record.data(), &header, sizeof(header));
    std::copy(value.begin(), value.end(), record.begin() + sizeof(header));

    const std::string destination = slot_key(key, replacement);
    const bool wrote =
        preferences.putBytes(destination.c_str(), record.data(), record.size()) == record.size();
    std::vector<std::uint8_t> verify;
    const bool verified =
        wrote && read_slot(preferences, key, replacement, verify) && verify == value;
    const bool switched = verified && preferences.putUInt(active_key(key).c_str(), replacement) ==
                                          sizeof(std::uint32_t);
    preferences.end();
    return switched;
  }

  bool erase_all() override {
    // Factory reset intentionally erases the entire default NVS partition:
    // application slots, Wi-Fi credentials, device secrets, and sessions.
    // Reinitialize it so shutdown/restart code can still use platform APIs.
    if (nvs_flash_erase() != ESP_OK) {
      return false;
    }
    return nvs_flash_init() == ESP_OK;
  }

 private:
  struct RecordHeader {
    std::uint32_t magic;
    std::uint32_t checksum;
    std::uint32_t length;
  };

  static constexpr const char* kNamespace = "parts-tally";
  static constexpr std::uint32_t kMagic = 0x50544132;

  static std::uint32_t checksum(const std::vector<std::uint8_t>& value) {
    std::uint32_t result = 2166136261U;
    for (std::uint8_t byte : value) {
      result = (result ^ byte) * 16777619U;
    }
    return result;
  }

  static std::string active_key(const std::string& key) { return key.substr(0, 10) + "-a"; }

  static std::string slot_key(const std::string& key, std::uint32_t slot) {
    return key.substr(0, 10) + (slot == 0 ? "-0" : "-1");
  }

  static bool read_slot(Preferences& preferences, const std::string& key, std::uint32_t slot,
                        std::vector<std::uint8_t>& value) {
    const std::string source = slot_key(key, slot);
    const std::size_t size = preferences.getBytesLength(source.c_str());
    if (size < sizeof(RecordHeader) || size > 65536) {
      return false;
    }
    std::vector<std::uint8_t> record(size);
    if (preferences.getBytes(source.c_str(), record.data(), size) != size) {
      return false;
    }
    RecordHeader header{};
    std::memcpy(&header, record.data(), sizeof(header));
    if (header.magic != kMagic || header.length != size - sizeof(header)) {
      return false;
    }
    value.assign(record.begin() + sizeof(header), record.end());
    return checksum(value) == header.checksum;
  }
};

}  // namespace parts_tally
