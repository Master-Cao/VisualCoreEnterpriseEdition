#include "gtest/gtest.h"
#include "CoLa2ProtocolHandler.h"
#include "CoLaParameterWriter.h"
#include "MockTransport.h"
#include "VisionaryEndian.h"

using namespace visionary;
//---------------------------------------------------------------------------------------
class CoLa2ProtocolHandlerTest
  : public ::testing::Test
{
public:
  CoLa2ProtocolHandlerTest()
  :  m_protocolHandler(m_transport)
  {}
protected:
  void SetUp() override
  {
  }

  void TearDown() override
  {
  }
  visionary_test::MockTransport m_transport;
  CoLa2ProtocolHandler m_protocolHandler;
  std::vector<uint8_t> buildColaAnswer(const std::string& answer)
  {
      std::vector<uint8_t> buffer = { 0x02, 0x02, 0x02, 0x02};
      const auto length = nativeToBigEndian(static_cast<uint32_t>(answer.size()));
      buffer.insert(buffer.end(), reinterpret_cast<const uint8_t*>(&length), reinterpret_cast<const uint8_t*>(&length) + 4);
      buffer.insert(buffer.end(), answer.begin(), answer.end());
      return buffer;
  }
};

//---------------------------------------------------------------------------------------
TEST_F(CoLa2ProtocolHandlerTest, InvalidMagicBytes)
{
    std::vector<uint8_t> buffer = { 0x02, 0x02, 0x02, 0x01 };
    m_transport.setBuffer(buffer);
    CoLaCommand testCommand = CoLaParameterWriter(CoLaCommandType::READ_VARIABLE, "framePeriodTime").build();
    auto recVal = m_protocolHandler.send(testCommand);
    EXPECT_EQ(CoLaError::UNKNOWN, recVal.getError());
}

TEST_F(CoLa2ProtocolHandlerTest, EmptyAnswer)
{
    std::vector<uint8_t> buffer = { 0x02, 0x02, 0x02, 0x02 };
    m_transport.setBuffer(buffer);
    CoLaCommand testCommand = CoLaParameterWriter(CoLaCommandType::READ_VARIABLE, "framePeriodTime").build();
    auto recVal = m_protocolHandler.send(testCommand);
    EXPECT_EQ(CoLaError::NETWORK_ERROR, recVal.getError());
}

TEST_F(CoLa2ProtocolHandlerTest, EmptyPackage)
{
    std::vector<uint8_t> buffer;
    m_transport.setBuffer(buffer);
    CoLaCommand testCommand = CoLaParameterWriter(CoLaCommandType::READ_VARIABLE, "framePeriodTime").build();
    auto recVal = m_protocolHandler.send(testCommand);
    EXPECT_EQ(CoLaError::NETWORK_ERROR, recVal.getError());
}

TEST_F(CoLa2ProtocolHandlerTest, InvalidCode)
{
    const auto buffer = buildColaAnswer("FB");
    m_transport.setBuffer(buffer);
    CoLaCommand testCommand = CoLaParameterWriter(CoLaCommandType::READ_VARIABLE, "framePeriodTime").build();
    auto recVal = m_protocolHandler.send(testCommand);
    EXPECT_EQ(CoLaError::OK, recVal.getError());
}

TEST_F(CoLa2ProtocolHandlerTest, ReadVariable)
{
    const auto buffer = buildColaAnswer("RA 1234567890");
    m_transport.setBuffer(buffer);
    CoLaCommand testCommand = CoLaParameterWriter(CoLaCommandType::READ_VARIABLE, "framePeriodTime").build();
    auto recVal = m_protocolHandler.send(testCommand);
    EXPECT_EQ(CoLaError::OK, recVal.getError());
}

TEST_F(CoLa2ProtocolHandlerTest, WriteVariable)
{
    const auto buffer = buildColaAnswer("WA 1234567890");
    m_transport.setBuffer(buffer);
    CoLaCommand testCommand = CoLaParameterWriter(CoLaCommandType::READ_VARIABLE, "framePeriodTime").build();
    auto recVal = m_protocolHandler.send(testCommand);
    EXPECT_EQ(CoLaError::OK, recVal.getError());
}

TEST_F(CoLa2ProtocolHandlerTest, MethodAnswer)
{
    const auto buffer = buildColaAnswer("AN 1234567890");
    m_transport.setBuffer(buffer);
    CoLaCommand testCommand = CoLaParameterWriter(CoLaCommandType::READ_VARIABLE, "framePeriodTime").build();
    auto recVal = m_protocolHandler.send(testCommand);
    EXPECT_EQ(CoLaError::OK, recVal.getError());
}

TEST_F(CoLa2ProtocolHandlerTest, ColaErrorTooShort)
{
    const auto buffer = buildColaAnswer("FA5");
    m_transport.setBuffer(buffer);
    CoLaCommand testCommand = CoLaParameterWriter(CoLaCommandType::READ_VARIABLE, "framePeriodTime").build();
    auto recVal = m_protocolHandler.send(testCommand);
    EXPECT_EQ(CoLaError::UNKNOWN, recVal.getError());
}

TEST_F(CoLa2ProtocolHandlerTest, ColaErrorIncomplete)
{
    const auto buffer = buildColaAnswer("FA ");
    m_transport.setBuffer(buffer);
    CoLaCommand testCommand = CoLaParameterWriter(CoLaCommandType::READ_VARIABLE, "framePeriodTime").build();
    auto recVal = m_protocolHandler.send(testCommand);
    EXPECT_EQ(CoLaError::UNKNOWN, recVal.getError());
}

TEST_F(CoLa2ProtocolHandlerTest, ColaErrorValid)
{
    auto buffer = buildColaAnswer("FAxx");
    buffer.data()[11] = 4;
    buffer.data()[10] = 0;
    m_transport.setBuffer(buffer);
    CoLaCommand testCommand = CoLaParameterWriter(CoLaCommandType::READ_VARIABLE, "framePeriodTime").build();
    auto recVal = m_protocolHandler.send(testCommand);
    EXPECT_EQ(CoLaError::LOCAL_CONDITION_FAILED, recVal.getError());
}

TEST_F(CoLa2ProtocolHandlerTest, SendFailed)
{
    m_transport.setFakeSendReturn(true, -1);
    CoLaCommand testCommand = CoLaParameterWriter(CoLaCommandType::READ_VARIABLE, "framePeriodTime").build();
    auto recVal = m_protocolHandler.send(testCommand);
    EXPECT_EQ(CoLaError::NETWORK_ERROR, recVal.getError());
}

TEST_F(CoLa2ProtocolHandlerTest, OpenSession)
{
    std::vector<uint8_t> buffer = { 0x02, 0x02, 0x02, 0x02 };
    m_transport.setBuffer(buffer);
    EXPECT_FALSE(m_protocolHandler.openSession(50u));
}

TEST_F(CoLa2ProtocolHandlerTest, OpenSessionEmptySession)
{
    std::vector<uint8_t> buffer = { 0x02, 0x02, 0x02, 0x02 };
    m_transport.setBuffer(buffer);
    EXPECT_FALSE(m_protocolHandler.openSession(50u));
}

TEST_F(CoLa2ProtocolHandlerTest, OpenSessionInvalidMagic)
{
    std::vector<uint8_t> buffer = { 0x02, 0x02, 0x02, 0x01 };
    m_transport.setBuffer(buffer);
    EXPECT_FALSE(m_protocolHandler.openSession(50u));
}

TEST_F(CoLa2ProtocolHandlerTest, OpenSessionValid)
{
    std::vector<uint8_t> buffer = { 0x02, 0x02, 0x02, 0x02, 0x0 ,0x0, 0x0, 0x4, 0x1, 0x1, 0x1, 0x1};
    m_transport.setBuffer(buffer);
    EXPECT_TRUE(m_protocolHandler.openSession(50u));
}

TEST_F(CoLa2ProtocolHandlerTest, OpenSessioninValid)
{
    std::vector<uint8_t> buffer = { 0x02, 0x02, 0x02, 0x02, 0x0 ,0x0, 0x0, 0x1, 0x1};
    m_transport.setBuffer(buffer);
    EXPECT_FALSE(m_protocolHandler.openSession(50u));
}

