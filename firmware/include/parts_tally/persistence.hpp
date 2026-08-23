#pragma once
#include <cstdint>
#include <string>
#include <vector>

#include "parts_tally/interfaces.hpp"
#include "parts_tally/measurement.hpp"

namespace parts_tally {
struct Profile {
  std::string id, name;
  Calibration calibration;
  int low_stock_threshold{};
};
struct HistoryEntry {
  std::uint64_t sequence{}, monotonic_ms{};
  std::string profile_id, kind, event_id, reason;
  std::int64_t count{};
  std::string related_event_id;
};
struct PersistentState {
  static constexpr std::uint32_t schema_version = 3;
  std::string device_name{"Parts Tally"};
  std::vector<Profile> profiles;
  std::vector<HistoryEntry> history;
  // Intentionally device-only; never serialized by export_json().
  std::string wifi_ssid, wifi_password, device_secret;
};
enum class LoadResult { ok, empty, migrated, corrupt, unsupported };
class Persistence {
 public:
  explicit Persistence(IStorage& storage, std::size_t history_limit = 256)
      : storage_(storage), history_limit_(history_limit) {}
  bool save(const PersistentState& state);
  LoadResult load(PersistentState& state);
  void append_history(PersistentState& state, HistoryEntry entry) const;
  std::string export_json(const PersistentState& state, bool include_history) const;

 private:
  IStorage& storage_;
  std::size_t history_limit_;
};
}  // namespace parts_tally
