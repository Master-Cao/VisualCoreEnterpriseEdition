//
// SPDX-License-Identifier: Unlicense
// 
// Created: November 2019
// 
// SICK AG, Waldkirch
// email: TechSupport0905@sick.de

#include "CoLaBProtocolHandler.h"

#include <cassert>

#include "VisionaryEndian.h"

namespace visionary 
{

CoLaBProtocolHandler::CoLaBProtocolHandler(ITransport& rTransport)
: m_rTransport(rTransport)
{
}

CoLaBProtocolHandler::~CoLaBProtocolHandler()
= default;

bool CoLaBProtocolHandler::openSession(uint8_t /*sessionTimeout secs*/)
{
  // we don't have a session id byte in CoLaB protocol. Nothing to do here.
  return true;
}

void CoLaBProtocolHandler::closeSession()
{
  // we don't have a session id byte in CoLaB protocol. Nothing to do here.
}

CoLaCommand CoLaBProtocolHandler::send(CoLaCommand cmd)
{
  //
  // convert cola cmd to vector buffer and add/fill header
  //

  std::vector<std::uint8_t> buffer;
  buffer = cmd.getBuffer();

  // insert magic bytes
  const uint8_t MAGIC_BYTE = 0x02;
  // inserts 8 bytes at front (Magic Bytes and length)
  auto it = buffer.begin();
  for (uint8_t i = 0; i < 8; i++)
  {
    it = buffer.insert(it, MAGIC_BYTE);
  }
  // Overwrite length
  assert(buffer.size() >=  4u + 4u + 8u);
  *reinterpret_cast<uint32_t*>(&buffer[4]) = nativeToBigEndian(static_cast<uint32_t>(buffer.size()) - 8);
  
  // Add checksum to end
  buffer.insert(buffer.end(), calculateChecksum(buffer));

  //
  // send to socket
  //
  if (m_rTransport.send(buffer) != static_cast<ITransport::send_return_t>(buffer.size()))
  {
    return CoLaCommand::networkErrorCommand();
  }
  buffer.clear();

  //
  // get response
  //

  size_t stxRecv = 0;

  while (stxRecv < 4)
  {
    if (m_rTransport.recv(buffer, 1) < 1)
    {
      break;
    }
    if (0x02 == buffer[0])
    {
      stxRecv++;
    }
    else
    {
      stxRecv = 0;
    }
  }
  buffer.clear();

  if (stxRecv == 4)
  {
    // get length
    m_rTransport.read(buffer, sizeof(uint32_t));
    const uint32_t length = readUnalignBigEndian<uint32_t>(buffer.data()) + 1; // packetlength is only the data without STx, Packet Length and Checksum, add Checksum to get end of data
    buffer.clear();
    m_rTransport.read(buffer, length);
  }

  CoLaCommand response(buffer);
  return response;
}

uint8_t CoLaBProtocolHandler::calculateChecksum(const std::vector<uint8_t>& buffer)
{
  uint8_t checksum = 0;
  for (size_t i = 8; i < buffer.size(); i++)
  {
    checksum ^= buffer[i];
  }
  return checksum;
}

}
