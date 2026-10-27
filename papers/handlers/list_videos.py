import traceback

from channels.db import database_sync_to_async

from papers.models import Paper
from papers.pipeline.render import ensure_thumbnail


def _get_videos(user):
    papers = Paper.objects.filter(user=user, status="completed").values(
        "id", "title", "summary", "video_path", "created_at", "key_takeaways", "quiz", "suggested_papers"
    )
    results = []
    for p in papers:
        pid = str(p["id"])
        summary = p["summary"] or ""
        results.append({
            "id": pid,
            "title": p["title"],
            "summary": summary[:200] + ("..." if len(summary) > 200 else ""),
            "video_url": p["video_path"],
            "thumbnail_url": ensure_thumbnail(pid, p["video_path"]),
            "created_at": p["created_at"].isoformat(),
            "key_takeaways": p["key_takeaways"] or [],
            "quiz": p["quiz"] or [],
            "suggested_papers": p["suggested_papers"] or [],
        })
    return results


async def handle(send, user, data):
    try:
        videos = await database_sync_to_async(_get_videos)(user)
        await send({"websocket_type": "list_videos", "videos": videos})
    except Exception as e:
        print(f"Error in list_videos: {e}")
        traceback.print_exc()
        await send({"websocket_type": "list_videos", "videos": [], "error": str(e)})
