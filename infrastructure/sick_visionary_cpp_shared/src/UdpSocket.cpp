//
// SPDX-License-Identifier: Unlicense
// 
// Created: January 2020
// 
// SICK AG, Waldkirch
// email: TechSupport0905@sick.de

#include <cstring>

#include "UdpSocket.h"

#include <iostream>

namespace visionary 
{

UdpSocket::UdpSocket()
: m_socket(0u)
{
  memset(&m_udpAddr, 0, sizeof(m_udpAddr));
}

int UdpSocket::connect(const std::string& hostname, uint16_t port)
{
  int iResult = 0;
  int trueVal = 1;
  long timeoutSeconds = 5L;
#ifdef _WIN32
  //-----------------------------------------------
  // Initialize Winsock
  WSADATA wsaData;
  iResult = ::WSAStartup(MAKEWORD(2, 2), &wsaData);
  if (iResult != NO_ERROR)
  {
    return iResult;
  }
#endif

  //-----------------------------------------------
  // Create a receiver socket to receive datagrams
  m_socket = ::socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
  if (m_socket == INVALID_SOCKET) {
    return -1;
  }

  //-----------------------------------------------
  // Bind the socket to any address and the specified port.
  m_udpAddr.sin_family = AF_INET;
  m_udpAddr.sin_port = port;
  if(inet_pton(AF_INET, hostname.c_str(), &m_udpAddr.sin_addr.s_addr)!= 1)
      return -1;
  // Set the timeout for the socket to 5 seconds
#ifdef _WIN32
  // On Windows timeout is a DWORD in milliseconds (https://docs.microsoft.com/en-us/windows/desktop/api/winsock/nf-winsock-setsockopt)
  long timeoutMs = timeoutSeconds * 1000L;
  iResult = setsockopt(m_socket, SOL_SOCKET, SO_RCVTIMEO, (const char*)&timeoutMs, sizeof(timeoutMs));
#else
  struct timeval tv;
  tv.tv_sec = timeoutSeconds;  /* 5 seconds Timeout */
  tv.tv_usec = 0L;  // Not init'ing this can cause strange errors
  iResult = setsockopt(m_socket, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&tv), sizeof(struct timeval));
#endif

  if (iResult >= 0)
  {
    iResult = setsockopt(m_socket, SOL_SOCKET, SO_BROADCAST, reinterpret_cast<const char*>(&trueVal), sizeof(trueVal));
  }

  return iResult;
}

int UdpSocket::shutdown()
{
  // Close the socket when finished receiving datagrams
#ifdef _WIN32
  closesocket(m_socket);
  WSACleanup();
#else
  close(m_socket);
#endif
  m_socket = INVALID_SOCKET;
  return 0;
}

ITransport::send_return_t UdpSocket::send(const char* pData, size_t size)
{
  // send buffer via UDP socket
  #ifdef _WIN32
  return sendto(m_socket, pData, static_cast<int>(size), 0, reinterpret_cast<struct sockaddr*>(&m_udpAddr), sizeof(m_udpAddr));
  #else
  return sendto(m_socket, pData, size, 0, reinterpret_cast<struct sockaddr*>(&m_udpAddr), sizeof(m_udpAddr));
  #endif
}

ITransport::recv_return_t UdpSocket::recv(std::vector<std::uint8_t>& buffer, std::size_t maxBytesToReceive)
{
  // receive from UDP Socket
  buffer.resize(maxBytesToReceive);
  char* pBuffer = reinterpret_cast<char*>(buffer.data());
#ifdef _WIN32
  return ::recv(m_socket, pBuffer, static_cast<int>(maxBytesToReceive), 0);
#else
  return ::recv(m_socket, pBuffer, maxBytesToReceive, 0);
#endif
  
}

ITransport::recv_return_t UdpSocket::read(std::vector<std::uint8_t>& buffer, std::size_t nBytesToReceive)
{
  // receive from UDP Socket
  buffer.resize(nBytesToReceive);
  char* pBuffer = reinterpret_cast<char*>(buffer.data());

  while (nBytesToReceive > 0)
  {
#ifdef _WIN32
    const ITransport::recv_return_t bytesReceived = ::recv(m_socket, pBuffer, static_cast<int>(nBytesToReceive), 0);
#else
  	const ITransport::recv_return_t bytesReceived = ::recv(m_socket, pBuffer, nBytesToReceive, 0);
#endif

    if (bytesReceived == SOCKET_ERROR || bytesReceived == 0)
    {
      return -1;
    }
    pBuffer += bytesReceived;
    nBytesToReceive -= static_cast<size_t>(bytesReceived);
  }
  return static_cast<ITransport::recv_return_t>(buffer.size());
}

int UdpSocket::getLastError()
{
    int error_code;
#ifdef _WIN32
    int error_code_size = sizeof(int);
    getsockopt(m_socket, SOL_SOCKET, SO_ERROR, (char*)(&error_code), &error_code_size);
#else
    socklen_t error_code_size = sizeof error_code;
    if (getsockopt(m_socket, SOL_SOCKET, SO_ERROR, &error_code, &error_code_size) != 0)
    {
        std::cout << "Error getting error code" << std::endl;
    }

#endif
    return error_code;
}

}
