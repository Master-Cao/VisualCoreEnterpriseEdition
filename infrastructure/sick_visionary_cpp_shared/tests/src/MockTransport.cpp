#include "MockTransport.h"
#include <iostream>
namespace visionary_test
{

MockTransport::MockTransport()
: m_fakeSendReturnActivated(false)
, m_fakeSendReturn(0)
, m_recBufPos(0u)
{}

visionary::ITransport::send_return_t MockTransport::send(const char*, size_t size)
{
    if(m_fakeSendReturnActivated)
    {
        return m_fakeSendReturn;
    }
    return static_cast<visionary::ITransport::send_return_t>(size);
}
visionary::ITransport::recv_return_t MockTransport::recv(std::vector<std::uint8_t>& buffer, std::size_t maxBytesToReceive)
{
    const auto returnSize = std::min(maxBytesToReceive, m_buffer.size() - m_recBufPos);
    auto first = std::next(m_buffer.begin(), static_cast<int64_t>(m_recBufPos));
    auto last = std::next(first, static_cast<int64_t>(returnSize));
    buffer.assign(first, last);
    m_recBufPos += returnSize;
    return static_cast<visionary::ITransport::recv_return_t>(returnSize);
}
visionary::ITransport::recv_return_t MockTransport::read(std::vector<std::uint8_t>& buffer, std::size_t nBytesToReceive)
{
    return recv(buffer, nBytesToReceive);
}

void MockTransport::setBuffer(const std::vector<std::uint8_t>& buffer)
{
    m_recBufPos = 0;
    m_buffer = buffer;
}

void MockTransport::setFakeSendReturn(bool activate, send_return_t size)
{
    m_fakeSendReturn = size;
    m_fakeSendReturnActivated = activate;
}

int MockTransport::shutdown()
{
    return 0;
}
int MockTransport::getLastError()
{
    return 0;
}

}