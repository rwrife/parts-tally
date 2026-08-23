#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace parts_tally {

enum class SensorFault { none, disconnected, saturated, overload_indicated };
struct AdcSample {
  std::int32_t code{};
  std::uint64_t monotonic_ms{};
  SensorFault fault{SensorFault::none};
};

class IAdcReader {
 public:
  virtual ~IAdcReader() = default;
  virtual bool read(AdcSample& sample) = 0;
};
class IButton {
 public:
  virtual ~IButton() = default;
  virtual bool pressed() const = 0;
};
class IStatusIndicator {
 public:
  virtual ~IStatusIndicator() = default;
  virtual void set(bool red, bool green, bool blue) = 0;
};
class IClock {
 public:
  virtual ~IClock() = default;
  virtual std::uint64_t monotonic_ms() const = 0;
};
class IStorage {
 public:
  virtual ~IStorage() = default;
  virtual bool read(const std::string& key, std::vector<std::uint8_t>& value) = 0;
  // Replacement must become visible wholly or not at all after interruption.
  virtual bool replace_atomically(const std::string& key,
                                  const std::vector<std::uint8_t>& value) = 0;
  virtual bool erase_all() = 0;
};
struct TransportRequest {
  std::string method, path, content_type, origin, authorization, idempotency_key, body;
};
struct TransportResponse {
  int status{};
  std::string content_type{"application/json"};
  std::string body;
};
class IProtocolTransport {
 public:
  virtual ~IProtocolTransport() = default;
  virtual void respond(const TransportResponse&) = 0;
};

namespace pins {
constexpr int sda = 6, scl = 7, button = 3, rgb_red = 4, rgb_green = 5, rgb_blue = 10;
constexpr int uart_tx = 21, uart_rx = 20;
}  // namespace pins
}  // namespace parts_tally
