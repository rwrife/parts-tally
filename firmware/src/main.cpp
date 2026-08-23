#include <Arduino.h>
#include <WiFi.h>
#include <esp_system.h>

#include <cstdio>
#include <string>

#include "drivers/arduino_adapters.hpp"
#include "drivers/target_transport.hpp"
#include "parts_tally/factory_reset.hpp"
#include "parts_tally/measurement.hpp"
#include "parts_tally/persistence.hpp"
#include "parts_tally/protocol.hpp"

using namespace parts_tally;

namespace {

std::string random_token();
void start_sta(const std::string& ssid, const std::string& password);

ArduinoClock clock_source;
CarrierButton button;
ActiveLowRgb indicator;
Nau7802Adc adc;
MeasurementPipeline pipeline;
PreferencesStorage storage;
Persistence persistence(storage);
PersistentState state;
ProtocolGuard guard("http://192.168.4.1");
ApiService api("pt-esp32c3", guard, pipeline, state, []() { return persistence.save(state); },
               random_token, start_sta);
LocalTransport transport(api);
ButtonPolicy button_policy(storage);
std::uint64_t last_event_ms{};
MeasurementState last_event_state{MeasurementState::stale};

std::string random_token() {
  char token[33]{};
  std::snprintf(token, sizeof(token), "%08lx%08lx%08lx%08lx",
                static_cast<unsigned long>(esp_random()), static_cast<unsigned long>(esp_random()),
                static_cast<unsigned long>(esp_random()), static_cast<unsigned long>(esp_random()));
  return token;
}

void start_sta(const std::string& ssid, const std::string& password) {
  transport.begin_sta(ssid, password);
}

void show_reset_progress(ResetProgress progress, std::uint64_t now_ms) {
  if (progress == ResetProgress::warning) {
    const bool phase = ((now_ms / 250) % 2) == 0;
    indicator.set(phase, false, !phase);
  } else if (progress == ResetProgress::holding) {
    indicator.set(false, false, true);
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  button.begin();
  indicator.begin();

  const std::uint64_t now = clock_source.monotonic_ms();
  const bool initially_pressed = button.pressed();
  button_policy.begin(initially_pressed, now);
  if (initially_pressed) {
    api.set_session(guard.open_setup_session(true, now, random_token()));
  }

  const LoadResult loaded = persistence.load(state);
  if (loaded == LoadResult::corrupt || loaded == LoadResult::unsupported) {
    indicator.set(true, false, false);
  }
  if (!state.profiles.empty()) {
    pipeline.set_calibration(state.profiles.front().calibration);
  }

  // The direct AP is the recovery/control plane on every boot. STA association
  // is asynchronous and never removes AP access.
  transport.begin("Parts-Tally-Direct");
  transport.begin_sta(state.wifi_ssid, state.wifi_password);

  if (!adc.begin()) {
    indicator.set(true, false, false);
  }
}

void loop() {
  const std::uint64_t now = clock_source.monotonic_ms();
  const bool pressed = button.pressed();
  const ButtonAction action = button_policy.update(pressed, now);
  const ResetProgress reset = action == ButtonAction::reset_warning
                                  ? ResetProgress::warning
                                  : (action == ButtonAction::reset_holding ? ResetProgress::holding
                                                                           : ResetProgress::idle);
  show_reset_progress(reset, now);
  if (action == ButtonAction::factory_erased) {
    transport.broadcast(api.event("device.restarting", "{}", now));
    WiFi.disconnect(true, true);
    delay(100);
    ESP.restart();
  }

  AdcSample sample;
  if (adc.read(sample)) {
    pipeline.ingest(sample, now);
  }
  const Measurement measurement = pipeline.evaluate(now);
  if (!state.profiles.empty()) {
    api.record_stable_count(state.profiles.front().id, measurement, now);
  }
  if (reset == ResetProgress::idle) {
    indicator.set(measurement.state != MeasurementState::stable,
                  measurement.state == MeasurementState::stable,
                  measurement.state == MeasurementState::unstable);
  }

  if (action == ButtonAction::tare && pipeline.tare(now)) {
    if (!state.profiles.empty()) state.profiles.front().calibration = pipeline.calibration();
    persistence.save(state);
    transport.broadcast(api.event("status.updated", "{\"localTare\":true}", now));
  }

  if (now - last_event_ms >= 250) {
    char payload[192]{};
    std::snprintf(payload, sizeof(payload),
                  "{\"state\":\"%s\",\"stable\":%s,\"netGrams\":%.6g}",
                  state_name(measurement.state), measurement.stable ? "true" : "false",
                  measurement.net_grams);
    transport.broadcast(api.event("measurement.updated", payload, now));
    if (measurement.state != last_event_state) {
      const bool fault = measurement.state == MeasurementState::disconnected ||
                         measurement.state == MeasurementState::saturated ||
                         measurement.state == MeasurementState::overload_indicated;
      transport.broadcast(api.event(fault ? "fault.raised" : "status.updated", payload, now));
      last_event_state = measurement.state;
    }
    last_event_ms = now;
  }

  transport.poll();
  delay(2);
}
