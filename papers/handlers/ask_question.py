import asyncio
import traceback

from channels.db import database_sync_to_async

from papers.models import Paper
from papers.pipeline import llm, pdf
from papers.prompts.qa import qa_prompt


async def handle(send, user, data):
    video_id = data.get("video_id")
    question = data.get("question", "").strip()

    async def reply(**fields):
        await send({"websocket_type": "ask_answer", "video_id": video_id, **fields})

    if not video_id or not question:
        await reply(error="Missing video_id or question.")
        return

    try:
        paper = await database_sync_to_async(Paper.objects.get)(id=video_id, user=user)
        paper_text = await asyncio.to_thread(pdf.extract_text, paper.pdf_file.path)

        await reply(status="streaming", chunk="")
        async for text in llm.stream_text(qa_prompt(paper.summary, paper_text, question), llm.FAST_MODEL, 1024):
            await reply(status="streaming", chunk=text)
        await reply(status="done")

    except Exception as e:
        print(f"Error in ask_question: {e}")
        traceback.print_exc()
        await reply(error=str(e))
