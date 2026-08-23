#include "parts_tally/measurement.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

namespace parts_tally {
const char* state_name(MeasurementState s) {
  static const char* names[] = {"stable",
                                "uncalibrated",
                                "unstable",
                                "stale",
                                "disconnected",
                                "saturated",
                                "overload_indicated",
                                "below_tare",
                                "calibration_invalid",
                                "uncertainty_excessive"};
  return names[static_cast<unsigned>(s)];
}
MeasurementPipeline::MeasurementPipeline(MeasurementConfig config) : config_(config) {
  config_.minimum_samples = std::max<std::size_t>(20, config_.minimum_samples);
  config_.minimum_dwell_ms = std::max<std::uint64_t>(2000, config_.minimum_dwell_ms);
  config_.window_samples = std::max(config_.window_samples, config_.minimum_samples);
}
void MeasurementPipeline::set_scale(double v) { calibration_.grams_per_code = v; }
void MeasurementPipeline::set_calibration(const Calibration& c) { calibration_ = c; }

Diagnostics MeasurementPipeline::diagnostics(std::uint64_t now) const {
  Diagnostics d{};
  d.accepted_samples = window_.size();
  d.sample_age_ms =
      have_sample_ ? now - last_sample_ms_ : std::numeric_limits<std::uint64_t>::max();
  if (window_.empty()) return d;
  std::vector<double> values;
  values.reserve(window_.size());
  for (const auto& p : window_) values.push_back(p.value);
  std::sort(values.begin(), values.end());
  auto pct = [&](double q) {
    double x = q * (values.size() - 1);
    auto lo = static_cast<std::size_t>(x);
    auto hi = std::min(lo + 1, values.size() - 1);
    return values[lo] + (values[hi] - values[lo]) * (x - lo);
  };
  d.noise_p95_p5_codes = pct(.95) - pct(.05);
  const std::size_t outliers = static_cast<std::size_t>(
      std::count_if(observations_.begin(), observations_.end(),
                    [](const Observation& observation) { return observation.outlier; }));
  d.outlier_rate = observations_.empty()
                       ? 0
                       : static_cast<double>(outliers) / observations_.size();
  double mt = 0, mv = 0;
  for (const auto& p : window_) {
    mt += static_cast<double>(p.ms);
    mv += p.value;
  }
  mt /= window_.size();
  mv /= window_.size();
  double num = 0, den = 0;
  for (const auto& p : window_) {
    double t = static_cast<double>(p.ms) - mt;
    num += t * (p.value - mv);
    den += t * t;
  }
  d.slope_codes_per_second = den ? 1000 * num / den : 0;
  return d;
}
bool MeasurementPipeline::stationary(std::uint64_t now, const Diagnostics& d) const {
  return fault_ == SensorFault::none && d.accepted_samples >= config_.minimum_samples &&
         now >= dwell_start_ms_ + config_.minimum_dwell_ms &&
         d.noise_p95_p5_codes <= config_.max_noise_codes &&
         std::abs(d.slope_codes_per_second) <= config_.max_abs_slope_codes_per_second &&
         d.outlier_rate <= config_.max_outlier_rate;
}

Measurement MeasurementPipeline::ingest(const AdcSample& sample, std::uint64_t now) {
  fault_ = sample.fault;
  last_sample_ms_ = sample.monotonic_ms;
  have_sample_ = true;
  if (fault_ != SensorFault::none ||
      std::abs(static_cast<double>(sample.code)) >= config_.overload_abs_codes) {
    if (fault_ == SensorFault::none) fault_ = SensorFault::overload_indicated;
    window_.clear();
    observations_.clear();
    dwell_start_ms_ = now;
    return evaluate(now);
  }
  double x = sample.code;
  if (window_.empty()) {
    filtered_ = x;
    dwell_start_ms_ = sample.monotonic_ms;
  } else if (std::abs(x - filtered_) > config_.outlier_threshold_codes) {
    observations_.push_back({true});
    while (observations_.size() > config_.window_samples) observations_.pop_front();
    ++pending_step_;
    if (pending_step_ >= config_.step_accept_count) {
      window_.clear();
      observations_.clear();
      pending_step_ = 0;
      filtered_ = x;
      dwell_start_ms_ = sample.monotonic_ms;
    } else
      return evaluate(now);
  } else {
    observations_.push_back({false});
    pending_step_ = 0;
    filtered_ = x;
  }
  window_.push_back({filtered_, sample.monotonic_ms});
  while (window_.size() > config_.window_samples) window_.pop_front();
  while (observations_.size() > config_.window_samples) observations_.pop_front();
  return evaluate(now);
}
Measurement MeasurementPipeline::evaluate(std::uint64_t now) const {
  Measurement m{};
  m.filtered_code = filtered_;
  m.diagnostics = diagnostics(now);
  if (!have_sample_ || m.diagnostics.sample_age_ms > config_.stale_after_ms)
    m.state = MeasurementState::stale;
  else if (fault_ == SensorFault::disconnected)
    m.state = MeasurementState::disconnected;
  else if (fault_ == SensorFault::saturated)
    m.state = MeasurementState::saturated;
  else if (fault_ == SensorFault::overload_indicated)
    m.state = MeasurementState::overload_indicated;
  else if (!stationary(now, m.diagnostics))
    m.state = MeasurementState::unstable;
  else if (!calibration_.tare_valid || !std::isfinite(calibration_.grams_per_code) ||
           calibration_.grams_per_code == 0)
    m.state = MeasurementState::uncalibrated;
  else if (calibration_.schema_version != 2 || !calibration_.valid ||
           !std::isfinite(calibration_.unit_mass_grams) || calibration_.unit_mass_grams <= 0)
    m.state = MeasurementState::calibration_invalid;
  else {
    m.net_grams = (filtered_ - calibration_.tare_code) * calibration_.grams_per_code;
    if (m.net_grams < -config_.zero_band_grams)
      m.state = MeasurementState::below_tare;
    else {
      if (std::abs(m.net_grams) <= config_.zero_band_grams) m.net_grams = 0;
      double b = m.diagnostics.noise_p95_p5_codes * std::abs(calibration_.grams_per_code);
      double drift = std::abs(m.diagnostics.slope_codes_per_second) * 2 *
                     std::abs(calibration_.grams_per_code);
      double um = std::max({b, drift, calibration_.calibration_residual_grams});
      int uq = static_cast<int>(
          std::ceil(um / calibration_.unit_mass_grams +
                    std::abs(m.net_grams) * calibration_.unit_uncertainty_grams /
                        (calibration_.unit_mass_grams * calibration_.unit_mass_grams) +
                    .5));
      if (uq > config_.max_uncertainty_pieces)
        m.state = MeasurementState::uncertainty_excessive;
      else {
        m.state = MeasurementState::stable;
        m.stable = true;
        m.estimated_count = round_ties_away(m.net_grams / calibration_.unit_mass_grams);
        m.uncertainty_pieces = uq;
      }
    }
  }
  return m;
}
bool MeasurementPipeline::tare(std::uint64_t now) {
  auto m = evaluate(now);
  if (m.state != MeasurementState::unstable && m.state != MeasurementState::stale &&
      m.state != MeasurementState::disconnected && m.state != MeasurementState::saturated &&
      m.state != MeasurementState::overload_indicated) {
    calibration_.tare_code = filtered_;
    calibration_.tare_valid = true;
    calibration_.valid = false;
    return true;
  }
  return false;
}
bool MeasurementPipeline::calibrate(std::uint32_t n, std::uint64_t now, std::string& reason,
                                    std::optional<double> known_mass) {
  auto d = diagnostics(now);
  if (!calibration_.tare_valid) {
    reason = "tare_required";
    return false;
  }
  if (n < 10) {
    reason = "known_count_too_small";
    return false;
  }
  if (!stationary(now, d)) {
    reason = "measurement_unstable";
    return false;
  }
  const double delta = filtered_ - calibration_.tare_code;
  double scale = calibration_.grams_per_code;
  if (!std::isfinite(scale) || scale == 0) {
    if (!known_mass || !std::isfinite(*known_mass) || *known_mass <= 0 || delta == 0) {
      reason = "known_sample_mass_required";
      return false;
    }
    scale = *known_mass / delta;
  }
  double mass = delta * scale;
  double unit = mass / n;
  double band = d.noise_p95_p5_codes * std::abs(scale);
  if (!std::isfinite(unit) || mass <= 0 ||
      unit < std::max(20 * band, config_.characterized_resolution_floor_grams)) {
    reason = "unit_mass_below_noise_floor";
    return false;
  }
  Calibration next = calibration_;
  next.grams_per_code = scale;
  next.valid = true;
  next.provisional = true;
  next.unit_mass_grams = unit;
  next.unit_uncertainty_grams = std::max(band / static_cast<double>(n), unit * .01);
  next.calibration_residual_grams = band;
  next.known_count = n;
  next.created_ms = now;
  calibration_ = next;
  reason.clear();
  return true;
}
std::int64_t MeasurementPipeline::round_ties_away(double v) {
  return v >= 0 ? static_cast<std::int64_t>(std::floor(v + .5))
                : static_cast<std::int64_t>(std::ceil(v - .5));
}
}  // namespace parts_tally
