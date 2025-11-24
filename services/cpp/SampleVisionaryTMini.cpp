//
// Copyright note: Redistribution and use in source, with or without modification, are permitted.
// 
// Created: July 2020
// 
// @auther:  Patrick Ebner
// SICK AG, Waldkirch
// email: TechSupport0905@sick.de

#include <cstdio>
#include <iostream>
#include <memory>
#include <sstream>
#include <fstream>
#include <iterator>

#include "VisionaryControl.h"
#include "CoLaParameterReader.h"
#include "CoLaParameterWriter.h"
#include "VisionaryTMiniData.h"    // Header specific for the Time of Flight data
#include "VisionaryDataStream.h"
#include "PointXYZ.h"
#include "PointCloudPlyWriter.h"

#include <chrono>
#include <thread>

bool runStreamingDemo(const char ipAddress[], unsigned short dataPort, uint32_t numberOfFrames, bool executeExtTrigger)
{
  using namespace visionary;
  
  // Generate Visionary instance
  auto pDataHandler = std::make_shared<VisionaryTMiniData>();
  VisionaryDataStream dataStream(pDataHandler);
  VisionaryControl visionaryControl;

  //-----------------------------------------------
  // Connect to devices data stream 
  if (!dataStream.open(ipAddress, htons(dataPort)))
  {
    std::printf("Failed to open data stream connection to device.\n");
    return false;   // connection failed
  }

  //-----------------------------------------------
  // Connect to devices control channel
  if (!visionaryControl.open(VisionaryControl::ProtocolType::COLA_2, ipAddress, 5000/*ms*/))
  {
    std::printf("Failed to open control connection to device.\n");
    return false;   // connection failed
  }
  
  //-----------------------------------------------
  // read Device Ident
  std::printf("DeviceIdent: '%s'\n", visionaryControl.getDeviceIdent().c_str());

  //-----------------------------------------------
  // Login as authorized client
  if (visionaryControl.login(IAuthentication::UserLevel::AUTHORIZED_CLIENT, "CLIENT"))
  {
    //-----------------------------------------------
    // An example of reading an writing device parameters is shown here.
    // Use the "SOPAS Communication Interface Description" PDF to determine data types for other variables
    //-----------------------------------------------
    // Set enDepthMask parameter to false
    {
      std::printf("Setting enDepthMask to false\n");
      CoLaCommand setEnDepthMaskCommand = CoLaParameterWriter(CoLaCommandType::WRITE_VARIABLE, "enDepthMask").parameterBool(false).build();
      CoLaCommand setEnDepthMaskResponse = visionaryControl.sendCommand(setEnDepthMaskCommand);
      if (setEnDepthMaskResponse.getError() == CoLaError::OK)
      {
        std::printf("Successfully set enDepthMask to false\n");
      }
    }

    //-----------------------------------------------
    // Read humidity parameter
    CoLaCommand getHumidity = CoLaParameterWriter(CoLaCommandType::READ_VARIABLE, "humidity").build();
    CoLaCommand humidityResponse = visionaryControl.sendCommand(getHumidity);
    const double humidity = CoLaParameterReader(humidityResponse).readLReal();
    std::printf("Read humidity = %f\n", humidity);

    //-----------------------------------------------
    // Read info messages variable
    CoLaCommand getMessagesCommand = CoLaParameterWriter(CoLaCommandType::READ_VARIABLE, "MSinfo").build();
    CoLaCommand messagesResponse = visionaryControl.sendCommand(getMessagesCommand);

    std::printf("Setting frontendMode to STOP (= 1)\n");
    CoLaCommand setFrontendModeCommand = CoLaParameterWriter(CoLaCommandType::WRITE_VARIABLE, "frontendMode").parameterUSInt(1).build();
    CoLaCommand setFrontendModeResponse = visionaryControl.sendCommand(setFrontendModeCommand);
    if (setFrontendModeResponse.getError() != CoLaError::OK)
    {
      std::printf("Failed to set frontendMode to STOP (= 1)\n");
    }

    //-----------------------------------------------
  }

  {
    CoLaCommand setEnDepthMaskCommand = CoLaParameterWriter(CoLaCommandType::WRITE_VARIABLE, "enDepthMask").parameterBool(true).build();
    CoLaCommand setEnDepthMaskResponse = visionaryControl.sendCommand(setEnDepthMaskCommand);
    if (setEnDepthMaskResponse.getError() != CoLaError::OK)
    {
      std::printf("Failed to set enDepthMask to true\n");
    }
  }

  //-----------------------------------------------
  // Logout from device after reading variables.
  if (!visionaryControl.logout())
  {
    std::printf("Failed to logout\n");
  }
  
  //-----------------------------------------------
  // Stop image acquisition (works always, also when already stopped)
  visionaryControl.stopAcquisition();

  //-----------------------------------------------
  // Capture a single frame
  for (int i = 0; i < 10; ++i)
  {
    auto tStart = std::chrono::steady_clock::now();
  visionaryControl.stepAcquisition();
  bool gotFrame = dataStream.getNextFrame();
  auto tEnd = std::chrono::steady_clock::now();
  long long elapsedMs = std::chrono::duration_cast<std::chrono::milliseconds>(tEnd - tStart).count();
  if (gotFrame)
  {
    std::printf("Single frame #%d acquisition time: %lld ms\n", i + 1, (long long)elapsedMs);
    

    //-----------------------------------------------
    // Convert data to a point cloud
    std::vector<PointXYZ> pointCloud;
    pDataHandler->generatePointCloud(pointCloud);
    pDataHandler->transformPointCloud(pointCloud);

    //-----------------------------------------------
    // Write point cloud to PLY
      if (i == 0)
      {
        const char plyFilePath[] = "VisionaryT_Mini.ply";
    std::printf("Writing frame to %s\n", plyFilePath);
    PointCloudPlyWriter::WriteFormatPLY(plyFilePath, pointCloud, pDataHandler->getIntensityMap(), true);
        std::printf("Finished writing frame to %s\n", plyFilePath);
      }
  }
  else
  {
    std::printf("Single frame #%d acquisition failed after %lld ms\n", i + 1, (long long)elapsedMs);
  }
  }

  //-----------------------------------------------
  // Start image acquisiton and continously receive frames
  visionaryControl.startAcquisition();
  for (uint32_t i = 0; i < numberOfFrames; i++)
  {
    if (!dataStream.getNextFrame())
    {
      continue;     // No valid frame received
    }
    std::printf("Frame received in continuous mode, frame #%d \n", pDataHandler->getFrameNum());
    std::vector<uint16_t> intensityMap = pDataHandler->getIntensityMap();
    std::vector<uint16_t> distanceMap = pDataHandler->getDistanceMap();
    std::vector<uint16_t> stateMap = pDataHandler->getStateMap();
  }

  //-----------------------------------------------
  // This part of the sample code is skipped by default because not every user has a working IO trigger hardware available. 
  // If you want to execute it set variable "executeExtTrigger" in main function to "true".
  if (executeExtTrigger)
  {
    // Capture single frames with external trigger
    // NOTE: This part of the sample only works if you have a working rising egde signal on IO1 which triggers an image!
    std::printf("\n=== Starting external trigger example: \n");
    // Login as authorized client
    if (visionaryControl.login(IAuthentication::UserLevel::AUTHORIZED_CLIENT, "CLIENT"))
    {
      // Set frontendMode to STOP (= 1)
      std::printf("Setting frontendMode to STOP (= 1)\n");
      CoLaCommand setFrontendModeCommand = CoLaParameterWriter(CoLaCommandType::WRITE_VARIABLE, "frontendMode").parameterUSInt(1).build();
      CoLaCommand setFrontendModeResponse = visionaryControl.sendCommand(setFrontendModeCommand);
      if (setFrontendModeResponse.getError() != CoLaError::OK)
      {
        std::printf("Failed to set frontendMode to STOP (= 1)\n");
      }

      // Set INOUT1_Function to Trigger (= 7)
      std::printf("Setting DIO1Fnc to Trigger (= 7)\n");
      CoLaCommand setDIO1FncCommand = CoLaParameterWriter(CoLaCommandType::WRITE_VARIABLE, "DIO1Fnc").parameterUSInt(7).build();
      CoLaCommand setDIO1FncResponse = visionaryControl.sendCommand(setDIO1FncCommand);
      if (setDIO1FncResponse.getError() != CoLaError::OK)
      {
        std::printf("Failed to set DIO1Fnc to Trigger (= 7)\n");
      }

      // Set INOUT2_Function to TriggerBusy (= 23)
      std::printf("Setting DIO2Fnc to TriggerBusy (= 23)\n");
      CoLaCommand setDIO2FncCommand = CoLaParameterWriter(CoLaCommandType::WRITE_VARIABLE, "DIO2Fnc").parameterUSInt(23).build();
      CoLaCommand setDIO2FncResponse = visionaryControl.sendCommand(setDIO2FncCommand);
      if (setDIO2FncResponse.getError() != CoLaError::OK)
      {
        std::printf("Failed to set DIO2Fnc to TriggerBusy (= 23)\n");
      }
    }

    // Re-Connect to device data stream (make sure there are no old images in the pipeline)
    dataStream.close();
    std::this_thread::sleep_for(std::chrono::seconds(1)); // This short deelay is necessary to not have any old frames in the pipeline.
    if (!dataStream.open(ipAddress, htons(dataPort)))
    {
      std::printf("Failed to open data stream connection to device.\n");
      return false;   // connection failed
    }

    std::printf("Please enable trigger on IO1 to receive an image: \n");
    long long startTime = std::chrono::system_clock::now().time_since_epoch().count();
    long long timeNow = startTime;

    // Limited time loop for receiving hardware trigger signals on IO1 pin
    bool frameReceived = false;
    long long triggerTimeOut = 100000000; // 10 sec = 100 000 000
    while ((timeNow - startTime) <= triggerTimeOut) {
      // Read variable IOValue
      CoLaCommand getIOValue = CoLaParameterWriter(CoLaCommandType::READ_VARIABLE, "IOValue").build();
      CoLaCommand IOValueResponse = visionaryControl.sendCommand(getIOValue);
      CoLaParameterReader IOValues(IOValueResponse);
      const int8_t IOValue1 = IOValues.readSInt();
      const int8_t IOValue2 = IOValues.readSInt(); // We need the IOValue of IO2 from the V3SIOsState struct
      std::printf("Read TriggerBusy = %d\n", IOValue2);
      
      // Receive the next frame
      if (IOValue2 == 0)
      {
        if (dataStream.getNextFrame())
        {
          std::printf("Frame received in external trigger mode, frame #%d \n", pDataHandler->getFrameNum());
          frameReceived = true;
        }
        timeNow = std::chrono::system_clock::now().time_since_epoch().count();
      }
    }
  
    if (frameReceived == false)
    {
      std::printf("TIMEOUT: No trigger signal received on IO1 within %.2f seconds!\n", (float)triggerTimeOut/10000000);
    }
  }
  //-----------------------------------------------

  visionaryControl.close();
  dataStream.close();
  return true;
}

int main(int argc, char* argv[])
{
  // Insert IP and the API port of your camera, aswell as the number of images you want to receive via cmd/terminal
  /// Default values:
  /// IP:        "192.168.1.10"
  /// API-port:  2114

  std::string deviceIpAddr("192.168.2.99");
  unsigned short deviceBlobCtrlPort = 2114u;
  unsigned cnt = 100u;

  bool showHelpAndExit = false;
  bool executeExtTrigger = false;

  int exitCode = 0;

  for (int i = 1; i < argc; ++i)
  {
    std::istringstream argstream(argv[i]);

    if (argstream.get() != '-')
    {
      showHelpAndExit = true;
      exitCode = 1;
      break;
    }
    switch (argstream.get())
    {
    case 'h':
      showHelpAndExit = true;
      break;
    case 'c':
      argstream >> deviceBlobCtrlPort;
      break;
    case 'i':
      argstream >> deviceIpAddr;
      break;
    case 'n':
      argstream >> cnt;
      break;
    case 't':
      executeExtTrigger = true;
      break;
    default:
      showHelpAndExit = true;
      exitCode = 1;
      break;
    }
  }

  if (showHelpAndExit)
  {
    std::cout << argv[0] << " [option]*" << std::endl;
    std::cout << "where option is one of" << std::endl;
    std::cout << "-h          show this help and exit" << std::endl;
    std::cout << "-i<IP>      connect to the device with IP address <IP>; default is 192.168.1.10" << std::endl;
    std::cout << "-c<port>    assume the BLOB control port of the device was configured to <port>; default is 2114" << std::endl;
    std::cout << "-n<cnt>     acquire <cnt> frames and stop; default is 100" << std::endl;
    std::cout << "-t          execute external trigger example part" << std::endl;

    return exitCode;
  }

  runStreamingDemo(deviceIpAddr.c_str(), deviceBlobCtrlPort, cnt, executeExtTrigger);
}
