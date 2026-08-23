#include "parts_tally/persistence.hpp"

#include <algorithm>
#include <cmath>
#include <cctype>
#include <cstring>
#include <iomanip>
#include <limits>
#include <set>
#include <sstream>

namespace parts_tally {
namespace {
constexpr char magic[] = "PTDB";
constexpr std::uint32_t current = 3;
std::uint32_t checksum(const std::vector<std::uint8_t>& v, std::size_t n) {
  std::uint32_t h = 2166136261u;
  for (std::size_t i = 0; i < n; i++) {
    h ^= v[i];
    h *= 16777619u;
  }
  return h;
}
template <class T>
void put(std::vector<std::uint8_t>& v, T x) {
  auto* p = reinterpret_cast<const std::uint8_t*>(&x);
  v.insert(v.end(), p, p + sizeof x);
}
void putstr(std::vector<std::uint8_t>& v, const std::string& s) {
  put<std::uint32_t>(v, s.size());
  v.insert(v.end(), s.begin(), s.end());
}
struct Reader {
  const std::vector<std::uint8_t>& v;
  std::size_t p{};
  template <class T>
  bool get(T& x) {
    if (p + sizeof x > v.size()) return false;
    std::memcpy(&x, v.data() + p, sizeof x);
    p += sizeof x;
    return true;
  }
  bool str(std::string& s) {
    std::uint32_t n;
    if (!get(n) || n > 4096 || p + n > v.size()) return false;
    s.assign(reinterpret_cast<const char*>(v.data() + p), n);
    p += n;
    return true;
  }
};
std::string esc(const std::string& s) {
  std::ostringstream o;
  for (char c : s) {
    if (c == '"' || c == '\\')
      o << '\\' << c;
    else if (static_cast<unsigned char>(c) < 32)
      o << '?';
    else
      o << c;
  }
  return o.str();
}
bool sane(const Calibration& c) {
  return c.schema_version == 2 && std::isfinite(c.tare_code) && std::isfinite(c.grams_per_code) &&
         std::isfinite(c.unit_mass_grams) &&
         (!c.valid || (c.tare_valid && c.grams_per_code != 0 && c.unit_mass_grams > 0));
}
bool identifier(const std::string& value, std::size_t maximum) {
  if (value.empty() || value.size() > maximum) return false;
  return std::all_of(value.begin(), value.end(), [](unsigned char character) {
    return std::isalnum(character) || character == '_' || character == '-';
  });
}
}  // namespace
bool Persistence::save(const PersistentState& s) {
  std::vector<std::uint8_t> v(magic, magic + 4);
  put(v, current);
  putstr(v, s.device_name);
  putstr(v, s.wifi_ssid);
  putstr(v, s.wifi_password);
  putstr(v, s.device_secret);
  put<std::uint32_t>(v, s.profiles.size());
  for (const auto& p : s.profiles) {
    putstr(v, p.id);
    putstr(v, p.name);
    put(v, p.low_stock_threshold);
    const auto& c = p.calibration;
    put(v, c.schema_version);
    put(v, c.tare_valid);
    put(v, c.valid);
    put(v, c.provisional);
    put(v, c.tare_code);
    put(v, c.grams_per_code);
    put(v, c.unit_mass_grams);
    put(v, c.unit_uncertainty_grams);
    put(v, c.calibration_residual_grams);
    put(v, c.known_count);
    put(v, c.created_ms);
  }
  auto start = s.history.size() > history_limit_ ? s.history.size() - history_limit_ : 0;
  put<std::uint32_t>(v, s.history.size() - start);
  for (std::size_t i = start; i < s.history.size(); i++) {
    const auto& h = s.history[i];
    put(v, h.sequence);
    put(v, h.monotonic_ms);
    putstr(v, h.profile_id);
    putstr(v, h.kind);
    putstr(v, h.event_id);
    putstr(v, h.reason);
    put(v, h.count);
    putstr(v, h.related_event_id);
  }
  put(v, checksum(v, v.size()));
  return storage_.replace_atomically("state", v);
}
LoadResult Persistence::load(PersistentState& s) {
  std::vector<std::uint8_t> v;
  if (!storage_.read("state", v)) return LoadResult::empty;
  if (v.size() < 12 || std::memcmp(v.data(), magic, 4) != 0) return LoadResult::corrupt;
  std::uint32_t stored;
  std::memcpy(&stored, v.data() + v.size() - 4, 4);
  if (stored != checksum(v, v.size() - 4)) return LoadResult::corrupt;
  Reader r{v, 4};
  std::uint32_t version;
  if (!r.get(version)) return LoadResult::corrupt;
  if (version < 1 || version > current) return LoadResult::unsupported;
  PersistentState candidate;
  if (!r.str(candidate.device_name)) return LoadResult::corrupt;
  if (version >= 3 && (!r.str(candidate.wifi_ssid) || !r.str(candidate.wifi_password) ||
                       !r.str(candidate.device_secret))) {
    return LoadResult::corrupt;
  }
  std::uint32_t pc;
  if (!r.get(pc) || pc > 128) return LoadResult::corrupt;
  std::set<std::string> profile_ids;
  for (std::uint32_t i = 0; i < pc; i++) {
    Profile p;
    if (!r.str(p.id) || !r.str(p.name) || !r.get(p.low_stock_threshold)) return LoadResult::corrupt;
    auto& c = p.calibration;
    if (version == 1)
      c.schema_version = 2;
    else if (!r.get(c.schema_version))
      return LoadResult::corrupt;
    if (!r.get(c.tare_valid) || !r.get(c.valid) || !r.get(c.provisional) || !r.get(c.tare_code) ||
        !r.get(c.grams_per_code) || !r.get(c.unit_mass_grams) || !r.get(c.unit_uncertainty_grams) ||
        !r.get(c.calibration_residual_grams) || !r.get(c.known_count) || !r.get(c.created_ms) ||
        !sane(c))
      return LoadResult::corrupt;
    if (!identifier(p.id, 64) || p.name.empty() || p.name.size() > 80 ||
        p.low_stock_threshold < 0 || !profile_ids.insert(p.id).second) {
      return LoadResult::corrupt;
    }
    candidate.profiles.push_back(p);
  }
  std::uint32_t hc;
  if (!r.get(hc) || hc > history_limit_) return LoadResult::corrupt;
  std::uint64_t previous_sequence{};
  std::set<std::string> event_ids;
  for (std::uint32_t i = 0; i < hc; i++) {
    HistoryEntry h;
    if (!r.get(h.sequence) || !r.get(h.monotonic_ms) || !r.str(h.profile_id) || !r.str(h.kind) ||
        (version >= 3 && (!r.str(h.event_id) || !r.str(h.reason))) || !r.get(h.count) ||
        (version >= 3 && !r.str(h.related_event_id)) || h.sequence <= previous_sequence ||
        h.count < 0 || (h.kind != "count" && h.kind != "correction")) {
      return LoadResult::corrupt;
    }
    if (profile_ids.count(h.profile_id) == 0) return LoadResult::corrupt;
    if (version < 3) {
      h.event_id = (h.kind == "count" ? "count-" : "correction-") +
                   std::to_string(h.sequence);
      if (h.kind == "correction") {
        auto source = std::find_if(candidate.history.rbegin(), candidate.history.rend(),
                                   [&](const HistoryEntry& prior) {
                                     return prior.kind == "count" &&
                                            prior.profile_id == h.profile_id;
                                   });
        if (source == candidate.history.rend()) return LoadResult::corrupt;
        h.related_event_id = source->event_id;
        h.reason = "legacy migration: reason unavailable";
      }
    }
    if (!identifier(h.event_id, 128) || h.reason.size() > 200 ||
        !event_ids.insert(h.event_id).second ||
        (h.kind == "count" && !h.related_event_id.empty()) ||
        (h.kind == "correction" &&
         (h.reason.empty() || !identifier(h.related_event_id, 128) ||
          std::none_of(candidate.history.begin(), candidate.history.end(),
                       [&](const HistoryEntry& prior) {
                         return prior.kind == "count" && prior.event_id == h.related_event_id &&
                                prior.profile_id == h.profile_id;
                       })))) {
      return LoadResult::corrupt;
    }
    previous_sequence = h.sequence;
    candidate.history.push_back(h);
  }
  if (r.p != v.size() - 4) return LoadResult::corrupt;
  s = candidate;
  if (version < current) {
    if (!save(s)) return LoadResult::corrupt;
    return LoadResult::migrated;
  }
  return LoadResult::ok;
}
void Persistence::append_history(PersistentState& s, HistoryEntry h) const {
  s.history.push_back(std::move(h));
  if (s.history.size() > history_limit_)
    s.history.erase(s.history.begin(), s.history.begin() + (s.history.size() - history_limit_));
}
std::string Persistence::export_json(const PersistentState& s, bool hist) const {
  std::ostringstream o;
  o << "{\"schemaVersion\":3,\"deviceName\":\"" << esc(s.device_name) << "\",\"profiles\":[";
  for (std::size_t i = 0; i < s.profiles.size(); i++) {
    if (i) o << ',';
    const auto& p = s.profiles[i];
    const auto& c = p.calibration;
    o << "{\"id\":\"" << esc(p.id) << "\",\"name\":\"" << esc(p.name)
      << "\",\"lowStockThreshold\":" << p.low_stock_threshold
      << ",\"calibrated\":" << (c.valid ? "true" : "false")
      << ",\"provisional\":" << (c.provisional ? "true" : "false")
      << ",\"calibration\":{\"schemaVersion\":" << c.schema_version
      << ",\"tareValid\":" << (c.tare_valid ? "true" : "false")
      << ",\"valid\":" << (c.valid ? "true" : "false")
      << ",\"provisional\":" << (c.provisional ? "true" : "false")
      << ",\"tareCode\":" << c.tare_code << ",\"gramsPerCode\":" << c.grams_per_code
      << ",\"unitMassGrams\":" << c.unit_mass_grams
      << ",\"unitUncertaintyGrams\":" << c.unit_uncertainty_grams
      << ",\"calibrationResidualGrams\":" << c.calibration_residual_grams
      << ",\"knownCount\":" << c.known_count << ",\"createdMs\":" << c.created_ms << "}}";
  }
  o << ']';
  if (hist) {
    o << ",\"history\":[";
    for (std::size_t i = 0; i < s.history.size(); ++i) {
      if (i) o << ',';
      const auto& h = s.history[i];
      o << "{\"sequence\":" << h.sequence << ",\"deviceUptimeMs\":" << h.monotonic_ms
        << ",\"profileId\":\"" << esc(h.profile_id) << "\",\"kind\":\"" << esc(h.kind)
        << "\",\"eventId\":\"" << esc(h.event_id) << "\",\"reason\":\"" << esc(h.reason)
        << "\",\"count\":" << h.count;
      if (!h.related_event_id.empty())
        o << ",\"relatedEventId\":\"" << esc(h.related_event_id) << '"';
      o << '}';
    }
    o << ']';
  }
  o << '}';
  return o.str();
}
}  // namespace parts_tally
