//
// SPDX-License-Identifier: Unlicense
// 
// Created: November 2019
// 
// SICK AG, Waldkirch
// email: TechSupport0905@sick.de

#pragma once
#include "IProtocolHandler.h"
#include "ITransport.h"
#include "CoLaCommand.h"

namespace visionary 
{

class CoLaBProtocolHandler:
  public IProtocolHandler
{
public:
  CoLaBProtocolHandler(ITransport& rTransport);
  ~CoLaBProtocolHandler() override;

  bool openSession(uint8_t sessionTimeout /*secs*/) override;
  void closeSession() override;

  // send cola cmd and receive cola response
  CoLaCommand send(CoLaCommand cmd) override;

private:
  ITransport& m_rTransport;
  uint8_t calculateChecksum(const std::vector<uint8_t>& buffer);
};

}
