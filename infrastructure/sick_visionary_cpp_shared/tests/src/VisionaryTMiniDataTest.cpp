#include "gtest/gtest.h"
#include "VisionaryTMiniData.h"
#include "VisionaryDataStream.h"
#include "MockTransport.h"
#include "VisionaryEndian.h"

namespace {
  void appendToVector(const std::vector<uint8_t>& src, std::vector<uint8_t>& dst)
  {
    dst.reserve(src.size() + dst.size());
    dst.insert(dst.end(), src.begin(), src.end());
  }
  std::vector<uint8_t> uint32ToBEVector(uint32_t n)
  {
    std::vector<uint8_t> retVal;
    retVal.push_back((n >> 24) & 0xFF);
    retVal.push_back((n >> 16) & 0xFF);
    retVal.push_back((n >> 8) & 0xFF);
    retVal.push_back(n  & 0xFF);
    return retVal;
  }
  

  void setBlobLength(std::vector<uint8_t>& blobVector)
  {
    auto blobLengthVector = uint32ToBEVector(blobVector.size() - 8u);
    memcpy(&blobVector[4], &blobLengthVector[0], 4u);
  }

  const std::vector<uint8_t> kMagicBytes = { 0x02, 0x02, 0x02, 0x02 };
  const std::vector<uint8_t> kProtocolVersion = { 0x0, 0x1 };
  const std::vector<uint8_t> kPackageType = { 0x62u };
  const std::vector<uint8_t> kBlobId = { 0x0u, 0x0u };
  const std::vector<uint8_t> kNumSegements = { 0x0u, 0x3u };
  const std::vector<uint8_t> kXMLOffset = { 0x0u, 0x0u, 0x0u, 0x1Cu};
  const std::vector<uint8_t> kBlobVersion = { 0x0u, 0x2u};
  const uint32_t kDataSetSize = 1302528;
  const std::string kXMLStr = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><SickRecord xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:noNamespaceSchemaLocation=\"SickRecord_schema.xsd\"><Revision>SICK V1.10 in work</Revision><SchemaChecksum>01020304050607080910111213141516</SchemaChecksum><ChecksumFile>checksum.hex</ChecksumFile><RecordDescription><Location>V3SXX5-1</Location><StartDateTime>2023-03-31T11:09:33+02:00</StartDateTime><EndDateTime>2023-03-31T11:09:37+02:00</EndDateTime><UserName>default</UserName><RecordToolName>Sick Scandata Recorder</RecordToolName><RecordToolVersion>v0.4</RecordToolVersion><ShortDescription></ShortDescription></RecordDescription><DataSets><DataSetDepthMap id=\"1\" datacount=\"1\"><DeviceDescription><Family>V3SXX5-1</Family><Ident>Visionary-T Mini CX V3S105-1x 2.0.0.457B</Ident><Version>3.0.0.2334</Version><SerialNumber>12345678</SerialNumber><LocationName>not defined</LocationName><IPAddress>192.168.136.10</IPAddress></DeviceDescription><FormatDescriptionDepthMap><TimestampUTC/><Version>uint16</Version><DataStream><Interleaved>false</Interleaved><Width>512</Width><Height>424</Height><CameraToWorldTransform><value>1.000000</value><value>0.000000</value><value>0.000000</value><value>0.000000</value><value>0.000000</value><value>1.000000</value><value>0.000000</value><value>0.000000</value><value>0.000000</value><value>0.000000</value><value>1.000000</value><value>-10.000000</value><value>0.000000</value><value>0.000000</value><value>0.000000</value><value>1.000000</value></CameraToWorldTransform><CameraMatrix><FX>-366.964999</FX><FY>-367.057999</FY><CX>252.118999</CX><CY>205.213999</CY></CameraMatrix><CameraDistortionParams><K1>-0.076050</K1><K2>0.217518</K2><P1>0.000000</P1><P2>0.000000</P2><K3>0.000000</K3></CameraDistortionParams><FrameNumber>uint32</FrameNumber><Quality>uint8</Quality><Status>uint8</Status><PixelSize><X>1.000000</X><Y>1.000000</Y><Z>0.250000</Z></PixelSize><Distance decimalexponent=\"0\" min=\"1\" max=\"16384\">uint16</Distance><Intensity decimalexponent=\"0\" min=\"1\" max=\"20000\">uint16</Intensity><Confidence decimalexponent=\"0\" min=\"0\" max=\"65535\">uint16</Confidence></DataStream><DeviceInfo><Status>OK</Status></DeviceInfo></FormatDescriptionDepthMap><DataLink><FileName>data.bin</FileName><Checksum>01020304050607080910111213141516</Checksum></DataLink><OverlayLink><FileName>overlay.xml</FileName></OverlayLink></DataSetDepthMap></DataSets></SickRecord>";
  const std::vector<uint8_t> kXMLVec(kXMLStr.c_str(), kXMLStr.c_str() + kXMLStr.size()); 
}

using namespace visionary;
//---------------------------------------------------------------------------------------

class VisionaryTMiniDataTest
  : public ::testing::Test
{
public:
  VisionaryTMiniDataTest()
  : m_dataHandler(std::make_shared<VisionaryTMiniData>())
  , m_dataStream(m_dataHandler)
  {
  }
protected:
  void SetUp() override
  {
  }

  void TearDown() override
  {
  }
  //visionary_test::MockTransport m_transport;
  std::shared_ptr<VisionaryTMiniData> m_dataHandler;
  VisionaryDataStream m_dataStream;
  
  
};

//---------------------------------------------------------------------------------------
TEST_F(VisionaryTMiniDataTest, InvalidMagicBytes)
{
    std::vector<uint8_t> buffer = kMagicBytes;
    buffer[3] = 0x01;
    buffer.insert(buffer.end(), 5000, 0);
    auto pMockTransport = new visionary_test::MockTransport();
    pMockTransport->setBuffer(buffer);
    std::unique_ptr<ITransport> pITransport (pMockTransport);
    m_dataStream.open(pITransport);
    ASSERT_FALSE(m_dataStream.getNextFrame());
}

//---------------------------------------------------------------------------------------
TEST_F(VisionaryTMiniDataTest, MissingHeader)
{
    std::vector<uint8_t> buffer = kMagicBytes;
    auto pMockTransport = new visionary_test::MockTransport();
    pMockTransport->setBuffer(buffer);
    std::unique_ptr<ITransport> pITransport (pMockTransport);
    m_dataStream.open(pITransport);
    ASSERT_FALSE(m_dataStream.getNextFrame());
}

//---------------------------------------------------------------------------------------
TEST_F(VisionaryTMiniDataTest, WrongHeader)
{
    std::vector<uint8_t> buffer = kMagicBytes;
    std::vector<uint8_t> length = { 0x0, 0x0, 0x0, 0x2 };
    std::vector<uint8_t> wrongProtocol = { 0x0, 0x0 };
    appendToVector(length, buffer);
    auto pMockTransport = new visionary_test::MockTransport();
    pMockTransport->setBuffer(buffer);
    {
        std::unique_ptr<ITransport> pITransport (pMockTransport);
        m_dataStream.open(pITransport);
        EXPECT_FALSE(m_dataStream.getNextFrame());
    }
    
    // Wrong Protocol
    pMockTransport = new visionary_test::MockTransport();
    buffer = kMagicBytes;
    length = {0x0, 0x0, 0x0, 0x3};
    appendToVector(length, buffer);
    appendToVector(wrongProtocol, buffer);
    appendToVector(kPackageType, buffer);
    pMockTransport->setBuffer(buffer);
    {
        std::unique_ptr<ITransport> pITransport (pMockTransport);
        m_dataStream.open(pITransport);
        EXPECT_FALSE(m_dataStream.getNextFrame());
    }

    // Wrong Package Type
    pMockTransport = new visionary_test::MockTransport();
    buffer = kMagicBytes;
    length = {0x0, 0x0, 0x0, 0x3};
    appendToVector(length, buffer);
    appendToVector(kProtocolVersion, buffer);
    buffer.push_back(0x61);
    pMockTransport->setBuffer(buffer);
    {
        std::unique_ptr<ITransport> pITransport (pMockTransport);
        m_dataStream.open(pITransport);
        EXPECT_FALSE(m_dataStream.getNextFrame());
    }
    
}

//---------------------------------------------------------------------------------------
TEST_F(VisionaryTMiniDataTest, NoDataHandler)
{
    std::vector<uint8_t> buffer = kMagicBytes;
    std::vector<uint8_t> length = { 0x0, 0x0, 0xFFu, 0xFFu };
    appendToVector(length, buffer);
    appendToVector(kProtocolVersion, buffer);
    appendToVector(kPackageType, buffer);
    //Append dummy data
    buffer.insert(buffer.end(), 65536u + 3u, 0u);
    auto pMockTransport = new visionary_test::MockTransport();
    pMockTransport->setBuffer(buffer);
    {
        std::unique_ptr<ITransport> pITransport (pMockTransport);
        m_dataStream.setDataHandler(nullptr);
        m_dataStream.open(pITransport);
        EXPECT_FALSE(m_dataStream.getNextFrame());
    }
    
}

//---------------------------------------------------------------------------------------
TEST_F(VisionaryTMiniDataTest, InvalidBlobData)
{
    std::vector<uint8_t> buffer = kMagicBytes;
    std::vector<uint8_t> length = { 0x0u, 0x0u, 0xFFu, 0xFFu };
    appendToVector(length, buffer);
    appendToVector(kProtocolVersion, buffer);
    appendToVector(kPackageType, buffer);
    std::vector<uint8_t> bufferBase = buffer;
    //Append dummy data
    buffer.insert(buffer.end(), 65536u + 3u, 0u);
    // Invalid segment count
    auto pMockTransport = new visionary_test::MockTransport();
    pMockTransport->setBuffer(buffer);
    {
        std::unique_ptr<ITransport> pITransport (pMockTransport);
        m_dataStream.open(pITransport);
        EXPECT_FALSE(m_dataStream.getNextFrame());
    }
    // Corrupted XML part
    buffer = bufferBase;
    appendToVector(kBlobId, buffer);
    appendToVector(kNumSegements, buffer);
    appendToVector(kXMLOffset, buffer);
    buffer.insert(buffer.end(), 3u, 0x0u);
    buffer.push_back(0x1u); // set change counter to 1
    uint32_t binaryOffset = kXMLVec.size() + 28u;
    const auto binaryOffsetVec = uint32ToBEVector(binaryOffset);
    appendToVector(binaryOffsetVec, buffer);
    buffer.insert(buffer.end(), 4u, 0x0u);
    const auto footerOffsetVec = uint32ToBEVector(binaryOffset + kDataSetSize + 4u + 8u + 2u + 6u + 8u);
    appendToVector(footerOffsetVec, buffer);
    buffer.insert(buffer.end(), 4u, 0x0u);
    appendToVector(kXMLVec, buffer);
    const auto bufferWithXMLBase = buffer;
    buffer.erase(buffer.end()- 10, buffer.end());
    setBlobLength(buffer);
    pMockTransport = new visionary_test::MockTransport();
    pMockTransport->setBuffer(buffer);
    {
        std::unique_ptr<ITransport> pITransport (pMockTransport);
        m_dataStream.open(pITransport);
        EXPECT_FALSE(m_dataStream.getNextFrame());
    }

  {
    // Corrupted Binary part
    buffer = bufferWithXMLBase;
    std::vector<uint8_t> binLengthVec = uint32ToBEVector(kDataSetSize);
    std::reverse(binLengthVec.begin(), binLengthVec.end());
    appendToVector(binLengthVec, buffer);
    buffer.insert(buffer.end(), 8u, 0x0u); // Timestamp
    appendToVector(kBlobVersion, buffer);
    buffer.insert(buffer.end(), 6u, 0x0u); // Extended Header
    buffer.insert(buffer.end(), kDataSetSize, 0x0u); // Add Image Data (4 bytes(CRC) are missing)
    setBlobLength(buffer);
    pMockTransport = new visionary_test::MockTransport();
    pMockTransport->setBuffer(buffer);
    {
        std::unique_ptr<ITransport> pITransport (pMockTransport);
        m_dataStream.open(pITransport);
        EXPECT_FALSE(m_dataStream.getNextFrame());
    }
  }
}

//---------------------------------------------------------------------------------------
TEST_F(VisionaryTMiniDataTest, ValidBlobData)
{
  std::vector<uint8_t> buffer = kMagicBytes;
  std::vector<uint8_t> length = { 0x0u, 0x0u, 0x00u, 0x00u };
  appendToVector(length, buffer);
  appendToVector(kProtocolVersion, buffer);
  appendToVector(kPackageType, buffer);
  appendToVector(kBlobId, buffer);
  appendToVector(kNumSegements, buffer);
  appendToVector(kXMLOffset, buffer);
  buffer.insert(buffer.end(), 3u, 0x0u);
  buffer.push_back(0x1u); // set change counter to 1
  uint32_t binaryOffset = kXMLVec.size() + 28u;
  const auto binaryOffsetVec = uint32ToBEVector(binaryOffset);
  appendToVector(binaryOffsetVec, buffer);
  buffer.insert(buffer.end(), 4u, 0x0u);
  const auto footerOffsetVec = uint32ToBEVector(binaryOffset +  kDataSetSize + 4u + 8u + 2u + 6u + 8u);
  appendToVector(footerOffsetVec, buffer);
  buffer.insert(buffer.end(), 4u, 0x0u);
  appendToVector(kXMLVec, buffer);
  std::vector<uint8_t> binLengthVec = uint32ToBEVector(kDataSetSize);
  std::reverse(binLengthVec.begin(), binLengthVec.end());
  appendToVector(binLengthVec, buffer);
  buffer.insert(buffer.end(), 8u, 0x0u); // Timestamp
  appendToVector(kBlobVersion, buffer);
  buffer.insert(buffer.end(), 6u, 0x0u); // Extended Header
  buffer.insert(buffer.end(), kDataSetSize, 0x0u); // Add Image Data
  buffer.insert(buffer.end(), 4u, 0x0u); // CRC
  appendToVector(binLengthVec, buffer);
  setBlobLength(buffer);
  auto pMockTransport = new visionary_test::MockTransport();
  pMockTransport->setBuffer(buffer);
  {
      std::unique_ptr<ITransport> pITransport (pMockTransport);
      m_dataStream.open(pITransport);
      EXPECT_TRUE(m_dataStream.getNextFrame());
  }
}