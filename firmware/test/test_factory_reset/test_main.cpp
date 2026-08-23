#include <unity.h>

#include "parts_tally/factory_reset.hpp"
using namespace parts_tally;
class Store : public IStorage {
 public:
  bool erased{}, fail{};
  bool read(const std::string&, std::vector<std::uint8_t>&) override { return false; }
  bool replace_atomically(const std::string&, const std::vector<std::uint8_t>&) override {
    return false;
  }
  bool erase_all() override {
    erased = !fail;
    return !fail;
  }
};
void exact_gesture() {
  Store s;
  FactoryResetGesture g(s);
  TEST_ASSERT_EQUAL_INT((int)ResetProgress::holding, (int)g.update(true, 100));
  TEST_ASSERT_EQUAL_INT((int)ResetProgress::warning, (int)g.update(true, 7100));
  TEST_ASSERT_FALSE(s.erased);
  TEST_ASSERT_EQUAL_INT((int)ResetProgress::erased, (int)g.update(true, 10100));
  TEST_ASSERT_TRUE(s.erased);
}
void early_release_cancels() {
  Store s;
  FactoryResetGesture g(s);
  g.update(true, 0);
  g.update(true, 8000);
  TEST_ASSERT_EQUAL_INT((int)ResetProgress::idle, (int)g.update(false, 9000));
  g.update(true, 10000);
  TEST_ASSERT_EQUAL_INT((int)ResetProgress::holding, (int)g.update(true, 16000));
  TEST_ASSERT_FALSE(s.erased);
}
void short_release_tares_and_later_long_press_never_resets() {
  Store s;
  ButtonPolicy policy(s);
  policy.begin(false, 0);
  TEST_ASSERT_EQUAL_INT((int)ButtonAction::idle, (int)policy.update(true, 100));
  TEST_ASSERT_EQUAL_INT((int)ButtonAction::tare, (int)policy.update(false, 500));
  policy.update(true, 1000);
  TEST_ASSERT_EQUAL_INT((int)ButtonAction::idle, (int)policy.update(true, 12000));
  TEST_ASSERT_FALSE(s.erased);
}
int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(exact_gesture);
  RUN_TEST(early_release_cancels);
  RUN_TEST(short_release_tares_and_later_long_press_never_resets);
  return UNITY_END();
}
