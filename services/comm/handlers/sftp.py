# -*- coding: utf-8 -*-

from domain.enums.commands import VisionCoreCommands, MessageType
from domain.models.mqtt import MQTTResponse
from .context import CommandContext


def handle_sftp_test(_req: MQTTResponse, ctx: CommandContext) -> MQTTResponse:
    try:
        sftp = ctx.sftp
        ok = sftp.test() if sftp else False
        return MQTTResponse(
            command=VisionCoreCommands.SFTP_TEST.value,
            component="sftp",
            messageType=MessageType.SUCCESS if ok else MessageType.ERROR,
            message="ok" if ok else "sftp_not_ready",
            data={"ready": ok},
        )
    except Exception as e:
        return MQTTResponse(
            command=VisionCoreCommands.SFTP_TEST.value,
            component="sftp",
            messageType=MessageType.ERROR,
            message=str(e),
            data={},
        )


