import json

from channels.generic.websocket import AsyncWebsocketConsumer

from papers.handlers import ask_question, generate_video, list_videos

# Incoming websocket_type → handler(send, user, data)
HANDLERS = {
    "list_videos": list_videos.handle,
    "ask_question": ask_question.handle,
    "generate_video": generate_video.handle,
}


class AppConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope.get("user")

        if not self.user or self.user.is_anonymous:
            await self.close()
            return

        await self.accept()
        await self.send_json({
            "type": "connection_established",
            "message": "Connected successfully",
        })

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        websocket_type = data.get("websocket_type", "") or data.get("type", "")

        if websocket_type == "ping":
            await self.send_json({"type": "pong"})
            return

        handler = HANDLERS.get(websocket_type)
        if handler:
            await handler(self.send_json, self.user, data)

    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload))
