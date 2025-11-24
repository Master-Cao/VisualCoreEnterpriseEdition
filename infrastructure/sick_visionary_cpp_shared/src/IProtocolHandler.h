//
// SPDX-License-Identifier: Unlicense
// 
// Created: November 2019
// 
// SICK AG, Waldkirch
// email: TechSupport0905@sick.de

#pragma once

#include <cstdint>
#include "CoLaCommand.h"

namespace visionary 
{

class IProtocolHandler
{
public:
  virtual ~IProtocolHandler() = default;
  virtual bool openSession(uint8_t sessionTimeout /*secs*/) = 0;
  virtual void closeSession() = 0;
  virtual CoLaCommand send(CoLaCommand cmd) = 0;
};

}
