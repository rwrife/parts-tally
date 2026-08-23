#include <unity.h>

#include <cmath>
#include <cstdint>
#include <limits>
#include <string>

#include "parts_tally/measurement.hpp"

using namespace parts_tally;

namespace {

MeasurementConfig configuration() {
  MeasurementConfig config;
  config.window_samples = 25;
  config.max_noise_codes = 10;
  config.max_abs_slope_codes_per_second = 5;
  config.outlier_threshold_codes = 40;
  config.stale_after_ms = 600;
  config.max_uncertainty_pieces = 5;
  return config;
}

void feed_constant(MeasurementPipeline& pipeline, int code, std::uint64_t start, int count,
                   SensorFault fault = SensorFault::none) {
  for (int index = 0; index < count; ++index) {
    const std::uint64_t time = start + static_cast<std::uint64_t>(index) * 100;
    pipeline.ingest({code + (index % 3) - 1, time, fault}, time);
  }
}

void zero_stream_becomes_stable_but_uncalibrated() {
  MeasurementPipeline pipeline(configuration());
  feed_constant(pipeline, 0, 0, 25);
  TEST_ASSERT_EQUAL_STRING("uncalibrated", state_name(pipeline.evaluate(2400).state));
  TEST_ASSERT_FALSE(pipeline.evaluate(2400).estimated_count.has_value());
}

void sustained_step_restarts_dwell_and_recovers() {
  MeasurementPipeline pipeline(configuration());
  feed_constant(pipeline, 1000, 0, 25);
  feed_constant(pipeline, 1200, 2500, 3);
  TEST_ASSERT_EQUAL_STRING("unstable", state_name(pipeline.evaluate(2700).state));
  feed_constant(pipeline, 1200, 2800, 22);
  TEST_ASSERT_INT_WITHIN(2, 1200, static_cast<int>(pipeline.evaluate(4900).filtered_code));
}

void vibration_never_claims_a_count() {
  MeasurementPipeline pipeline(configuration());
  for (int index = 0; index < 50; ++index) {
    const int code = index % 2 == 0 ? 900 : 1100;
    const std::uint64_t time = static_cast<std::uint64_t>(index) * 100;
    pipeline.ingest({code, time, SensorFault::none}, time);
  }
  const Measurement result = pipeline.evaluate(4900);
  TEST_ASSERT_EQUAL_STRING("unstable", state_name(result.state));
  TEST_ASSERT_FALSE(result.estimated_count.has_value());
}

void drift_and_creep_withhold_stability() {
  MeasurementPipeline drift(configuration());
  for (int index = 0; index < 30; ++index) {
    const std::uint64_t time = static_cast<std::uint64_t>(index) * 100;
    drift.ingest({1000 + index, time, SensorFault::none}, time);
  }
  TEST_ASSERT_EQUAL_STRING("unstable", state_name(drift.evaluate(2900).state));
  TEST_ASSERT_GREATER_THAN(5.0, std::abs(drift.evaluate(2900).diagnostics.slope_codes_per_second));

  MeasurementPipeline creep(configuration());
  for (int index = 0; index < 40; ++index) {
    const std::uint64_t time = static_cast<std::uint64_t>(index) * 100;
    creep.ingest({2000 + index / 2, time, SensorFault::none}, time);
  }
  TEST_ASSERT_EQUAL_STRING("unstable", state_name(creep.evaluate(3900).state));
}

void disconnect_saturation_overload_and_stale_are_explicit() {
  MeasurementPipeline pipeline(configuration());
  feed_constant(pipeline, 0, 0, 25);

  pipeline.ingest({0, 2500, SensorFault::disconnected}, 2500);
  TEST_ASSERT_EQUAL_STRING("disconnected", state_name(pipeline.evaluate(2500).state));
  pipeline.ingest({8388607, 2600, SensorFault::saturated}, 2600);
  TEST_ASSERT_EQUAL_STRING("saturated", state_name(pipeline.evaluate(2600).state));
  pipeline.ingest({8000001, 2700, SensorFault::none}, 2700);
  TEST_ASSERT_EQUAL_STRING("overload_indicated", state_name(pipeline.evaluate(2700).state));
  TEST_ASSERT_EQUAL_STRING("stale", state_name(pipeline.evaluate(4000).state));
}

void calibration_and_rounding_are_deterministic() {
  MeasurementPipeline pipeline(configuration());
  pipeline.set_scale(0.01);
  feed_constant(pipeline, 1000, 0, 25);
  TEST_ASSERT_TRUE(pipeline.tare(2400));
  feed_constant(pipeline, 3000, 2500, 25);
  std::string reason;
  TEST_ASSERT_TRUE(pipeline.calibrate(20, 4900, reason));
  feed_constant(pipeline, 5200, 5000, 25);
  const Measurement result = pipeline.evaluate(7400);
  TEST_ASSERT_EQUAL_STRING("stable", state_name(result.state));
  TEST_ASSERT_EQUAL_INT64(42, *result.estimated_count);
  TEST_ASSERT_EQUAL_INT64(3, MeasurementPipeline::round_ties_away(2.5));
  TEST_ASSERT_EQUAL_INT64(-3, MeasurementPipeline::round_ties_away(-2.5));
}

void calibration_guards_preserve_last_valid_record() {
  MeasurementPipeline pipeline(configuration());
  pipeline.set_scale(0.01);
  feed_constant(pipeline, 1000, 0, 25);
  TEST_ASSERT_TRUE(pipeline.tare(2400));
  feed_constant(pipeline, 1100, 2500, 25);
  std::string reason;
  TEST_ASSERT_FALSE(pipeline.calibrate(9, 4900, reason));
  TEST_ASSERT_EQUAL_STRING("known_count_too_small", reason.c_str());
  TEST_ASSERT_FALSE(pipeline.calibration().valid);
}

void fresh_device_calibration_derives_scale_from_known_mass_and_preserves_failures() {
  MeasurementPipeline pipeline(configuration());
  feed_constant(pipeline, 1000, 0, 25);
  TEST_ASSERT_TRUE(pipeline.tare(2400));
  feed_constant(pipeline, 3000, 2500, 25);
  std::string reason;
  TEST_ASSERT_FALSE(pipeline.calibrate(20, 4900, reason));
  TEST_ASSERT_EQUAL_STRING("known_sample_mass_required", reason.c_str());
  TEST_ASSERT_FALSE(pipeline.calibration().valid);
  TEST_ASSERT_TRUE(pipeline.calibrate(20, 4900, reason, 50.0));
  TEST_ASSERT_TRUE(std::abs(pipeline.calibration().grams_per_code - 0.025) < 0.000001);
  TEST_ASSERT_TRUE(std::abs(pipeline.calibration().unit_mass_grams - 2.5) < 0.000001);
  const Calibration valid = pipeline.calibration();
  TEST_ASSERT_FALSE(pipeline.calibrate(9, 4900, reason,
                                       std::numeric_limits<double>::infinity()));
  TEST_ASSERT_EQUAL_MEMORY(&valid, &pipeline.calibration(), sizeof(Calibration));

  MeasurementPipeline noisy(configuration());
  feed_constant(noisy, 1000, 0, 25);
  TEST_ASSERT_TRUE(noisy.tare(2400));
  feed_constant(noisy, 1100, 2500, 25);
  TEST_ASSERT_FALSE(noisy.calibrate(10, 4900, reason, 10.0));
  TEST_ASSERT_EQUAL_STRING("unit_mass_below_noise_floor", reason.c_str());
  TEST_ASSERT_FALSE(noisy.calibration().valid);
}

void old_outliers_age_out_and_stability_recovers() {
  MeasurementPipeline pipeline(configuration());
  feed_constant(pipeline, 1000, 0, 25);
  for (int index = 0; index < 8; ++index) {
    const std::uint64_t time = 2500 + static_cast<std::uint64_t>(index) * 200;
    pipeline.ingest({1200, time, SensorFault::none}, time);
    pipeline.ingest({1000, time + 100, SensorFault::none}, time + 100);
  }
  TEST_ASSERT_TRUE(pipeline.evaluate(4000).diagnostics.outlier_rate > 0.20);
  feed_constant(pipeline, 1000, 4100, 25);
  const Measurement recovered = pipeline.evaluate(6500);
  TEST_ASSERT_TRUE(std::abs(recovered.diagnostics.outlier_rate) < 0.001);
  TEST_ASSERT_EQUAL_STRING("uncalibrated", state_name(recovered.state));
}

}  // namespace

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(zero_stream_becomes_stable_but_uncalibrated);
  RUN_TEST(sustained_step_restarts_dwell_and_recovers);
  RUN_TEST(vibration_never_claims_a_count);
  RUN_TEST(drift_and_creep_withhold_stability);
  RUN_TEST(disconnect_saturation_overload_and_stale_are_explicit);
  RUN_TEST(calibration_and_rounding_are_deterministic);
  RUN_TEST(calibration_guards_preserve_last_valid_record);
  RUN_TEST(fresh_device_calibration_derives_scale_from_known_mass_and_preserves_failures);
  RUN_TEST(old_outliers_age_out_and_stability_recovers);
  return UNITY_END();
}
