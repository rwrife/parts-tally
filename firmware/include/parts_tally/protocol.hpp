#pragma once
#include <cstdint>
#include <deque>
#include <functional>
#include <optional>
#include <string>

#include "parts_tally/interfaces.hpp"
#include "parts_tally/measurement.hpp"
#include "parts_tally/persistence.hpp"

namespace parts_tally {
enum class AuthScope { none, setup, authenticated };
struct Session {
  std::string token;
  AuthScope scope{AuthScope::none};
  std::uint64_t expires_ms{};
};

struct ValidationResult {
  bool ok{};
  int status{};
  std::string code;
};

class ProtocolGuard {
 public:
  explicit ProtocolGuard(std::string allowed_origin);
  Session open_setup_session(bool physical_button_pressed, std::uint64_t now_ms,
                             const std::string& nonce) const;
  ValidationResult validate(const TransportRequest& request, const Session& session,
                            std::uint64_t now_ms, bool mutating) const;
  bool origin_allowed(const std::string& origin) const { return origin == allowed_origin_; }
  bool remember_idempotency(const std::string& key, const std::string& fingerprint,
                            TransportResponse response);
  const TransportResponse* replay(const std::string& key, const std::string& fingerprint,
                                  bool& conflict) const;
  static std::string redact(const std::string& text);

 private:
  struct IdempotencyRecord {
    std::string key;
    std::string fingerprint;
    TransportResponse response;
  };
  std::string allowed_origin_;
  std::deque<IdempotencyRecord> ids_;
};

class EventSequencer {
 public:
  std::uint64_t next() { return ++sequence_; }
  bool gap(std::uint64_t received) const { return received != sequence_ + 1; }
  void accept(std::uint64_t sequence) { sequence_ = sequence; }

 private:
  std::uint64_t sequence_{};
};

class ApiService {
 public:
  using PersistCallback = std::function<bool()>;
  using TokenCallback = std::function<std::string()>;
  using ProvisionedCallback = std::function<void(const std::string&, const std::string&)>;

  ApiService(std::string device_id, ProtocolGuard& guard, MeasurementPipeline& measurement,
             PersistentState& state, PersistCallback persist, TokenCallback token,
             ProvisionedCallback provisioned = {});

  void set_session(Session session);
  const Session& session() const;
  bool authorize_event_token(const std::string& token, std::uint64_t now_ms,
                             std::uint64_t& expires_ms) const;
  bool record_stable_count(const std::string& profile_id, const Measurement& measurement,
                           std::uint64_t now_ms);
  TransportResponse handle(const TransportRequest& request, std::uint64_t now_ms);
  std::string event(const std::string& type, const std::string& payload_json, std::uint64_t now_ms);

 private:
  bool is_mutating(const TransportRequest& request) const;
  TransportResponse dispatch(const TransportRequest& request, std::uint64_t now_ms);
  TransportResponse error(int status, const std::string& code, const std::string& message) const;

  std::string device_id_;
  ProtocolGuard& guard_;
  MeasurementPipeline& measurement_;
  PersistentState& state_;
  PersistCallback persist_;
  TokenCallback token_;
  ProvisionedCallback provisioned_;
  Session setup_session_;
  Session authenticated_session_;
  EventSequencer events_;
  std::string import_preview_token_;
  std::string import_preview_payload_;
  std::string import_preview_session_token_;
  std::uint64_t import_preview_expires_ms_{};
  std::optional<std::int64_t> last_recorded_count_;
  std::string last_recorded_profile_id_;
};
}  // namespace parts_tally
