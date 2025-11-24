//
// SPDX-License-Identifier: Unlicense
// 
// Created: November 2019
// 
// SICK AG, Waldkirch
// email: TechSupport0905@sick.de

#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace visionary 
{

class ITransport
{
public:
#ifdef _WIN32
  using send_return_t = int;
  using recv_return_t = int;
#else
  using send_return_t = ssize_t;
  using recv_return_t = ssize_t;
#endif

  virtual ~ITransport() = default; // destructor, use it to call destructor of the inherit classes

  virtual int shutdown() = 0;
  virtual int getLastError() = 0;

  /// Send data on socket to device
  ///
  /// \e All bytes are sent on the socket. It is regarded as error if this is not possible.
  ///
  /// \param[in] buffer buffer containing the bytes that shall be sent.
  ///
  /// \return OS error code.
  template <typename T>
  send_return_t send(const std::vector<T>& buffer) {
    return send(reinterpret_cast<const char*>(buffer.data()), buffer.size()*sizeof(T));
  }


  /// Receive data on socket to device
  ///
  /// Receive at most \a maxBytesToReceive bytes.
  ///
  /// \param[in] buffer buffer containing the bytes that shall be sent.
  /// \param[in] maxBytesToReceive maximum number of bytes to receive.
  ///
  /// \return number of received bytes, negative values are OS error codes.
  virtual recv_return_t recv(std::vector<std::uint8_t>& buffer, std::size_t maxBytesToReceive) = 0;

  /// Read a number of bytes
  ///
  /// Contrary to recv this method reads precisely \a nBytesToReceive bytes.
  ///
  /// \param[in] buffer buffer containing the bytes that shall be sent.
  /// \param[in] nBytesToReceive maximum number of bytes to receive.
  ///
  /// \return number of received bytes, negative values are OS error codes.
  virtual recv_return_t read(std::vector<std::uint8_t>& buffer, std::size_t nBytesToReceive) = 0;

protected:
  virtual send_return_t send(const char* pData, size_t size) = 0;

};

}
