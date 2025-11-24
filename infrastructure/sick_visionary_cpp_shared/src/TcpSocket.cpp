//
// SPDX-License-Identifier: Unlicense
// 
// Created: November 2019
// 
// SICK AG, Waldkirch
// email: TechSupport0905@sick.de
#include <stdexcept>  
#include "TcpSocket.h"
#include <fcntl.h>

#include <iostream>

namespace visionary
{

    TcpSocket::TcpSocket()
        : m_socket(0u)
    {
    }

    int TcpSocket::connect(const std::string& hostname, uint16_t port, long timeoutMs)
    {
        int iResult = 0;
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
        m_socket = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
        if (m_socket == INVALID_SOCKET) {
            return -1;
        }

        //-----------------------------------------------
        // Bind the socket to any address and the specified port.
        sockaddr_in recvAddr{};
        recvAddr.sin_family = AF_INET;
        recvAddr.sin_port = port;
        if(inet_pton(AF_INET, hostname.c_str(), &recvAddr.sin_addr.s_addr) != 1)
            return -1;
        {
#ifdef _WIN32
            unsigned long block = 1;
            ioctlsocket(static_cast<unsigned int>(m_socket), FIONBIO, &block);
#else
            int flags = fcntl(m_socket, F_GETFL, 0);
            if (flags == -1) 
            { 
                close(m_socket); 
                return -1; 
            }
            flags |= O_NONBLOCK;
            if (::fcntl(m_socket, F_SETFL, flags) == -1)
            {
                close(m_socket);
                return -1;
            }
#endif
        }
        // calculate the timeout in seconds and microseconds
        #ifdef _WIN32
        long timeoutSeconds = timeoutMs / 1000;
        long timeoutUSeconds = (timeoutMs % 1000) * 1000;
        #else
        time_t timeoutSeconds = timeoutMs / 1000;
        suseconds_t timeoutUSeconds = (timeoutMs % 1000) * 1000;
        #endif
        //applying the calculated values
        struct timeval tv;
        tv.tv_sec = timeoutSeconds;
        tv.tv_usec = timeoutUSeconds;

        iResult = ::connect(m_socket, reinterpret_cast<sockaddr*>(&recvAddr), sizeof(recvAddr));
        if (iResult != 0)
        {
#ifdef _WIN32
            if (WSAGetLastError() != WSAEWOULDBLOCK)
            {
                closesocket(m_socket);
                return -1;
            }
#else
            if (errno != EINPROGRESS)
            {
                close(m_socket);
                return -1;
            }
#endif
            fd_set setW, setE;
            FD_ZERO(&setW);
            FD_SET(m_socket, &setW);
            FD_ZERO(&setE);
            FD_SET(m_socket, &setE);
            int ret = select(static_cast<int>(m_socket + 1), nullptr, &setW, &setE, &tv);
#ifdef _WIN32
            if (ret <= 0)
            {
                // select() failed or connection timed out
                closesocket(m_socket);
                if (ret == 0)
                    WSASetLastError(WSAETIMEDOUT);
                return -1;
            }
            if (FD_ISSET(m_socket, &setE))
            {
                // connection failed
                int error_code;
                int error_code_size = sizeof(error_code);
                getsockopt(m_socket, SOL_SOCKET, SO_ERROR, (char*)(&error_code), &error_code_size);
                closesocket(m_socket);
                WSASetLastError(error_code);
                return -1;
            }
#else
            {
                int so_error;
                socklen_t len = sizeof(so_error);
                getsockopt(m_socket, SOL_SOCKET, SO_ERROR, &ret, &len);
                if (ret != 0)
                {
                    close(m_socket);
                    return ret;
                }
            }
#endif
        }
        {
#ifdef _WIN32
	        unsigned long block = 0;
	        if (ioctlsocket(m_socket, FIONBIO, &block) == SOCKET_ERROR)
	        {
	            closesocket(m_socket);
	            return -1;
	        }
#else
	        {
	            int flags = fcntl(m_socket, F_GETFL, 0);
	            if (flags == -1)
	            {
		            close(m_socket);
            		return -1;
	            }
	            flags &= ~O_NONBLOCK;
	            if(::fcntl(m_socket, F_SETFL, flags) == -1)
	            {
	                close(m_socket);
	                return -1;
	            }
	        }
#endif
        }
        
        // Set TCP_NODELAY to disable Nagle's algorithm (avoid buffering delays, especially on ARM platforms)
        {
            int flag = 1;
#ifdef _WIN32
            iResult = setsockopt(m_socket, IPPROTO_TCP, TCP_NODELAY, (const char*)&flag, sizeof(int));
#else
            iResult = setsockopt(m_socket, IPPROTO_TCP, TCP_NODELAY, (const char*)&flag, sizeof(int));
#endif
            if (iResult != 0)
            {
                std::cout << "Warning: Failed to set TCP_NODELAY" << std::endl;
                // Continue anyway - TCP_NODELAY is an optimization, not critical
            }
        }
        
        // Set the timeout for the socket
#ifdef _WIN32
  // On Windows timeout is a DWORD in milliseconds (https://docs.microsoft.com/en-us/windows/desktop/api/winsock/nf-winsock-setsockopt)
        iResult = setsockopt(m_socket, SOL_SOCKET, SO_RCVTIMEO, (const char*)&timeoutMs, sizeof(DWORD));
#else
        iResult = setsockopt(m_socket, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&tv), sizeof(struct timeval));
#endif
        return iResult;
    }

    int TcpSocket::shutdown()
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

    ITransport::send_return_t TcpSocket::send(const char* pData, size_t size)
    {
        // send buffer via TCP socket  
#ifdef _WIN32
        return ::send(m_socket, pData, static_cast<int>(size), 0);
#else
        return ::send(m_socket, pData, size, 0);
#endif
    }

    ITransport::recv_return_t TcpSocket::recv(std::vector<std::uint8_t>& buffer, std::size_t maxBytesToReceive)
    {
        // receive from TCP Socket
        buffer.resize(maxBytesToReceive);
        char* pBuffer = reinterpret_cast<char*>(buffer.data());
#ifdef _WIN32
        return ::recv(m_socket, pBuffer, static_cast<int>(maxBytesToReceive), 0);
#else
        return ::recv(m_socket, pBuffer, maxBytesToReceive, 0);
#endif
    }

    ITransport::recv_return_t TcpSocket::read(std::vector<std::uint8_t>& buffer, std::size_t nBytesToReceive)
    {
        // receive from TCP Socket
        try
        {
            buffer.resize(nBytesToReceive);
        }
        catch (std::length_error&)
        {
            // Supress warning for sizes >= 125MB, because it is very likely an invalid size
            if (nBytesToReceive < 1024u * 1024u * 125u)
            {
				std::cout << "TcpSocket::" <<  __FUNCTION__ << ": Unable to allocate buffer of size " << nBytesToReceive << std::endl;
            }
            return -1;
        }

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
    int TcpSocket::getLastError()
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
