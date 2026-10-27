import traceback

from channels.db import database_sync_to_async

from papers.models import Paper
from papers.pipeline.video import generate_video


async def handle(send, user, data):
    paper_id = data.get("paper_id")
    if not paper_id:
        await send({
            "websocket_type": "generate_video",
            "status": "error",
            "message": "Missing paper_id.",
        })
        return

    async def emit(status, **fields):
        await send({"websocket_type": "generate_video", "status": status, **fields})

    try:
        paper = await database_sync_to_async(Paper.objects.get)(id=paper_id, user=user)
        await generate_video(paper, data.get("skill_level", "college"), emit)
    except Exception as e:
        print(f"Error in generate_video: {e}")
        traceback.print_exc()
        await emit("error", message=str(e))
