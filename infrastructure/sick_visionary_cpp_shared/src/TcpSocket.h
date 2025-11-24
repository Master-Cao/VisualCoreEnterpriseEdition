//
// SPDX-License-Identifier: Unlicense
// 
// Created: November 2019
// 
// SICK AG, Waldkirch
// email: TechSupport0905@sick.de

#pragma once
#include <string>
#include <cstdint>

#include "ITransport.h"

// Include socket
#ifdef _WIN32    // Windows specific
#include <winsock2.h>
#include <ws2tcpip.h>
// to use with other compiler than Visual C++ need to set Linker flag -lws2_32
#ifdef _MSC_VER
#pragma comment(lib,"ws2_32.lib")
#endif
#else        // Linux specific
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>

typedef int SOCKET;
#define INVALID_SOCKET  (SOCKET(~0))
#define SOCKET_ERROR    (-1)
#endif

namespace visionary 
{

class TcpSocket :
  public ITransport
{
public:
  TcpSocket();
  int connect(const std::string& hostname, uint16_t port, long timeoutMs = 5000);
  int shutdown() override;
  int getLastError() override;

  using ITransport::send;
  send_return_t send(const char* pData, size_t size) override;
  recv_return_t recv(std::vector<std::uint8_t>& buffer, std::size_t maxBytesToReceive) override;
  recv_return_t read(std::vector<std::uint8_t>& buffer, std::size_t nBytesToReceive) override;

private:
  SOCKET m_socket;
};

}
