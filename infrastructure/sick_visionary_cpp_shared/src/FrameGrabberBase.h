//
// Copyright note: Redistribution and use in source, with or without modification, are permitted.
// 
// Created: February 2023
// 
// SICK AG, Waldkirch
// email: TechSupport0905@sick.de

#pragma once

#include "VisionaryDataStream.h"
#include <thread>
#include <mutex>
#include <condition_variable>

namespace visionary
{
	class FrameGrabberBase
	{
	public:
		FrameGrabberBase(const std::string& hostname, std::uint16_t port, std::uint64_t timeoutMs);
		~FrameGrabberBase();

		void start(std::shared_ptr<VisionaryData> inactiveDataHandler, std::shared_ptr<VisionaryData> activeDataHandler);
		bool getNextFrame(std::shared_ptr<VisionaryData>& pDataHandler, std::uint64_t timeoutMs = 1000);
		bool getCurrentFrame(std::shared_ptr<VisionaryData>& pDataHandler);
	private:
		void run();
		bool m_isRunning;
		bool m_FrameAvailable;
		bool m_connected;
		const std::string m_hostname;
		const std::uint16_t m_port;
		const std::uint64_t m_timeoutMs;
		std::unique_ptr<VisionaryDataStream> m_pDataStream;
		std::thread m_grabberThread;
		std::shared_ptr<VisionaryData> m_pDataHandler;
		std::mutex m_dataHandler_mutex;
		std::condition_variable m_frameAvailableCv;
	};
}