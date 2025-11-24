//
// SPDX-License-Identifier: Unlicense
// 
// Created: December 2019
// 
// SICK AG, Waldkirch
// email: TechSupport0905@sick.de

#pragma once
#include "VisionaryControl.h"

namespace visionary 
{

class AuthenticationLegacy:
  public IAuthentication
{
public:
  explicit AuthenticationLegacy(VisionaryControl& vctrl);
  ~AuthenticationLegacy() override;

  bool login(UserLevel userLevel, const std::string& password) override;
  bool logout() override;

private:
  VisionaryControl& m_VisionaryControl;
};

}
