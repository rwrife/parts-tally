#pragma once
#include <cstddef>
#include <cstdint>
#include <deque>
#include <optional>
#include <string>
#include <vector>

#include "parts_tally/interfaces.hpp"

namespace parts_tally {
enum class MeasurementState {
  stable,
  uncalibrated,
  unstable,
  stale,
  disconnected,
  saturated,
  overload_indicated,
  below_tare,
  calibration_invalid,
  uncertainty_excessive
};
const char* state_name(MeasurementState state);

struct MeasurementConfig {
  std::size_t window_samples{25}, minimum_samples{20};
  std::uint64_t minimum_dwell_ms{2000}, stale_after_ms{500};
  double max_noise_codes{8}, max_abs_slope_codes_per_second{2}, max_outlier_rate{0.20};
  double outlier_threshold_codes{30}, step_accept_count{3}, zero_band_grams{0.05};
  double overload_abs_codes{8000000}, characterized_resolution_floor_grams{0.02};
  int max_uncertainty_pieces{3};
};
struct Calibration {
  std::uint32_t schema_version{2};
  bool tare_valid{false}, valid{false}, provisional{true};
  double tare_code{}, grams_per_code{}, unit_mass_grams{}, unit_uncertainty_grams{},
      calibration_residual_grams{};
  std::uint32_t known_count{};
  std::uint64_t created_ms{};
};
struct Diagnostics {
  double noise_p95_p5_codes{}, slope_codes_per_second{}, outlier_rate{};
  std::uint64_t sample_age_ms{};
  std::size_t accepted_samples{};
};
struct Measurement {
  MeasurementState state{MeasurementState::uncalibrated};
  bool stable{};
  double filtered_code{}, net_grams{};
  std::optional<std::int64_t> estimated_count;
  std::optional<int> uncertainty_pieces;
  Diagnostics diagnostics;
};

class MeasurementPipeline {
 public:
  explicit MeasurementPipeline(MeasurementConfig config = {});
  Measurement ingest(const AdcSample& sample, std::uint64_t now_ms);
  Measurement evaluate(std::uint64_t now_ms) const;
  bool tare(std::uint64_t now_ms);
  bool calibrate(std::uint32_t known_count, std::uint64_t now_ms, std::string& reason,
                 std::optional<double> known_sample_mass_grams = std::nullopt);
  void set_scale(double grams_per_code);
  void set_calibration(const Calibration& calibration);
  const Calibration& calibration() const { return calibration_; }
  static std::int64_t round_ties_away(double value);

 private:
  struct Point {
    double value;
    std::uint64_t ms;
  };
  struct Observation {
    bool outlier;
  };
  MeasurementConfig config_;
  Calibration calibration_;
  std::deque<Point> window_;
  std::deque<Observation> observations_;
  SensorFault fault_{SensorFault::none};
  std::uint64_t last_sample_ms_{}, dwell_start_ms_{};
  double filtered_{};
  int pending_step_{};
  bool have_sample_{false};
  Diagnostics diagnostics(std::uint64_t now_ms) const;
  bool stationary(std::uint64_t now_ms, const Diagnostics& d) const;
};
}  // namespace parts_tally
