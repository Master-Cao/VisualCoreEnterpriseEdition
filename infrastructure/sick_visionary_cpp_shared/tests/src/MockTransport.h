//
// Copyright note: Redistribution and use in source, with or without modification, are permitted.
// 
// Created: March 2023
// 
// SICK AG, Waldkirch
// email: TechSupport0905@sick.de

#pragma once
#include <string>
#include <vector>

#include "ITransport.h"

namespace visionary_test
{

class MockTransport :
  public visionary::ITransport
{
public:
  MockTransport();

  void setBuffer(const std::vector<std::uint8_t>& buffer);
  void setFakeSendReturn(bool activate, send_return_t size);

  send_return_t send(const char* buffer, size_t size) override;
  recv_return_t recv(std::vector<std::uint8_t>& buffer, std::size_t maxBytesToReceive) override;
  recv_return_t read(std::vector<std::uint8_t>& buffer, std::size_t nBytesToReceive) override;

  int shutdown() override;
  int getLastError() override;
private:
    std::vector<std::uint8_t> m_buffer;
    bool m_fakeSendReturnActivated;
    send_return_t m_fakeSendReturn;
    size_t m_recBufPos;
};
}