#include "parts_tally/protocol.hpp"

#include <ArduinoJson.h>

#include <algorithm>
#include <cctype>
#include <cmath>
#include <limits>
#include <set>
#include <utility>

namespace parts_tally {
namespace {

constexpr std::size_t kMaximumBodyBytes = 8192;
constexpr std::size_t kMaximumProfiles = 128;
constexpr std::size_t kMaximumHistory = 256;
constexpr std::uint64_t kSessionLifetimeMs = 300000;
constexpr std::uint64_t kImportPreviewLifetimeMs = 30000;

std::string json_string(const JsonDocument& document) {
  std::string output;
  serializeJson(document, output);
  return output;
}

std::string fingerprint(const TransportRequest& request) {
  return request.method + "\n" + request.path + "\n" + request.body;
}

bool valid_identifier(const char* value, std::size_t maximum) {
  if (value == nullptr) return false;
  const std::size_t size = std::char_traits<char>::length(value);
  if (size == 0 || size > maximum) return false;
  return std::all_of(value, value + size, [](char character) {
    const auto byte = static_cast<unsigned char>(character);
    return std::isalnum(byte) || character == '-' || character == '_';
  });
}

bool valid_text(const char* value, std::size_t maximum, bool allow_empty = false) {
  if (value == nullptr) return false;
  const std::size_t size = std::char_traits<char>::length(value);
  return (allow_empty || size != 0) && size <= maximum;
}

bool is_setup_path(const std::string& path) { return path.rfind("/api/v1/setup/", 0) == 0; }

struct HistoryQuery {
  std::uint64_t after{};
  std::size_t limit{50};
};

bool unsigned_decimal(const std::string& value, std::uint64_t maximum, std::uint64_t& parsed) {
  if (value.empty()) return false;
  std::uint64_t result = 0;
  for (char character : value) {
    if (character < '0' || character > '9') return false;
    const std::uint64_t digit = static_cast<std::uint64_t>(character - '0');
    if (result > (maximum - digit) / 10) return false;
    result = result * 10 + digit;
  }
  parsed = result;
  return true;
}

bool parse_history_query(const std::string& path, HistoryQuery& query) {
  constexpr const char* base = "/api/v1/history";
  if (path == base) return true;
  const std::string prefix = std::string(base) + '?';
  if (path.rfind(prefix, 0) != 0) return false;
  const std::string parameters = path.substr(prefix.size());
  if (parameters.empty() || parameters.find('#') != std::string::npos) return false;
  bool have_after = false;
  bool have_limit = false;
  std::size_t start = 0;
  while (start <= parameters.size()) {
    const std::size_t end = parameters.find('&', start);
    const std::string parameter = parameters.substr(start, end - start);
    const std::size_t equals = parameter.find('=');
    if (equals == std::string::npos || equals == 0 ||
        parameter.find('=', equals + 1) != std::string::npos)
      return false;
    const std::string name = parameter.substr(0, equals);
    const std::string value = parameter.substr(equals + 1);
    std::uint64_t parsed = 0;
    if (name == "after") {
      if (have_after || !unsigned_decimal(value, std::numeric_limits<std::uint64_t>::max(), parsed))
        return false;
      query.after = parsed;
      have_after = true;
    } else if (name == "limit") {
      if (have_limit || !unsigned_decimal(value, 100, parsed) || parsed == 0) return false;
      query.limit = static_cast<std::size_t>(parsed);
      have_limit = true;
    } else {
      return false;
    }
    if (end == std::string::npos) break;
    start = end + 1;
  }
  return true;
}

bool exact_profile_path(const std::string& path, std::string& id) {
  constexpr const char* prefix = "/api/v1/profiles/";
  if (path.rfind(prefix, 0) != 0) return false;
  id = path.substr(std::char_traits<char>::length(prefix));
  return valid_identifier(id.c_str(), 64);
}

bool exact_correction_path(const std::string& path, std::string& event_id) {
  constexpr const char* prefix = "/api/v1/counts/";
  constexpr const char* suffix = "/correction";
  const std::size_t prefix_size = std::char_traits<char>::length(prefix);
  const std::size_t suffix_size = std::char_traits<char>::length(suffix);
  if (path.rfind(prefix, 0) != 0 || path.size() <= prefix_size + suffix_size ||
      path.compare(path.size() - suffix_size, suffix_size, suffix) != 0) {
    return false;
  }
  event_id = path.substr(prefix_size, path.size() - prefix_size - suffix_size);
  return valid_identifier(event_id.c_str(), 128);
}

bool only_keys(JsonObjectConst object, std::initializer_list<const char*> allowed) {
  for (JsonPairConst pair : object) {
    bool found = false;
    for (const char* key : allowed) found = found || pair.key() == key;
    if (!found) return false;
  }
  return true;
}

Profile* find_profile(PersistentState& state, const std::string& id) {
  auto found = std::find_if(state.profiles.begin(), state.profiles.end(),
                            [&](const Profile& profile) { return profile.id == id; });
  return found == state.profiles.end() ? nullptr : &*found;
}

std::string unique_event_id(const PersistentState& state, const std::string& prefix,
                            std::uint64_t sequence) {
  std::string candidate = prefix + '-' + std::to_string(sequence);
  for (std::uint64_t suffix = 1;
       std::any_of(state.history.begin(), state.history.end(),
                   [&](const HistoryEntry& entry) { return entry.event_id == candidate; });
       ++suffix) {
    candidate = prefix + '-' + std::to_string(sequence) + '-' + std::to_string(suffix);
  }
  return candidate;
}

void add_calibration(JsonObject object, const Calibration& calibration) {
  object["schemaVersion"] = calibration.schema_version;
  object["tareValid"] = calibration.tare_valid;
  object["valid"] = calibration.valid;
  object["provisional"] = calibration.provisional;
  object["tareCode"] = calibration.tare_code;
  object["gramsPerCode"] = calibration.grams_per_code;
  object["unitMassGrams"] = calibration.unit_mass_grams;
  object["unitUncertaintyGrams"] = calibration.unit_uncertainty_grams;
  object["calibrationResidualGrams"] = calibration.calibration_residual_grams;
  object["knownCount"] = calibration.known_count;
  object["createdMs"] = calibration.created_ms;
}

void add_profile(JsonObject object, const Profile& profile, bool full) {
  object["id"] = profile.id;
  object["name"] = profile.name;
  object["lowStockThreshold"] = profile.low_stock_threshold;
  object["calibrated"] = profile.calibration.valid;
  object["provisional"] = profile.calibration.provisional;
  if (full) add_calibration(object["calibration"].to<JsonObject>(), profile.calibration);
}

void add_history(JsonObject object, const HistoryEntry& entry) {
  object["sequence"] = entry.sequence;
  object["deviceUptimeMs"] = entry.monotonic_ms;
  object["profileId"] = entry.profile_id;
  object["kind"] = entry.kind;
  object["eventId"] = entry.event_id;
  object["reason"] = entry.reason;
  object["count"] = entry.count;
  if (!entry.related_event_id.empty()) object["relatedEventId"] = entry.related_event_id;
}

bool has_secret_key(JsonVariantConst value) {
  if (value.is<JsonObjectConst>()) {
    for (JsonPairConst pair : value.as<JsonObjectConst>()) {
      const std::string key = pair.key().c_str();
      if (key == "wifiSsid" || key == "wifiPassword" || key == "wifiSecret" ||
          key == "deviceSecret" || key == "sessionToken" || key == "token" ||
          key == "authorization" || has_secret_key(pair.value())) {
        return true;
      }
    }
  } else if (value.is<JsonArrayConst>()) {
    for (JsonVariantConst item : value.as<JsonArrayConst>()) {
      if (has_secret_key(item)) return true;
    }
  }
  return false;
}

void redact_secrets(JsonVariant value) {
  static const std::set<std::string> keys = {"password",    "wifiPassword",  "wifiSecret",
                                             "wifi_secret", "deviceSecret",  "device_secret",
                                             "token",       "authorization", "sessionToken"};
  if (value.is<JsonObject>()) {
    for (JsonPair pair : value.as<JsonObject>()) {
      if (keys.count(pair.key().c_str()) != 0)
        pair.value().set("[REDACTED]");
      else
        redact_secrets(pair.value());
    }
  } else if (value.is<JsonArray>()) {
    for (JsonVariant item : value.as<JsonArray>()) redact_secrets(item);
  }
}

bool parse_calibration(JsonObjectConst object, Calibration& calibration) {
  if (object.isNull() || object["schemaVersion"] != 2 ||
      !only_keys(object, {"schemaVersion", "tareValid", "valid", "provisional", "tareCode",
                          "gramsPerCode", "unitMassGrams", "unitUncertaintyGrams",
                          "calibrationResidualGrams", "knownCount", "createdMs"}) ||
      !object["tareValid"].is<bool>() || !object["valid"].is<bool>() ||
      !object["provisional"].is<bool>() || !object["tareCode"].is<double>() ||
      !object["gramsPerCode"].is<double>() || !object["unitMassGrams"].is<double>() ||
      !object["unitUncertaintyGrams"].is<double>() ||
      !object["calibrationResidualGrams"].is<double>() ||
      !object["knownCount"].is<std::uint32_t>() || !object["createdMs"].is<std::uint64_t>()) {
    return false;
  }
  calibration.schema_version = 2;
  calibration.tare_valid = object["tareValid"] | false;
  calibration.valid = object["valid"] | false;
  calibration.provisional = object["provisional"] | true;
  calibration.tare_code = object["tareCode"] | 0.0;
  calibration.grams_per_code = object["gramsPerCode"] | 0.0;
  calibration.unit_mass_grams = object["unitMassGrams"] | 0.0;
  calibration.unit_uncertainty_grams = object["unitUncertaintyGrams"] | 0.0;
  calibration.calibration_residual_grams = object["calibrationResidualGrams"] | 0.0;
  calibration.known_count = object["knownCount"] | 0U;
  calibration.created_ms = object["createdMs"] | 0ULL;
  if (!std::isfinite(calibration.tare_code) || !std::isfinite(calibration.grams_per_code) ||
      !std::isfinite(calibration.unit_mass_grams) ||
      !std::isfinite(calibration.unit_uncertainty_grams) ||
      !std::isfinite(calibration.calibration_residual_grams) || calibration.unit_mass_grams < 0 ||
      calibration.unit_uncertainty_grams < 0 || calibration.calibration_residual_grams < 0) {
    return false;
  }
  return !calibration.valid || (calibration.tare_valid && calibration.grams_per_code != 0 &&
                                calibration.unit_mass_grams > 0 && calibration.known_count >= 10);
}

bool parse_import(JsonObjectConst imported, PersistentState& replacement) {
  if (imported.isNull() || imported["schemaVersion"] != 3 || has_secret_key(imported) ||
      !only_keys(imported, {"schemaVersion", "deviceName", "profiles", "history"}))
    return false;
  const char* device_name = imported["deviceName"];
  if (!valid_text(device_name, 80)) return false;
  replacement.device_name = device_name;
  JsonArrayConst profiles = imported["profiles"].as<JsonArrayConst>();
  JsonArrayConst history = imported["history"].as<JsonArrayConst>();
  if (profiles.isNull() || history.isNull() || profiles.size() > kMaximumProfiles ||
      history.size() > kMaximumHistory) {
    return false;
  }
  std::set<std::string> profile_ids;
  for (JsonObjectConst item : profiles) {
    const char* id = item["id"];
    const char* name = item["name"];
    Profile profile;
    if (!only_keys(item, {"id", "name", "lowStockThreshold", "calibrated", "provisional",
                          "calibration"}) ||
        !valid_identifier(id, 64) || !valid_text(name, 80) || !item["calibrated"].is<bool>() ||
        !item["provisional"].is<bool>() || !item["lowStockThreshold"].is<int>() ||
        item["lowStockThreshold"].as<int>() < 0 ||
        !parse_calibration(item["calibration"].as<JsonObjectConst>(), profile.calibration)) {
      return false;
    }
    if (!profile_ids.insert(id).second ||
        item["calibrated"].as<bool>() != profile.calibration.valid ||
        item["provisional"].as<bool>() != profile.calibration.provisional) {
      return false;
    }
    profile.id = id;
    profile.name = name;
    profile.low_stock_threshold = item["lowStockThreshold"];
    replacement.profiles.push_back(std::move(profile));
  }
  std::uint64_t previous_sequence = 0;
  std::set<std::string> event_ids;
  for (JsonObjectConst item : history) {
    HistoryEntry entry;
    const char* profile_id = item["profileId"];
    const char* kind = item["kind"];
    const char* event_id = item["eventId"];
    const char* reason = item["reason"];
    const char* related_event_id = item["relatedEventId"];
    if (!only_keys(item, {"sequence", "deviceUptimeMs", "profileId", "kind", "eventId", "reason",
                          "count", "relatedEventId"}) ||
        !item["sequence"].is<std::uint64_t>() ||
        item["sequence"].as<std::uint64_t>() <= previous_sequence ||
        !item["deviceUptimeMs"].is<std::uint64_t>() || !valid_identifier(profile_id, 64) ||
        !valid_identifier(kind, 32) || !valid_identifier(event_id, 128) ||
        !valid_text(reason, 200, true) || !item["count"].is<std::int64_t>() ||
        item["count"].as<std::int64_t>() < 0 || profile_ids.count(profile_id) == 0 ||
        !event_ids.insert(event_id).second ||
        (std::string(kind) != "count" && std::string(kind) != "correction") ||
        (std::string(kind) == "count" && related_event_id != nullptr) ||
        (std::string(kind) == "correction" && !valid_identifier(related_event_id, 128))) {
      return false;
    }
    entry.sequence = item["sequence"];
    previous_sequence = entry.sequence;
    entry.monotonic_ms = item["deviceUptimeMs"];
    entry.profile_id = profile_id;
    entry.kind = kind;
    entry.event_id = event_id;
    entry.reason = reason;
    entry.count = item["count"];
    if (related_event_id != nullptr) {
      const auto related = std::find_if(
          replacement.history.begin(), replacement.history.end(), [&](const HistoryEntry& prior) {
            return prior.event_id == related_event_id && prior.kind == "count" &&
                   prior.profile_id == profile_id;
          });
      if (related == replacement.history.end()) return false;
      entry.related_event_id = related_event_id;
    }
    replacement.history.push_back(std::move(entry));
  }
  return true;
}

}  // namespace

ProtocolGuard::ProtocolGuard(std::string allowed_origin)
    : allowed_origin_(std::move(allowed_origin)) {}

Session ProtocolGuard::open_setup_session(bool physical_button_pressed, std::uint64_t now_ms,
                                          const std::string& nonce) const {
  if (!physical_button_pressed || nonce.size() < 16) return {};
  return {nonce, AuthScope::setup, now_ms + kSessionLifetimeMs};
}

ValidationResult ProtocolGuard::validate(const TransportRequest& request, const Session& session,
                                         std::uint64_t now_ms, bool mutating) const {
  if (request.path.rfind("/api/v1", 0) != 0) return {false, 404, "not_found"};
  if (session.scope == AuthScope::none || now_ms >= session.expires_ms ||
      request.authorization != "Bearer " + session.token) {
    return {false, 401, "authentication_required"};
  }
  if ((session.scope == AuthScope::setup) != is_setup_path(request.path)) {
    return {false, 403, "scope_rejected"};
  }
  if (!mutating) return {true, 200, {}};
  if (request.content_type != "application/json") return {false, 415, "content_type_required"};
  if (request.origin != allowed_origin_) return {false, 403, "origin_rejected"};
  if (request.idempotency_key.empty() || request.idempotency_key.size() > 128) {
    return {false, 400, "idempotency_key_required"};
  }
  if (request.body.empty() || request.body.size() > kMaximumBodyBytes) {
    return {false, 400, "malformed_request"};
  }
  return {true, 200, {}};
}

bool ProtocolGuard::remember_idempotency(const std::string& key,
                                         const std::string& request_fingerprint,
                                         TransportResponse response) {
  bool conflict = false;
  if (key.empty() || replay(key, request_fingerprint, conflict) != nullptr || conflict) {
    return false;
  }
  ids_.push_back({key, request_fingerprint, std::move(response)});
  if (ids_.size() > 64) ids_.pop_front();
  return true;
}

const TransportResponse* ProtocolGuard::replay(const std::string& key,
                                               const std::string& request_fingerprint,
                                               bool& conflict) const {
  conflict = false;
  for (const auto& record : ids_) {
    if (record.key != key) continue;
    conflict = record.fingerprint != request_fingerprint;
    return conflict ? nullptr : &record.response;
  }
  return nullptr;
}

std::string ProtocolGuard::redact(const std::string& text) {
  JsonDocument document;
  if (deserializeJson(document, text)) return "[unparseable redacted payload]";
  redact_secrets(document.as<JsonVariant>());
  return json_string(document);
}

ApiService::ApiService(std::string device_id, ProtocolGuard& guard,
                       MeasurementPipeline& measurement, PersistentState& state,
                       PersistCallback persist, TokenCallback token,
                       ProvisionedCallback provisioned)
    : device_id_(std::move(device_id)),
      guard_(guard),
      measurement_(measurement),
      state_(state),
      persist_(std::move(persist)),
      token_(std::move(token)),
      provisioned_(std::move(provisioned)) {}

void ApiService::set_session(Session session) {
  if (session.scope == AuthScope::setup) {
    setup_session_ = std::move(session);
  } else {
    if (authenticated_session_.token != session.token) {
      import_preview_token_.clear();
      import_preview_payload_.clear();
      import_preview_session_token_.clear();
      import_preview_expires_ms_ = 0;
    }
    authenticated_session_ = std::move(session);
  }
}

const Session& ApiService::session() const {
  return authenticated_session_.scope == AuthScope::authenticated ? authenticated_session_
                                                                  : setup_session_;
}

bool ApiService::authorize_event_token(const std::string& token, std::uint64_t now_ms,
                                       std::uint64_t& expires_ms) const {
  if (authenticated_session_.scope != AuthScope::authenticated ||
      now_ms >= authenticated_session_.expires_ms || token != authenticated_session_.token) {
    return false;
  }
  expires_ms = authenticated_session_.expires_ms;
  return true;
}

bool ApiService::record_stable_count(const std::string& profile_id, const Measurement& measurement,
                                     std::uint64_t now_ms) {
  if (!measurement.stable || !measurement.estimated_count ||
      find_profile(state_, profile_id) == nullptr) {
    return false;
  }
  if (!last_recorded_count_ || last_recorded_profile_id_ != profile_id) {
    const auto prior = std::find_if(
        state_.history.rbegin(), state_.history.rend(), [&](const HistoryEntry& entry) {
          return entry.profile_id == profile_id && entry.kind == "count";
        });
    if (prior != state_.history.rend()) {
      last_recorded_profile_id_ = profile_id;
      last_recorded_count_ = prior->count;
    }
  }
  if (last_recorded_profile_id_ == profile_id &&
      last_recorded_count_ == measurement.estimated_count) {
    return false;
  }
  const std::vector<HistoryEntry> history_before = state_.history;
  const std::uint64_t sequence = state_.history.empty() ? 1 : state_.history.back().sequence + 1;
  state_.history.push_back({sequence, now_ms, profile_id, "count",
                            unique_event_id(state_, "count", sequence), "",
                            *measurement.estimated_count, ""});
  if (state_.history.size() > kMaximumHistory) state_.history.erase(state_.history.begin());
  if (!persist_()) {
    state_.history = history_before;
    return false;
  }
  last_recorded_profile_id_ = profile_id;
  last_recorded_count_ = measurement.estimated_count;
  return true;
}

bool ApiService::is_mutating(const TransportRequest& request) const {
  return request.method != "GET";
}

TransportResponse ApiService::error(int status, const std::string& code,
                                    const std::string& message) const {
  JsonDocument output;
  output["error"]["code"] = code;
  output["error"]["message"] = message;
  output["error"]["retryable"] = false;
  return {status, "application/json", json_string(output)};
}

TransportResponse ApiService::handle(const TransportRequest& request, std::uint64_t now_ms) {
  const bool login = request.method == "POST" && request.path == "/api/v1/session";
  const bool setup_discovery = request.method == "GET" && request.path == "/api/v1/setup/session";
  const bool mutating = is_mutating(request);
  if (setup_discovery) {
    if (setup_session_.scope != AuthScope::setup || now_ms >= setup_session_.expires_ms) {
      return error(404, "setup_inactive", "physical-presence setup is not active");
    }
    JsonDocument output;
    output["protocol"] = "parts-tally/v1";
    output["token"] = setup_session_.token;
    output["expiresInSeconds"] = (setup_session_.expires_ms - now_ms) / 1000;
    return {200, "application/json", json_string(output)};
  }
  if (login) {
    if (request.content_type != "application/json") {
      return error(415, "content_type_required", "application/json is required");
    }
    if (!guard_.origin_allowed(request.origin)) {
      return error(403, "origin_rejected", "request rejected");
    }
    if (request.body.empty() || request.body.size() > kMaximumBodyBytes) {
      return error(400, "malformed_request", "request rejected");
    }
  } else {
    const Session& candidate =
        is_setup_path(request.path) ? setup_session_ : authenticated_session_;
    const ValidationResult validation = guard_.validate(request, candidate, now_ms, mutating);
    if (!validation.ok) return error(validation.status, validation.code, "request rejected");
  }

  const std::string request_fingerprint = fingerprint(request);
  if (mutating && !login) {
    bool conflict = false;
    const TransportResponse* previous =
        guard_.replay(request.idempotency_key, request_fingerprint, conflict);
    if (conflict) return error(409, "idempotency_conflict", "key was already used");
    if (previous != nullptr) return *previous;
  }

  const PersistentState state_before = state_;
  const Calibration calibration_before = measurement_.calibration();
  const Session setup_before = setup_session_;
  const Session authenticated_before = authenticated_session_;
  TransportResponse response = dispatch(request, now_ms);
  if (response.status >= 400) {
    state_ = state_before;
    measurement_.set_calibration(calibration_before);
    setup_session_ = setup_before;
    authenticated_session_ = authenticated_before;
  }
  if (mutating && !login && response.status < 500) {
    guard_.remember_idempotency(request.idempotency_key, request_fingerprint, response);
  }
  return response;
}

TransportResponse ApiService::dispatch(const TransportRequest& request, std::uint64_t now_ms) {
  JsonDocument input;
  if (is_mutating(request)) {
    if (deserializeJson(input, request.body) || !input.is<JsonObject>()) {
      return error(400, "malformed_request", "body must be one JSON object");
    }
    if (input["protocol"] != "parts-tally/v1" || !valid_identifier(input["requestId"], 128) ||
        input["deviceId"] != device_id_) {
      return error(422, "schema_invalid", "invalid protocol envelope");
    }
  }

  JsonDocument output;
  output["protocol"] = "parts-tally/v1";
  output["deviceId"] = device_id_;

  if (request.method == "POST" && request.path == "/api/v1/session") {
    const char* secret = input["deviceSecret"];
    if (state_.device_secret.empty() || secret == nullptr || state_.device_secret != secret) {
      return error(401, "credentials_invalid", "credentials are invalid");
    }
    const std::string fresh = token_();
    if (fresh.size() < 16) return error(503, "entropy_failed", "session could not be created");
    set_session({fresh, AuthScope::authenticated, now_ms + kSessionLifetimeMs});
    output["token"] = fresh;
    output["expiresInSeconds"] = kSessionLifetimeMs / 1000;
    return {200, "application/json", json_string(output)};
  }

  if (request.method == "POST" && request.path == "/api/v1/setup/provision") {
    const char* ssid = input["wifiSsid"];
    const char* password = input["wifiPassword"];
    const char* secret = input["deviceSecret"];
    if (!valid_text(ssid, 32, true) || !valid_text(password, 63, true) ||
        !valid_text(secret, 128) || std::char_traits<char>::length(secret) < 16 ||
        (*ssid == '\0' && *password != '\0')) {
      return error(422, "provision_invalid", "invalid Wi-Fi or device credentials");
    }
    state_.wifi_ssid = ssid;
    state_.wifi_password = password;
    state_.device_secret = secret;
    const std::string fresh = token_();
    if (fresh.size() < 16) return error(503, "entropy_failed", "session could not be created");
    set_session({fresh, AuthScope::authenticated, now_ms + kSessionLifetimeMs});
    if (!persist_()) return error(503, "storage_failed", "credentials were not persisted");
    setup_session_ = {};
    if (provisioned_) provisioned_(state_.wifi_ssid, state_.wifi_password);
    output["provisioned"] = true;
    output["directMode"] = state_.wifi_ssid.empty();
    output["token"] = fresh;
    output["expiresInSeconds"] = kSessionLifetimeMs / 1000;
    return {200, "application/json", json_string(output)};
  }

  if (request.method == "GET" && request.path == "/api/v1/status") {
    const Measurement current_measurement = measurement_.evaluate(now_ms);
    output["firmwareVersion"] = "0.2.0";
    output["deviceName"] = state_.device_name;
    JsonObject measured = output["measurement"].to<JsonObject>();
    measured["state"] = state_name(current_measurement.state);
    measured["stable"] = current_measurement.stable;
    measured["netGrams"] = current_measurement.net_grams;
    measured["sampleAgeMs"] = current_measurement.diagnostics.sample_age_ms;
    if (current_measurement.estimated_count) {
      measured["estimatedCount"] = *current_measurement.estimated_count;
      measured["uncertaintyPieces"] = *current_measurement.uncertainty_pieces;
    } else {
      measured["estimatedCount"] = nullptr;
      measured["uncertaintyPieces"] = nullptr;
    }
    output["faults"].to<JsonArray>();
    return {200, "application/json", json_string(output)};
  }

  if (request.method == "GET" && request.path == "/api/v1/profiles") {
    JsonArray profiles = output["profiles"].to<JsonArray>();
    for (const Profile& profile : state_.profiles) {
      add_profile(profiles.add<JsonObject>(), profile, true);
    }
    return {200, "application/json", json_string(output)};
  }

  if (request.method == "GET" &&
      (request.path == "/api/v1/history" || request.path.rfind("/api/v1/history?", 0) == 0)) {
    HistoryQuery query;
    if (!parse_history_query(request.path, query))
      return error(400, "query_invalid", "history query is malformed");
    JsonArray history = output["history"].to<JsonArray>();
    std::size_t emitted = 0;
    for (const HistoryEntry& entry : state_.history) {
      if (entry.sequence <= query.after || emitted >= query.limit) continue;
      add_history(history.add<JsonObject>(), entry);
      ++emitted;
    }
    output["limit"] = query.limit;
    output["bounded"] = true;
    output["nextAfter"] =
        emitted == 0 ? query.after : history[emitted - 1]["sequence"].as<std::uint64_t>();
    return {200, "application/json", json_string(output)};
  }

  if (request.method == "GET" && request.path == "/api/v1/export") {
    JsonDocument exported;
    exported["schemaVersion"] = 3;
    exported["deviceName"] = state_.device_name;
    JsonArray profiles = exported["profiles"].to<JsonArray>();
    for (const Profile& profile : state_.profiles) {
      add_profile(profiles.add<JsonObject>(), profile, true);
    }
    JsonArray history = exported["history"].to<JsonArray>();
    for (const HistoryEntry& entry : state_.history) {
      add_history(history.add<JsonObject>(), entry);
    }
    return {200, "application/json", json_string(exported)};
  }

  if (request.method == "POST" && request.path == "/api/v1/actions/tare") {
    if (!measurement_.tare(now_ms)) return error(409, "measurement_not_stable", "tare rejected");
    const char* profile_id = input["profileId"];
    if (profile_id != nullptr) {
      Profile* profile = find_profile(state_, profile_id);
      if (profile == nullptr) return error(404, "profile_not_found", "profile does not exist");
      profile->calibration = measurement_.calibration();
    }
    output["accepted"] = true;
  } else if (request.method == "POST" && request.path == "/api/v1/actions/calibrate") {
    if (!input["knownCount"].is<long>()) {
      return error(422, "known_count_invalid", "knownCount must be 10..1000000");
    }
    const long known_count = input["knownCount"].as<long>();
    if (known_count < 10 || known_count > 1000000) {
      return error(422, "known_count_invalid", "knownCount must be 10..1000000");
    }
    std::optional<double> known_mass;
    if (!input["knownSampleMassGrams"].isNull()) {
      if (!input["knownSampleMassGrams"].is<double>() ||
          !std::isfinite(input["knownSampleMassGrams"].as<double>()) ||
          input["knownSampleMassGrams"].as<double>() <= 0) {
        return error(422, "known_sample_mass_invalid",
                     "knownSampleMassGrams must be finite and positive");
      }
      known_mass = input["knownSampleMassGrams"].as<double>();
    }
    std::string reason;
    if (!measurement_.calibrate(static_cast<std::uint32_t>(known_count), now_ms, reason,
                                known_mass)) {
      return error(409, reason, "calibration rejected");
    }
    const char* profile_id = input["profileId"];
    if (profile_id != nullptr) {
      Profile* profile = find_profile(state_, profile_id);
      if (profile == nullptr) return error(404, "profile_not_found", "profile does not exist");
      profile->calibration = measurement_.calibration();
    }
    output["accepted"] = true;
  } else if (request.method == "POST" && request.path == "/api/v1/profiles") {
    const char* id = input["profileId"];
    const char* name = input["name"];
    if (!valid_identifier(id, 64) || !valid_text(name, 80)) {
      return error(422, "profile_invalid", "invalid profile id or name");
    }
    if (state_.profiles.size() >= kMaximumProfiles || find_profile(state_, id) != nullptr) {
      return error(409, "profile_conflict", "profile exists or limit reached");
    }
    Profile profile;
    profile.id = id;
    profile.name = name;
    profile.low_stock_threshold = input["lowStockThreshold"] | 0;
    profile.calibration = measurement_.calibration();
    state_.profiles.push_back(std::move(profile));
    output["created"] = id;
  } else if (request.method == "PATCH") {
    std::string id;
    if (!exact_profile_path(request.path, id)) return error(404, "not_found", "route not found");
    Profile* profile = find_profile(state_, id);
    if (profile == nullptr) return error(404, "profile_not_found", "profile does not exist");
    if (!input["name"].isNull()) {
      const char* name = input["name"];
      if (!valid_text(name, 80)) return error(422, "profile_invalid", "invalid name");
      profile->name = name;
    }
    if (!input["lowStockThreshold"].isNull()) {
      if (!input["lowStockThreshold"].is<int>() || input["lowStockThreshold"].as<int>() < 0) {
        return error(422, "profile_invalid", "invalid threshold");
      }
      profile->low_stock_threshold = input["lowStockThreshold"];
    }
    output["updated"] = id;
  } else if (request.method == "DELETE" && request.path != "/api/v1/history") {
    std::string id;
    if (!exact_profile_path(request.path, id)) return error(404, "not_found", "route not found");
    const std::size_t before = state_.profiles.size();
    state_.profiles.erase(std::remove_if(state_.profiles.begin(), state_.profiles.end(),
                                         [&](const Profile& profile) { return profile.id == id; }),
                          state_.profiles.end());
    if (before == state_.profiles.size()) {
      return error(404, "profile_not_found", "profile does not exist");
    }
    output["deleted"] = id;
  } else if (request.method == "POST" && request.path.rfind("/api/v1/counts/", 0) == 0) {
    std::string event_id;
    if (!exact_correction_path(request.path, event_id)) {
      return error(404, "not_found", "route not found");
    }
    const char* profile_id = input["profileId"];
    const char* reason = input["reason"];
    if (!valid_identifier(event_id.c_str(), 128) || !valid_identifier(profile_id, 64) ||
        !valid_text(reason, 200) || !input["count"].is<long>()) {
      return error(422, "correction_invalid", "event, profile, count and reason are required");
    }
    const long count = input["count"];
    if (count < 0 || count > 100000000) {
      return error(422, "correction_invalid", "count is outside bounds");
    }
    if (find_profile(state_, profile_id) == nullptr) {
      return error(404, "profile_not_found", "profile does not exist");
    }
    const auto referenced =
        std::find_if(state_.history.begin(), state_.history.end(), [&](const HistoryEntry& entry) {
          return entry.event_id == event_id && entry.kind == "count" &&
                 entry.profile_id == profile_id;
        });
    if (referenced == state_.history.end()) {
      return error(404, "count_event_not_found", "count event does not exist");
    }
    const std::uint64_t sequence = state_.history.empty() ? 1 : state_.history.back().sequence + 1;
    const std::string correction_id = unique_event_id(state_, "correction", sequence);
    state_.history.push_back(
        {sequence, now_ms, profile_id, "correction", correction_id, reason, count, event_id});
    if (state_.history.size() > kMaximumHistory) state_.history.erase(state_.history.begin());
    output["recorded"] = true;
    output["eventId"] = correction_id;
    output["relatedEventId"] = event_id;
  } else if (request.method == "POST" && request.path == "/api/v1/import/preview") {
    JsonObjectConst imported = input["import"].as<JsonObjectConst>();
    PersistentState replacement;
    if (!parse_import(imported, replacement)) {
      return error(422, "import_invalid", "invalid, incompatible, or secret-bearing import");
    }
    import_preview_token_ = token_();
    if (import_preview_token_.size() < 16) return error(503, "entropy_failed", "preview failed");
    import_preview_payload_.clear();
    serializeJson(imported, import_preview_payload_);
    import_preview_session_token_ = authenticated_session_.token;
    import_preview_expires_ms_ = now_ms + kImportPreviewLifetimeMs;
    output["previewToken"] = import_preview_token_;
    output["wouldReplaceProfiles"] = replacement.profiles.size();
    output["wouldReplaceHistory"] = replacement.history.size();
    return {200, "application/json", json_string(output)};
  } else if (request.method == "POST" && request.path == "/api/v1/import/apply") {
    const char* preview = input["previewToken"];
    JsonObjectConst imported = input["import"].as<JsonObjectConst>();
    std::string payload;
    serializeJson(imported, payload);
    PersistentState replacement;
    if (preview == nullptr || preview != import_preview_token_ ||
        authenticated_session_.token != import_preview_session_token_ ||
        now_ms >= import_preview_expires_ms_ || payload != import_preview_payload_ ||
        !parse_import(imported, replacement)) {
      return error(422, "import_not_previewed", "matching valid preview is required");
    }
    replacement.wifi_ssid = state_.wifi_ssid;
    replacement.wifi_password = state_.wifi_password;
    replacement.device_secret = state_.device_secret;
    state_ = std::move(replacement);
    import_preview_token_.clear();
    import_preview_payload_.clear();
    import_preview_session_token_.clear();
    import_preview_expires_ms_ = 0;
    output["applied"] = true;
  } else if (request.method == "DELETE" && request.path == "/api/v1/history") {
    if (input["confirmation"] != "CLEAR HISTORY") {
      return error(422, "confirmation_required", "exact confirmation is required");
    }
    state_.history.clear();
    output["cleared"] = true;
  } else {
    return error(404, "not_found", "route not found");
  }

  if (!persist_()) return error(503, "storage_failed", "state was not persisted");
  return {200, "application/json", json_string(output)};
}

std::string ApiService::event(const std::string& type, const std::string& payload_json,
                              std::uint64_t now_ms) {
  JsonDocument payload;
  if (deserializeJson(payload, payload_json) || !payload.is<JsonObject>()) payload.clear();
  JsonDocument output;
  output["protocol"] = "parts-tally/v1";
  output["type"] = type;
  output["sequence"] = events_.next();
  output["deviceUptimeMs"] = now_ms;
  output["payload"] = payload.as<JsonObject>();
  return json_string(output);
}

}  // namespace parts_tally
