#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>
#include <WebServer.h>
#include <WebSocketsServer.h>
#include <WiFi.h>

#include <cstdint>
#include <map>
#include <string>
#include <vector>

#include "parts_tally/protocol.hpp"

namespace parts_tally {

class LocalTransport {
 public:
  explicit LocalTransport(ApiService& api) : api_(api), websocket_(81) {}

  void begin(const std::string& access_point_name) {
    WiFi.mode(WIFI_AP_STA);
    WiFi.softAP(access_point_name.c_str());

    const char* headers[] = {"Origin", "Authorization", "Idempotency-Key", "Content-Type"};
    http_.collectHeaders(headers, 4);
    http_.onNotFound([this]() { handle_http(); });
    http_.begin();

    websocket_.begin();
    static const char* websocket_headers[] = {"Origin"};
    websocket_.onValidateHttpHeader(
        [this](String name, String value) {
          return name != "Origin" || value == "http://192.168.4.1";
        },
        websocket_headers, 1);
    websocket_.onEvent(
        [this](std::uint8_t client, WStype_t type, std::uint8_t* payload, std::size_t length) {
          if (type == WStype_CONNECTED) {
            const std::string requested(reinterpret_cast<char*>(payload), length);
            if (requested != "/api/v1/events") websocket_.disconnect(client);
            authorized_clients_.erase(client);
          } else if (type == WStype_TEXT) {
            JsonDocument message;
            if (deserializeJson(message, payload, length) || message["type"] != "authenticate" ||
                !message["token"].is<const char*>()) {
              websocket_.disconnect(client);
              return;
            }
            std::uint64_t expires_ms{};
            if (!api_.authorize_event_token(message["token"].as<const char*>(), millis(),
                                            expires_ms)) {
              websocket_.disconnect(client);
              return;
            }
            authorized_clients_[client] = {message["token"].as<const char*>(), expires_ms};
          } else if (type == WStype_DISCONNECTED) {
            authorized_clients_.erase(client);
          }
        });
  }

  void begin_sta(const std::string& ssid, const std::string& password) {
    if (ssid.empty()) return;
    // WiFi.begin returns immediately; sampling and the direct AP remain available
    // while the ESP32 connection state machine performs its bounded retries.
    WiFi.begin(ssid.c_str(), password.c_str());
  }

  void poll() {
    http_.handleClient();
    websocket_.loop();
  }

  void broadcast(const std::string& event) {
    const std::uint64_t now = millis();
    std::vector<std::uint8_t> expired;
    for (auto client = authorized_clients_.begin(); client != authorized_clients_.end();) {
      std::uint64_t current_expiry{};
      if (now >= client->second.second ||
          !api_.authorize_event_token(client->second.first, now, current_expiry)) {
        expired.push_back(client->first);
        client = authorized_clients_.erase(client);
      } else {
        websocket_.sendTXT(client->first, event.c_str(), event.size());
        ++client;
      }
    }
    for (std::uint8_t client : expired) websocket_.disconnect(client);
  }

 private:
  static std::string method_name(HTTPMethod method) {
    switch (method) {
      case HTTP_GET:
        return "GET";
      case HTTP_POST:
        return "POST";
      case HTTP_PUT:
        return "PUT";
      case HTTP_PATCH:
        return "PATCH";
      case HTTP_DELETE:
        return "DELETE";
      default:
        return "UNSUPPORTED";
    }
  }

  void handle_http() {
    const std::string path = http_.uri().c_str();
    TransportRequest request;
    request.method = method_name(http_.method());
    request.path = path;
    request.content_type = http_.header("Content-Type").c_str();
    request.origin = http_.header("Origin").c_str();
    request.authorization = http_.header("Authorization").c_str();
    request.idempotency_key = http_.header("Idempotency-Key").c_str();
    request.body = http_.arg("plain").c_str();
    const TransportResponse response = api_.handle(request, millis());

    Serial.printf("api method=%s path=%s status=%d body=%s\n", request.method.c_str(),
                  request.path.c_str(), response.status,
                  ProtocolGuard::redact(request.body).c_str());
    http_.send(response.status, response.content_type.c_str(), response.body.c_str());
  }

  ApiService& api_;
  WebServer http_{80};
  WebSocketsServer websocket_;
  std::map<std::uint8_t, std::pair<std::string, std::uint64_t>> authorized_clients_;
};

}  // namespace parts_tally
