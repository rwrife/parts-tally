#include <unity.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <map>
#include <string>
#include <vector>

#include "parts_tally/persistence.hpp"
#include "parts_tally/protocol.hpp"

using namespace parts_tally;

namespace {

class MemoryStorage final : public IStorage {
 public:
  bool read(const std::string& key, std::vector<std::uint8_t>& value) override {
    const auto found = data.find(key);
    if (found == data.end()) {
      return false;
    }
    value = found->second;
    return true;
  }

  bool replace_atomically(const std::string& key, const std::vector<std::uint8_t>& value) override {
    if (fail_write) {
      return false;
    }
    data[key] = value;
    return true;
  }

  bool erase_all() override {
    data.clear();
    return true;
  }

  std::map<std::string, std::vector<std::uint8_t>> data;
  bool fail_write{};
};

template <typename T>
void append_bytes(std::vector<std::uint8_t>& output, T value) {
  const auto* bytes = reinterpret_cast<const std::uint8_t*>(&value);
  output.insert(output.end(), bytes, bytes + sizeof(value));
}

std::uint32_t state_checksum(const std::vector<std::uint8_t>& bytes) {
  std::uint32_t result = 2166136261U;
  for (std::uint8_t byte : bytes) {
    result = (result ^ byte) * 16777619U;
  }
  return result;
}

struct ApiFixture {
  ApiFixture()
      : persistence(storage, 256),
        guard("http://device.local"),
        api(
            "pt-test", guard, measurement, state, [this]() { return persistence.save(state); },
            []() { return "fedcba9876543210fedcba9876543210"; }) {
    api.set_session({"0123456789abcdef", AuthScope::authenticated, 100000});
  }

  TransportResponse request(const std::string& method, const std::string& path,
                            const std::string& body = {}, const std::string& key = "request-key") {
    return api.handle({method, path, body.empty() ? "" : "application/json", "http://device.local",
                       "Bearer 0123456789abcdef", key, body},
                      1000);
  }

  static std::string command(const std::string& fields = {}) {
    return "{\"protocol\":\"parts-tally/v1\",\"requestId\":\"req-1\","
           "\"deviceId\":\"pt-test\"" +
           fields + "}";
  }

  MemoryStorage storage;
  Persistence persistence;
  ProtocolGuard guard;
  MeasurementPipeline measurement;
  PersistentState state;
  ApiService api;
};

void persistence_bounds_history_and_redacts_exports() {
  MemoryStorage storage;
  Persistence persistence(storage, 2);
  PersistentState state;
  state.wifi_ssid = "Workshop";
  state.wifi_password = "supersecret";
  state.device_secret = "devicekey";
  Profile profile;
  profile.id = "p1";
  profile.name = "M3";
  profile.calibration.tare_valid = true;
  profile.calibration.valid = true;
  profile.calibration.grams_per_code = 0.1;
  profile.calibration.unit_mass_grams = 2;
  state.profiles.push_back(profile);
  for (int index = 0; index < 3; ++index) {
    const auto sequence = static_cast<std::uint64_t>(index + 1);
    persistence.append_history(state, {sequence, 0, "p1", "count",
                                       "event-" + std::to_string(sequence), "", index, ""});
  }
  TEST_ASSERT_TRUE(persistence.save(state));

  PersistentState restored;
  TEST_ASSERT_EQUAL_INT(static_cast<int>(LoadResult::ok),
                        static_cast<int>(persistence.load(restored)));
  TEST_ASSERT_EQUAL_UINT32(2, restored.history.size());
  TEST_ASSERT_EQUAL_STRING("Workshop", restored.wifi_ssid.c_str());
  TEST_ASSERT_EQUAL_STRING("supersecret", restored.wifi_password.c_str());
  TEST_ASSERT_EQUAL_STRING("devicekey", restored.device_secret.c_str());
  const std::string exported = persistence.export_json(state, true);
  TEST_ASSERT_NULL(std::strstr(exported.c_str(), "supersecret"));
  TEST_ASSERT_NULL(std::strstr(exported.c_str(), "devicekey"));
}

void restart_corruption_and_interrupted_write_are_safe() {
  MemoryStorage storage;
  Persistence persistence(storage);
  PersistentState original;
  original.device_name = "saved";
  TEST_ASSERT_TRUE(persistence.save(original));
  const std::vector<std::uint8_t> good = storage.data["state"];

  PersistentState after_restart;
  TEST_ASSERT_EQUAL_INT(static_cast<int>(LoadResult::ok),
                        static_cast<int>(persistence.load(after_restart)));
  TEST_ASSERT_EQUAL_STRING("saved", after_restart.device_name.c_str());

  storage.data["state"][5] ^= 0xFF;
  after_restart.device_name = "unchanged";
  TEST_ASSERT_EQUAL_INT(static_cast<int>(LoadResult::corrupt),
                        static_cast<int>(persistence.load(after_restart)));
  TEST_ASSERT_EQUAL_STRING("unchanged", after_restart.device_name.c_str());

  storage.data["state"] = good;
  storage.fail_write = true;
  original.device_name = "not committed";
  TEST_ASSERT_FALSE(persistence.save(original));
  TEST_ASSERT_EQUAL_MEMORY(good.data(), storage.data["state"].data(), good.size());
}

void version_one_empty_state_migrates_atomically() {
  MemoryStorage storage;
  std::vector<std::uint8_t> version_one{'P', 'T', 'D', 'B'};
  append_bytes<std::uint32_t>(version_one, 1);
  const std::string name = "legacy";
  append_bytes<std::uint32_t>(version_one, name.size());
  version_one.insert(version_one.end(), name.begin(), name.end());
  append_bytes<std::uint32_t>(version_one, 0);
  append_bytes<std::uint32_t>(version_one, 0);
  append_bytes<std::uint32_t>(version_one, state_checksum(version_one));
  storage.data["state"] = version_one;

  Persistence persistence(storage);
  PersistentState migrated;
  TEST_ASSERT_EQUAL_INT(static_cast<int>(LoadResult::migrated),
                        static_cast<int>(persistence.load(migrated)));
  TEST_ASSERT_EQUAL_STRING("legacy", migrated.device_name.c_str());
  TEST_ASSERT_EQUAL_UINT8(3, storage.data["state"][4]);
}

void version_two_history_migration_generates_valid_event_relationships() {
  MemoryStorage storage;
  std::vector<std::uint8_t> version_two{'P', 'T', 'D', 'B'};
  const auto append_string = [&](const std::string& value) {
    append_bytes<std::uint32_t>(version_two, value.size());
    version_two.insert(version_two.end(), value.begin(), value.end());
  };
  append_bytes<std::uint32_t>(version_two, 2);
  append_string("legacy-history");
  append_bytes<std::uint32_t>(version_two, 1);  // profiles
  append_string("p1");
  append_string("Legacy bolts");
  append_bytes<int>(version_two, 0);
  append_bytes<std::uint32_t>(version_two, 2);
  append_bytes<bool>(version_two, true);
  append_bytes<bool>(version_two, false);
  append_bytes<bool>(version_two, false);
  append_bytes<double>(version_two, 1000.0);
  append_bytes<double>(version_two, 0.1);
  append_bytes<double>(version_two, 1.0);
  append_bytes<double>(version_two, 0.0);
  append_bytes<double>(version_two, 0.0);
  append_bytes<std::uint32_t>(version_two, 10);
  append_bytes<std::uint64_t>(version_two, 1);
  append_bytes<std::uint32_t>(version_two, 2);  // history rows
  append_bytes<std::uint64_t>(version_two, 1);
  append_bytes<std::uint64_t>(version_two, 10);
  append_string("p1");
  append_string("count");
  append_bytes<std::int64_t>(version_two, 8);
  append_bytes<std::uint64_t>(version_two, 2);
  append_bytes<std::uint64_t>(version_two, 11);
  append_string("p1");
  append_string("correction");
  append_bytes<std::int64_t>(version_two, 9);
  append_bytes<std::uint32_t>(version_two, state_checksum(version_two));
  const std::vector<std::uint8_t> legacy_blob = version_two;
  storage.data["state"] = version_two;

  Persistence persistence(storage);
  PersistentState migrated;
  TEST_ASSERT_EQUAL_INT(static_cast<int>(LoadResult::migrated),
                        static_cast<int>(persistence.load(migrated)));
  TEST_ASSERT_EQUAL_UINT32(2, migrated.history.size());
  TEST_ASSERT_EQUAL_STRING("count-1", migrated.history[0].event_id.c_str());
  TEST_ASSERT_EQUAL_STRING("correction-2", migrated.history[1].event_id.c_str());
  TEST_ASSERT_EQUAL_STRING("count-1", migrated.history[1].related_event_id.c_str());

  PersistentState reloaded;
  TEST_ASSERT_EQUAL_INT(static_cast<int>(LoadResult::ok),
                        static_cast<int>(persistence.load(reloaded)));
  TEST_ASSERT_EQUAL_STRING("count-1", reloaded.history[1].related_event_id.c_str());

  std::vector<std::uint8_t> dangling = legacy_blob;
  const std::array<std::uint8_t, 2> profile_id{'p', '1'};
  auto profile = std::search(dangling.begin(), dangling.end() - 4, profile_id.begin(),
                             profile_id.end());
  TEST_ASSERT_NOT_EQUAL(dangling.end() - 4, profile);
  *profile = 'q';
  dangling.resize(dangling.size() - 4);
  append_bytes<std::uint32_t>(dangling, state_checksum(dangling));
  MemoryStorage invalid_storage;
  invalid_storage.data["state"] = dangling;
  Persistence invalid_persistence(invalid_storage);
  PersistentState rejected;
  TEST_ASSERT_EQUAL_INT(static_cast<int>(LoadResult::corrupt),
                        static_cast<int>(invalid_persistence.load(rejected)));
}

void guard_enforces_presence_expiry_origin_json_and_authentication() {
  ProtocolGuard guard("http://device.local");
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(AuthScope::none),
      static_cast<int>(guard.open_setup_session(false, 0, "0123456789abcdef").scope));
  Session session = guard.open_setup_session(true, 100, "0123456789abcdef");
  TransportRequest request{"POST",
                           "/api/v1/setup/provision",
                           "application/json",
                           "http://device.local",
                           "Bearer 0123456789abcdef",
                           "key",
                           "{}"};
  TEST_ASSERT_TRUE(guard.validate(request, session, 200, true).ok);
  request.path = "/api/v1/actions/tare";
  TEST_ASSERT_EQUAL_INT(403, guard.validate(request, session, 200, true).status);
  request.path = "/api/v1/setup/provision";
  request.origin = "http://evil.local";
  TEST_ASSERT_EQUAL_INT(403, guard.validate(request, session, 200, true).status);
  request.origin = "http://device.local";
  request.content_type = "text/plain";
  TEST_ASSERT_EQUAL_INT(415, guard.validate(request, session, 200, true).status);
  request.content_type = "application/json";
  request.authorization = "Bearer wrong";
  TEST_ASSERT_EQUAL_INT(401, guard.validate(request, session, 200, true).status);
  request.authorization = "Bearer 0123456789abcdef";
  TEST_ASSERT_EQUAL_INT(401, guard.validate(request, session, 400000, true).status);
}

void setup_scope_provision_login_and_expiry_are_enforced() {
  ApiFixture fixture;
  fixture.api.set_session(
      fixture.guard.open_setup_session(true, 100, "setup-token-0123456789abcdef"));
  TransportResponse setup_status =
      fixture.api.handle({"GET", "/api/v1/status", "", "http://device.local",
                          "Bearer setup-token-0123456789abcdef", "", ""},
                         200);
  TEST_ASSERT_EQUAL_INT(401, setup_status.status);

  const std::string provision = ApiFixture::command(
      ",\"wifiSsid\":\"Shop\",\"wifiPassword\":\"wifi-pass\","
      "\"deviceSecret\":\"new-device-secret-123\"");
  TransportResponse provisioned = fixture.api.handle(
      {"POST", "/api/v1/setup/provision", "application/json", "http://device.local",
       "Bearer setup-token-0123456789abcdef", "provision", provision},
      200);
  TEST_ASSERT_EQUAL_INT(200, provisioned.status);
  TEST_ASSERT_EQUAL_STRING("Shop", fixture.state.wifi_ssid.c_str());
  PersistentState restored;
  TEST_ASSERT_EQUAL_INT(static_cast<int>(LoadResult::ok),
                        static_cast<int>(fixture.persistence.load(restored)));
  TEST_ASSERT_EQUAL_STRING("new-device-secret-123", restored.device_secret.c_str());

  TransportResponse auth_on_setup =
      fixture.api.handle({"GET", "/api/v1/setup/session", "", "http://device.local",
                          "Bearer fedcba9876543210fedcba9876543210", "", ""},
                         300);
  TEST_ASSERT_EQUAL_INT(404, auth_on_setup.status);

  const std::string wrong = ApiFixture::command(",\"deviceSecret\":\"wrong-secret-value\"");
  TransportResponse rejected = fixture.api.handle(
      {"POST", "/api/v1/session", "application/json", "http://device.local", "", "", wrong}, 400);
  TEST_ASSERT_EQUAL_INT(401, rejected.status);
  const std::string login = ApiFixture::command(",\"deviceSecret\":\"new-device-secret-123\"");
  TransportResponse logged_in = fixture.api.handle(
      {"POST", "/api/v1/session", "application/json", "http://device.local", "", "", login}, 500);
  TEST_ASSERT_EQUAL_INT(200, logged_in.status);
  TransportResponse expired =
      fixture.api.handle({"GET", "/api/v1/status", "", "http://device.local",
                          "Bearer fedcba9876543210fedcba9876543210", "", ""},
                         301000);
  TEST_ASSERT_EQUAL_INT(401, expired.status);
}

void status_profiles_history_and_export_routes_return_real_data() {
  ApiFixture fixture;
  fixture.state.profiles.push_back({"p1", "Bolts", {}, 5});
  fixture.state.history.push_back({1, 100, "p1", "count", "evt-1", "", 12, ""});
  fixture.state.wifi_password = "never-export";

  TransportResponse status = fixture.request("GET", "/api/v1/status");
  TEST_ASSERT_EQUAL_INT(200, status.status);
  TEST_ASSERT_NOT_NULL(std::strstr(status.body.c_str(), "\"measurement\""));
  TransportResponse profiles = fixture.request("GET", "/api/v1/profiles");
  TEST_ASSERT_NOT_NULL(std::strstr(profiles.body.c_str(), "Bolts"));
  TransportResponse history = fixture.request("GET", "/api/v1/history?limit=100");
  TEST_ASSERT_NOT_NULL(std::strstr(history.body.c_str(), "\"count\":12"));
  TransportResponse exported = fixture.request("GET", "/api/v1/export");
  TEST_ASSERT_NULL(std::strstr(exported.body.c_str(), "never-export"));
}

void profile_crud_correction_and_clear_are_persisted() {
  ApiFixture fixture;
  TransportResponse created =
      fixture.request("POST", "/api/v1/profiles",
                      ApiFixture::command(",\"profileId\":\"m3\",\"name\":\"M3 bolts\""), "create");
  TEST_ASSERT_EQUAL_INT(200, created.status);
  TEST_ASSERT_EQUAL_UINT32(1, fixture.state.profiles.size());

  TransportResponse updated =
      fixture.request("PATCH", "/api/v1/profiles/m3",
                      ApiFixture::command(",\"name\":\"M3\",\"lowStockThreshold\":7"), "update");
  TEST_ASSERT_EQUAL_INT(200, updated.status);
  TEST_ASSERT_EQUAL_INT(7, fixture.state.profiles.front().low_stock_threshold);

  fixture.state.history.push_back({1, 900, "m3", "count", "source-7", "", 20, ""});

  TransportResponse correction =
      fixture.request("POST", "/api/v1/counts/source-7/correction",
                      ApiFixture::command(",\"profileId\":\"m3\",\"count\":21,"
                                          "\"reason\":\"manual recount\""),
                      "correct");
  TEST_ASSERT_EQUAL_INT(200, correction.status);
  TEST_ASSERT_EQUAL_INT64(21, fixture.state.history.back().count);
  TEST_ASSERT_NOT_EQUAL(0, std::strcmp("source-7", fixture.state.history.back().event_id.c_str()));
  TEST_ASSERT_EQUAL_STRING("source-7", fixture.state.history.back().related_event_id.c_str());
  TEST_ASSERT_EQUAL_STRING("manual recount", fixture.state.history.back().reason.c_str());
  TransportResponse missing_reason =
      fixture.request("POST", "/api/v1/counts/source-8/correction",
                      ApiFixture::command(",\"profileId\":\"m3\",\"count\":22"), "missing-reason");
  TEST_ASSERT_EQUAL_INT(422, missing_reason.status);

  TransportResponse rejected_clear =
      fixture.request("DELETE", "/api/v1/history", ApiFixture::command(), "bad-clear");
  TEST_ASSERT_EQUAL_INT(422, rejected_clear.status);
  TransportResponse clear =
      fixture.request("DELETE", "/api/v1/history",
                      ApiFixture::command(",\"confirmation\":\"CLEAR HISTORY\""), "clear");
  TEST_ASSERT_EQUAL_INT(200, clear.status);
  TEST_ASSERT_TRUE(fixture.state.history.empty());

  TransportResponse removed =
      fixture.request("DELETE", "/api/v1/profiles/m3", ApiFixture::command(), "remove");
  TEST_ASSERT_EQUAL_INT(200, removed.status);
  TEST_ASSERT_TRUE(fixture.state.profiles.empty());
}

void history_pagination_is_bounded_and_cursor_based() {
  ApiFixture fixture;
  for (std::uint64_t sequence = 1; sequence <= 130; ++sequence) {
    fixture.state.history.push_back(
        {sequence, sequence, "p1", "count", "evt", "", static_cast<std::int64_t>(sequence), ""});
  }
  TransportResponse page = fixture.request("GET", "/api/v1/history?after=5&limit=100");
  TEST_ASSERT_EQUAL_INT(200, page.status);
  TEST_ASSERT_NOT_NULL(std::strstr(page.body.c_str(), "\"limit\":100"));
  TEST_ASSERT_NOT_NULL(std::strstr(page.body.c_str(), "\"sequence\":6"));
  TEST_ASSERT_NOT_NULL(std::strstr(page.body.c_str(), "\"nextAfter\":105"));
}

void tare_and_calibrate_routes_assert_domain_outcomes() {
  ApiFixture fixture;
  fixture.measurement.set_scale(0.01);
  for (int index = 0; index < 25; ++index) {
    const std::uint64_t time = static_cast<std::uint64_t>(index) * 100;
    fixture.measurement.ingest({1000, time, SensorFault::none}, time);
  }
  TransportResponse tare =
      fixture.api.handle({"POST", "/api/v1/actions/tare", "application/json", "http://device.local",
                          "Bearer 0123456789abcdef", "tare", ApiFixture::command()},
                         2400);
  TEST_ASSERT_EQUAL_INT(200, tare.status);
  TEST_ASSERT_TRUE(fixture.measurement.calibration().tare_valid);

  TransportResponse too_small =
      fixture.request("POST", "/api/v1/actions/calibrate", ApiFixture::command(",\"knownCount\":9"),
                      "calibrate-small");
  TEST_ASSERT_EQUAL_INT(422, too_small.status);
}

void failed_persistence_rolls_back_route_mutation() {
  ApiFixture fixture;
  fixture.storage.fail_write = true;
  TransportResponse response = fixture.request(
      "POST", "/api/v1/profiles",
      ApiFixture::command(",\"profileId\":\"p1\",\"name\":\"Transient\""), "failed-write");
  TEST_ASSERT_EQUAL_INT(503, response.status);
  TEST_ASSERT_TRUE(fixture.state.profiles.empty());
  fixture.storage.fail_write = false;
  TransportResponse retry = fixture.request(
      "POST", "/api/v1/profiles",
      ApiFixture::command(",\"profileId\":\"p1\",\"name\":\"Transient\""), "failed-write");
  TEST_ASSERT_EQUAL_INT(200, retry.status);
  TEST_ASSERT_EQUAL_UINT32(1, fixture.state.profiles.size());
}

void import_requires_preview_and_rejects_secrets_and_bad_schema() {
  ApiFixture fixture;
  TransportResponse secret =
      fixture.request("POST", "/api/v1/import/preview",
                      ApiFixture::command(",\"import\":{\"schemaVersion\":3,\"profiles\":[],"
                                          "\"deviceName\":\"Imported\",\"history\":[],"
                                          "\"wifiSecret\":\"nope\"}"),
                      "secret-preview");
  TEST_ASSERT_EQUAL_INT(422, secret.status);

  TransportResponse incompatible = fixture.request(
      "POST", "/api/v1/import/preview",
      ApiFixture::command(",\"import\":{\"schemaVersion\":3,\"profiles\":[]}"), "bad-preview");
  TEST_ASSERT_EQUAL_INT(422, incompatible.status);

  const std::string imported =
      ",\"import\":{\"schemaVersion\":3,\"deviceName\":\"Imported\","
      "\"profiles\":[{\"id\":\"p2\",\"name\":\"Nuts\",\"lowStockThreshold\":9,"
      "\"calibrated\":true,\"provisional\":false,"
      "\"calibration\":{\"schemaVersion\":2,\"tareValid\":true,\"valid\":true,"
      "\"provisional\":false,\"tareCode\":11.5,\"gramsPerCode\":0.2,"
      "\"unitMassGrams\":2.5,\"unitUncertaintyGrams\":0.1,"
      "\"calibrationResidualGrams\":0.05,\"knownCount\":20,\"createdMs\":42}}],"
      "\"history\":[{\"sequence\":7,\"deviceUptimeMs\":98,\"profileId\":\"p2\","
      "\"kind\":\"count\",\"eventId\":\"evt-7\",\"reason\":\"\",\"count\":16},"
      "{\"sequence\":8,\"deviceUptimeMs\":99,\"profileId\":\"p2\","
      "\"kind\":\"correction\",\"eventId\":\"evt-8\",\"relatedEventId\":\"evt-7\","
      "\"reason\":\"recount\",\"count\":17}]}";
  TransportResponse preview =
      fixture.request("POST", "/api/v1/import/preview", ApiFixture::command(imported), "preview");
  TEST_ASSERT_EQUAL_INT(200, preview.status);
  TEST_ASSERT_NOT_NULL(std::strstr(preview.body.c_str(), "previewToken"));

  TransportResponse not_previewed =
      fixture.request("POST", "/api/v1/import/apply",
                      ApiFixture::command(imported + ",\"previewToken\":\"wrong\""), "apply-bad");
  TEST_ASSERT_EQUAL_INT(422, not_previewed.status);

  TransportResponse applied = fixture.request(
      "POST", "/api/v1/import/apply",
      ApiFixture::command(imported + ",\"previewToken\":\"fedcba9876543210fedcba9876543210\""),
      "apply");
  TEST_ASSERT_EQUAL_INT(200, applied.status);
  TEST_ASSERT_EQUAL_UINT32(1, fixture.state.profiles.size());
  TEST_ASSERT_EQUAL_STRING("p2", fixture.state.profiles.front().id.c_str());
  TEST_ASSERT_EQUAL_INT(9, fixture.state.profiles.front().low_stock_threshold);
  TEST_ASSERT_TRUE(std::abs(fixture.state.profiles.front().calibration.unit_mass_grams - 2.5) <
                   0.001);
  TEST_ASSERT_EQUAL_UINT32(2, fixture.state.history.size());
  TEST_ASSERT_EQUAL_STRING("evt-7", fixture.state.history.back().related_event_id.c_str());
}

void export_import_round_trip_preserves_correction_relationship() {
  ApiFixture fixture;
  fixture.state.profiles.push_back({"p1", "Bolts", {}, 0});
  fixture.state.history.push_back({1, 10, "p1", "count", "count-1", "", 8, ""});
  fixture.state.history.push_back(
      {2, 11, "p1", "correction", "correction-2", "recount", 9, "count-1"});
  const TransportResponse exported = fixture.request("GET", "/api/v1/export");
  TEST_ASSERT_EQUAL_INT(200, exported.status);
  const std::string imported = ",\"import\":" + exported.body;
  const TransportResponse roundtrip_preview = fixture.request(
      "POST", "/api/v1/import/preview", ApiFixture::command(imported), "roundtrip-preview");
  TEST_ASSERT_EQUAL_INT(200, roundtrip_preview.status);
  TEST_ASSERT_EQUAL_INT(
      200, fixture
               .request("POST", "/api/v1/import/apply",
                        ApiFixture::command(
                            imported + ",\"previewToken\":\"fedcba9876543210fedcba9876543210\""),
                        "roundtrip-apply")
               .status);
  TEST_ASSERT_EQUAL_UINT32(2, fixture.state.history.size());
  TEST_ASSERT_EQUAL_STRING("correction-2", fixture.state.history.back().event_id.c_str());
  TEST_ASSERT_EQUAL_STRING("count-1", fixture.state.history.back().related_event_id.c_str());
}

void malformed_schema_replay_conflict_and_redaction_are_deterministic() {
  ApiFixture fixture;
  TransportResponse malformed = fixture.request("POST", "/api/v1/profiles", "{broken", "malformed");
  TEST_ASSERT_EQUAL_INT(400, malformed.status);
  TransportResponse schema = fixture.request("POST", "/api/v1/profiles", "{}", "schema");
  TEST_ASSERT_EQUAL_INT(422, schema.status);

  const std::string create = ApiFixture::command(",\"profileId\":\"p1\",\"name\":\"One\"");
  TransportResponse first = fixture.request("POST", "/api/v1/profiles", create, "same");
  TransportResponse replay = fixture.request("POST", "/api/v1/profiles", create, "same");
  TEST_ASSERT_EQUAL_STRING(first.body.c_str(), replay.body.c_str());
  TEST_ASSERT_EQUAL_UINT32(1, fixture.state.profiles.size());
  TransportResponse conflict =
      fixture.request("POST", "/api/v1/profiles",
                      ApiFixture::command(",\"profileId\":\"p2\",\"name\":\"Two\""), "same");
  TEST_ASSERT_EQUAL_INT(409, conflict.status);

  const std::string redacted = ProtocolGuard::redact(
      "{\"password\":\"secret\",\"nested\":{\"token\":\"bearer\"},"
      "\"items\":[{\"deviceSecret\":\"deep-secret\"}],\"safe\":1}");
  TEST_ASSERT_NULL(std::strstr(redacted.c_str(), "secret"));
  TEST_ASSERT_NULL(std::strstr(redacted.c_str(), "bearer"));
  TEST_ASSERT_NULL(std::strstr(redacted.c_str(), "deep-secret"));
  TEST_ASSERT_NOT_NULL(std::strstr(redacted.c_str(), "\"safe\":1"));
}

void exact_routes_reject_lookalikes_and_corrections_require_real_references() {
  ApiFixture fixture;
  fixture.state.profiles.push_back({"p1", "Bolts", {}, 0});
  fixture.state.profiles.push_back({"p2", "Nuts", {}, 0});
  fixture.state.history.push_back({1, 1, "p1", "count", "evt", "", 1, ""});
  TEST_ASSERT_EQUAL_INT(404, fixture.request("GET", "/api/v1/historyevil").status);
  TEST_ASSERT_EQUAL_INT(404, fixture
                                 .request("PATCH", "/api/v1/profiles/p1/extra",
                                          ApiFixture::command(",\"name\":\"Wrong\""), "bad-profile")
                                 .status);
  TEST_ASSERT_EQUAL_INT(404, fixture
                                 .request("POST", "/api/v1/counts/evt/correction/extra",
                                          ApiFixture::command(",\"profileId\":\"p1\",\"count\":1,"
                                                              "\"reason\":\"bad\""),
                                          "bad-correction")
                                 .status);
  TEST_ASSERT_EQUAL_INT(404, fixture
                                 .request("POST", "/api/v1/counts/missing/correction",
                                          ApiFixture::command(",\"profileId\":\"p1\",\"count\":1,"
                                                              "\"reason\":\"recount\""),
                                          "missing-event")
                                 .status);
  TEST_ASSERT_EQUAL_INT(404, fixture
                                 .request("POST", "/api/v1/counts/evt/correction",
                                          ApiFixture::command(",\"profileId\":\"p2\",\"count\":1,"
                                                              "\"reason\":\"cross profile\""),
                                          "cross-profile")
                                 .status);
}

void history_query_rejects_every_malformed_form() {
  ApiFixture fixture;
  const char* malformed[] = {
      "/api/v1/history?",
      "/api/v1/history?after=",
      "/api/v1/history?limit=",
      "/api/v1/history?after=-1",
      "/api/v1/history?after=+1",
      "/api/v1/history?after=1x",
      "/api/v1/history?limit=0",
      "/api/v1/history?limit=101",
      "/api/v1/history?limit=1.0",
      "/api/v1/history?limit=1&limit=2",
      "/api/v1/history?after=1&after=2",
      "/api/v1/history?unknown=1",
      "/api/v1/history?after=1&&limit=2",
      "/api/v1/history?after=1&",
      "/api/v1/history?=1",
      "/api/v1/history?after=1=2",
      "/api/v1/history?after=18446744073709551616",
      "/api/v1/history?limit=18446744073709551616",
      "/api/v1/history?after=1#fragment",
  };
  for (const char* path : malformed)
    TEST_ASSERT_EQUAL_INT(400, fixture.request("GET", path).status);
  TEST_ASSERT_EQUAL_INT(404, fixture.request("GET", "/api/v1/history#fragment").status);
  TEST_ASSERT_EQUAL_INT(404, fixture.request("GET", "/api/v1/historyevil?after=1").status);
  TEST_ASSERT_EQUAL_INT(200, fixture.request("GET", "/api/v1/history?limit=1&after=0").status);
  TEST_ASSERT_EQUAL_INT(
      200, fixture.request("GET", "/api/v1/history?after=18446744073709551615").status);
}

void stable_count_history_is_bounded_persisted_and_changes_only() {
  ApiFixture fixture;
  fixture.state.profiles.push_back({"p1", "Bolts", {}, 0});
  Measurement stable;
  stable.state = MeasurementState::stable;
  stable.stable = true;
  stable.estimated_count = 12;
  stable.uncertainty_pieces = 1;
  TEST_ASSERT_TRUE(fixture.api.record_stable_count("p1", stable, 1000));
  TEST_ASSERT_FALSE(fixture.api.record_stable_count("p1", stable, 1001));
  stable.estimated_count = 13;
  TEST_ASSERT_TRUE(fixture.api.record_stable_count("p1", stable, 1002));
  TEST_ASSERT_EQUAL_UINT32(2, fixture.state.history.size());
  TEST_ASSERT_EQUAL_STRING("count", fixture.state.history.back().kind.c_str());
  PersistentState restored;
  TEST_ASSERT_EQUAL_INT(static_cast<int>(LoadResult::ok),
                        static_cast<int>(fixture.persistence.load(restored)));
  TEST_ASSERT_EQUAL_UINT32(2, restored.history.size());
}

void event_stream_auth_rejects_setup_expiry_and_session_changes_invalidate_preview() {
  ApiFixture fixture;
  std::uint64_t expiry{};
  TEST_ASSERT_TRUE(fixture.api.authorize_event_token("0123456789abcdef", 1000, expiry));
  TEST_ASSERT_FALSE(fixture.api.authorize_event_token("0123456789abcdef", 100000, expiry));
  fixture.api.set_session({"setup-token-012345", AuthScope::setup, 200000});
  TEST_ASSERT_FALSE(fixture.api.authorize_event_token("setup-token-012345", 1000, expiry));

  const std::string imported =
      ",\"import\":{\"schemaVersion\":3,\"deviceName\":\"Imported\","
      "\"profiles\":[],\"history\":[]}";
  TEST_ASSERT_EQUAL_INT(200, fixture
                                 .request("POST", "/api/v1/import/preview",
                                          ApiFixture::command(imported), "preview-session")
                                 .status);
  fixture.api.set_session({"different-session-token", AuthScope::authenticated, 200000});
  TransportResponse apply = fixture.api.handle(
      {"POST", "/api/v1/import/apply", "application/json", "http://device.local",
       "Bearer different-session-token", "apply-session",
       ApiFixture::command(imported + ",\"previewToken\":\"fedcba9876543210fedcba9876543210\"")},
      1000);
  TEST_ASSERT_EQUAL_INT(422, apply.status);
}

void import_runtime_rejects_schema_parity_and_cross_record_inconsistencies() {
  ApiFixture fixture;
  const std::string calibration =
      "{\"schemaVersion\":2,\"tareValid\":false,\"valid\":false,"
      "\"provisional\":true,\"tareCode\":0,\"gramsPerCode\":0,"
      "\"unitMassGrams\":0,\"unitUncertaintyGrams\":0,"
      "\"calibrationResidualGrams\":0,\"knownCount\":0,\"createdMs\":0}";
  const std::string profile =
      "{\"id\":\"p1\",\"name\":\"Bolts\",\"lowStockThreshold\":0,"
      "\"calibrated\":false,\"provisional\":true,\"calibration\":" +
      calibration + "}";
  auto preview = [&](const std::string& contents, const std::string& key) {
    return fixture.request("POST", "/api/v1/import/preview",
                           ApiFixture::command(",\"import\":{\"schemaVersion\":3,"
                                               "\"deviceName\":\"Imported\"," +
                                               contents + "}"),
                           key);
  };
  TEST_ASSERT_EQUAL_INT(
      422,
      preview("\"profiles\":[" + profile + "," + profile + "],\"history\":[]", "duplicate-profile")
          .status);
  TEST_ASSERT_EQUAL_INT(422,
                        preview("\"profiles\":[],\"history\":[{\"sequence\":1,"
                                "\"deviceUptimeMs\":1,\"profileId\":\"missing\",\"kind\":\"count\","
                                "\"eventId\":\"evt-1\",\"reason\":\"\",\"count\":1}]",
                                "dangling-profile")
                            .status);
  std::string inconsistent = profile;
  const std::size_t calibrated = inconsistent.find("\"calibrated\":false");
  inconsistent.replace(calibrated, std::strlen("\"calibrated\":false"), "\"calibrated\":true");
  TEST_ASSERT_EQUAL_INT(
      422,
      preview("\"profiles\":[" + inconsistent + "],\"history\":[]", "metadata-mismatch").status);
  std::string bad_boolean = profile;
  const std::size_t provisional = bad_boolean.find("\"provisional\":true");
  bad_boolean.replace(provisional, std::strlen("\"provisional\":true"), "\"provisional\":1");
  TEST_ASSERT_EQUAL_INT(
      422, preview("\"profiles\":[" + bad_boolean + "],\"history\":[]", "bad-boolean").status);
  std::string nonfinite = profile;
  const std::size_t tare_code = nonfinite.find("\"tareCode\":0");
  nonfinite.replace(tare_code, std::strlen("\"tareCode\":0"), "\"tareCode\":1e999");
  TEST_ASSERT_EQUAL_INT(
      422, preview("\"profiles\":[" + nonfinite + "],\"history\":[]", "nonfinite").status);
  const std::string event_one =
      "{\"sequence\":2,\"deviceUptimeMs\":1,\"profileId\":\"p1\","
      "\"kind\":\"count\",\"eventId\":\"evt-1\",\"reason\":\"\",\"count\":1}";
  const std::string event_two =
      "{\"sequence\":1,\"deviceUptimeMs\":2,\"profileId\":\"p1\","
      "\"kind\":\"count\",\"eventId\":\"evt-1\",\"reason\":\"\",\"count\":2}";
  TEST_ASSERT_EQUAL_INT(422, preview("\"profiles\":[" + profile + "],\"history\":[" + event_one +
                                         "," + event_two + "]",
                                     "bad-history-order")
                                 .status);
  const std::string duplicate_event =
      "{\"sequence\":3,\"deviceUptimeMs\":2,\"profileId\":\"p1\","
      "\"kind\":\"count\",\"eventId\":\"evt-1\",\"reason\":\"\",\"count\":2}";
  TEST_ASSERT_EQUAL_INT(422, preview("\"profiles\":[" + profile + "],\"history\":[" + event_one +
                                         "," + duplicate_event + "]",
                                     "duplicate-event-id")
                                 .status);
  const std::string correction =
      "{\"sequence\":3,\"deviceUptimeMs\":3,\"profileId\":\"p1\","
      "\"kind\":\"correction\",\"eventId\":\"fix-1\",\"relatedEventId\":\"missing\","
      "\"reason\":\"recount\",\"count\":2}";
  TEST_ASSERT_EQUAL_INT(422, preview("\"profiles\":[" + profile + "],\"history\":[" + event_one +
                                         "," + correction + "]",
                                     "dangling-correction")
                                 .status);
  const std::string other_profile =
      "{\"id\":\"p2\",\"name\":\"Nuts\",\"lowStockThreshold\":0,"
      "\"calibrated\":false,\"provisional\":true,\"calibration\":" +
      calibration + "}";
  std::string cross_profile = correction;
  cross_profile.replace(cross_profile.find("\"missing\""), std::strlen("\"missing\""), "\"evt-1\"");
  cross_profile.replace(cross_profile.find("\"profileId\":\"p1\""),
                        std::strlen("\"profileId\":\"p1\""), "\"profileId\":\"p2\"");
  TEST_ASSERT_EQUAL_INT(422, preview("\"profiles\":[" + profile + "," + other_profile +
                                         "],\"history\":[" + event_one + "," + cross_profile + "]",
                                     "cross-profile-correction")
                                 .status);
}

void event_sequence_exposes_gap_recovery_information() {
  ApiFixture fixture;
  const std::string first = fixture.api.event("measurement.updated", "{}", 10);
  const std::string second = fixture.api.event("fault.raised", "{}", 20);
  TEST_ASSERT_NOT_NULL(std::strstr(first.c_str(), "\"sequence\":1"));
  TEST_ASSERT_NOT_NULL(std::strstr(second.c_str(), "\"sequence\":2"));
  EventSequencer client;
  client.accept(1);
  TEST_ASSERT_TRUE(client.gap(3));
  TEST_ASSERT_FALSE(client.gap(2));
}

}  // namespace

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(persistence_bounds_history_and_redacts_exports);
  RUN_TEST(restart_corruption_and_interrupted_write_are_safe);
  RUN_TEST(version_one_empty_state_migrates_atomically);
  RUN_TEST(version_two_history_migration_generates_valid_event_relationships);
  RUN_TEST(guard_enforces_presence_expiry_origin_json_and_authentication);
  RUN_TEST(setup_scope_provision_login_and_expiry_are_enforced);
  RUN_TEST(status_profiles_history_and_export_routes_return_real_data);
  RUN_TEST(profile_crud_correction_and_clear_are_persisted);
  RUN_TEST(history_pagination_is_bounded_and_cursor_based);
  RUN_TEST(history_query_rejects_every_malformed_form);
  RUN_TEST(tare_and_calibrate_routes_assert_domain_outcomes);
  RUN_TEST(failed_persistence_rolls_back_route_mutation);
  RUN_TEST(import_requires_preview_and_rejects_secrets_and_bad_schema);
  RUN_TEST(export_import_round_trip_preserves_correction_relationship);
  RUN_TEST(malformed_schema_replay_conflict_and_redaction_are_deterministic);
  RUN_TEST(event_sequence_exposes_gap_recovery_information);
  RUN_TEST(exact_routes_reject_lookalikes_and_corrections_require_real_references);
  RUN_TEST(stable_count_history_is_bounded_persisted_and_changes_only);
  RUN_TEST(event_stream_auth_rejects_setup_expiry_and_session_changes_invalidate_preview);
  RUN_TEST(import_runtime_rejects_schema_parity_and_cross_record_inconsistencies);
  return UNITY_END();
}
