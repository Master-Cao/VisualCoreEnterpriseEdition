# -*- coding: utf-8 -*-

from domain.enums.commands import VisionCoreCommands, MessageType
from domain.models.mqtt import MQTTResponse
from .context import CommandContext


def handle_get_system_status(_req: MQTTResponse, ctx: CommandContext) -> MQTTResponse:
    mon = ctx.monitor
    status = mon.get_system_status() if mon else {"monitoring": False}
    return MQTTResponse(
        command=VisionCoreCommands.GET_SYSTEM_STATUS.value,
        component="system",
        messageType=MessageType.SUCCESS,
        message="ok",
        data={"status": status},
    )


def handle_restart(_req: MQTTResponse, _ctx: CommandContext) -> MQTTResponse:
    return MQTTResponse(
        command=VisionCoreCommands.RESTART.value,
        component="system",
        messageType=MessageType.SUCCESS,
        message="ack",
        data={},
    )


