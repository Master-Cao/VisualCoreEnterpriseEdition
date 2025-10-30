# -*- coding: utf-8 -*-

from domain.enums.commands import MessageType
from domain.models.mqtt import MQTTResponse
from .context import CommandContext


def handle_catch(_req: MQTTResponse, _ctx: CommandContext) -> MQTTResponse:
    # 协议要求返回字符串 "count,x,y,z,angle"
    return MQTTResponse(
        command="catch",
        component="tcp",
        messageType=MessageType.SUCCESS,
        message="ok",
        data={"response": "0,0,0,0,0"},
    )


