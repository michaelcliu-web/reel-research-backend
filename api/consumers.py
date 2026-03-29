import json
import os
import subprocess
import asyncio

import fitz  # PyMuPDF
import anthropic
import requests as http_requests
import environ
from google import genai

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

env = environ.Env()
env.read_env()

anthropic_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

MAX_PAPER_CHARS = 80000
MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media")


class AppConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope.get("user")

        if not self.user or self.user.is_anonymous:
            await self.close()
            return

        await self.accept()
        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "message": "Connected successfully",
        }))

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        websocket_type = data.get("websocket_type", "") or data.get("type", "")

        if websocket_type == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))

        elif websocket_type == "list_videos":
            try:
                from papers.models import Paper

                def _get_videos(user):
                    thumbs_dir = os.path.join(MEDIA_DIR, "thumbnails")
                    os.makedirs(thumbs_dir, exist_ok=True)

                    papers = Paper.objects.filter(user=user, status="completed").values(
                        "id", "title", "summary", "video_path", "created_at"
                    )
                    results = []
                    for p in papers:
                        pid = str(p["id"])
                        thumb_path = os.path.join(thumbs_dir, f"{pid}.jpg")
                        thumb_url = f"/media/thumbnails/{pid}.jpg"

                        if not os.path.exists(thumb_path) and p["video_path"]:
                            video_file = os.path.join(MEDIA_DIR, "videos",
                                os.path.basename(p["video_path"]))
                            if os.path.exists(video_file):
                                try:
                                    dur_result = subprocess.run(
                                        ["ffprobe", "-v", "error", "-show_entries",
                                         "format=duration", "-of", "csv=p=0", video_file],
                                        capture_output=True, text=True, timeout=10,
                                    )
                                    duration = float(dur_result.stdout.strip() or "20")
                                    seek_to = duration * 0.5

                                    subprocess.run(
                                        ["ffmpeg", "-y", "-ss", str(seek_to),
                                         "-i", video_file, "-frames:v", "1",
                                         "-q:v", "2", thumb_path],
                                        capture_output=True, text=True, timeout=15,
                                    )
                                except Exception:
                                    thumb_url = ""

                        if not os.path.exists(thumb_path):
                            thumb_url = ""

                        results.append({
                            "id": pid,
                            "title": p["title"],
                            "summary": p["summary"][:200] + ("..." if len(p["summary"]) > 200 else ""),
                            "video_url": p["video_path"],
                            "thumbnail_url": thumb_url,
                            "created_at": p["created_at"].isoformat(),
                        })
                    return results

                videos = await database_sync_to_async(_get_videos)(self.user)

                await self.send(text_data=json.dumps({
                    "websocket_type": "list_videos",
                    "videos": videos,
                }))
            except Exception as e:
                print(f"Error in list_videos: {e}")
                import traceback
                traceback.print_exc()
                await self.send(text_data=json.dumps({
                    "websocket_type": "list_videos",
                    "videos": [],
                    "error": str(e),
                }))

        elif websocket_type == "ask_question":
            video_id = data.get("video_id")
            question = data.get("question", "").strip()

            if not video_id or not question:
                await self.send(text_data=json.dumps({
                    "websocket_type": "ask_answer",
                    "video_id": video_id,
                    "error": "Missing video_id or question.",
                }))
                return

            try:
                from papers.models import Paper
                paper = await database_sync_to_async(Paper.objects.get)(id=video_id, user=self.user)
                pdf_path = await database_sync_to_async(lambda: paper.pdf_file.path)()
                summary = await database_sync_to_async(lambda: paper.summary)()

                def _extract(path):
                    doc = fitz.open(path)
                    text = ""
                    for page in doc:
                        text += page.get_text()
                    doc.close()
                    return text

                paper_text = await asyncio.to_thread(_extract, pdf_path)
                if len(paper_text) > MAX_PAPER_CHARS:
                    paper_text = paper_text[:MAX_PAPER_CHARS]

                qa_prompt = (
                    "You are a helpful research assistant. A user has watched a short animated "
                    "explainer video about a research paper and has a follow-up question.\n\n"
                    "Answer their question clearly and accurately based on the paper content below. "
                    "Use the same tone as 3Blue1Brown: direct, warm, curious, and simple. "
                    "If the answer isn't in the paper, say so honestly.\n\n"
                    "Keep your answer concise (2-4 paragraphs max). Use plain language.\n\n"
                    f"PAPER SUMMARY:\n{summary}\n\n"
                    f"FULL PAPER TEXT:\n{paper_text}\n\n"
                    f"USER QUESTION: {question}"
                )

                await self.send(text_data=json.dumps({
                    "websocket_type": "ask_answer",
                    "video_id": video_id,
                    "status": "streaming",
                    "chunk": "",
                }))

                async for chunk in await gemini_client.aio.models.generate_content_stream(
                    model="gemini-3.1-flash-lite-preview",
                    contents=qa_prompt,
                ):
                    if chunk.text:
                        await self.send(text_data=json.dumps({
                            "websocket_type": "ask_answer",
                            "video_id": video_id,
                            "status": "streaming",
                            "chunk": chunk.text,
                        }))

                await self.send(text_data=json.dumps({
                    "websocket_type": "ask_answer",
                    "video_id": video_id,
                    "status": "done",
                }))

            except Exception as e:
                print(f"Error in ask_question: {e}")
                import traceback
                traceback.print_exc()
                await self.send(text_data=json.dumps({
                    "websocket_type": "ask_answer",
                    "video_id": video_id,
                    "error": str(e),
                }))

        elif websocket_type == "generate_video":
            paper_id = data["paper_id"]

            try:
                # ── 1. Parse PDF ──
                from papers.models import Paper
                paper = await database_sync_to_async(Paper.objects.get)(id=paper_id)
                pdf_path = await database_sync_to_async(lambda: paper.pdf_file.path)()
                pdf_url = await database_sync_to_async(lambda: paper.pdf_file.url)()

                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "parsing_pdf",
                    "pdf_url": pdf_url,
                }))

                def _extract_text(path):
                    doc = fitz.open(path)
                    text = ""
                    for page in doc:
                        text += page.get_text()
                    doc.close()
                    if len(text.strip()) < 100:
                        raise ValueError("Could not extract meaningful text from the PDF.")
                    return text

                paper_text = await asyncio.to_thread(_extract_text, pdf_path)
                if len(paper_text) > MAX_PAPER_CHARS:
                    paper_text = paper_text[:MAX_PAPER_CHARS]

                # ── 2. Summarize with Gemini (streamed) ──
                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "summarizing",
                }))

                summary_prompt = (
                    "You are explaining a research paper to a smart friend over coffee. "
                    "Your tone is like Grant Sanderson (3Blue1Brown): direct, curious, warm, "
                    "and genuinely interested in the ideas. You never sound like a press release "
                    "or a textbook.\n\n"
                    "STRICT TONE RULES:\n"
                    "- Use plain, everyday words. Say 'shows' not 'unveils', 'important' not 'groundbreaking'.\n"
                    "- NO flowery metaphors or dramatic language. Never say things like "
                    "'a one-way street of chaotic behavior', 'elegant tapestry', 'unlock the secrets', "
                    "'revolutionize the field', or 'paradigm shift'.\n"
                    "- NO hype words: groundbreaking, remarkable, fascinating, game-changing, cutting-edge.\n"
                    "- Talk like a real person. Short sentences. Ask genuine questions. "
                    "'Here's the cool part' is fine. 'This heralds a new era' is not.\n"
                    "- It's OK to say 'we don't fully know why yet' or 'this part is tricky'.\n\n"
                    "Read this research paper and create two things:\n\n"
                    "1. SUMMARY: Cover the FULL paper in this structure (400-600 words):\n"
                    "   - What problem are they trying to solve, and why should anyone care? (2-3 sentences)\n"
                    "   - What's the key idea or approach? Explain it simply. (1 paragraph)\n"
                    "   - What did they actually find? Cover the main results and what the data shows. (1-2 paragraphs)\n"
                    "   - What does this mean? Cover the conclusions and implications — "
                    "what changes because of this work? What are the limitations? (1 paragraph)\n\n"
                    "2. NARRATION: A SHORT 20-30 second spoken narration (75-100 words MAX). "
                    "This is critical — keep it tight and punchy. Structure it as:\n"
                    "   - Hook (first 3 seconds): One question or surprising fact.\n"
                    "   - The core idea: What did they do and find? (3-4 sentences total)\n"
                    "   - The takeaway: Why does it matter? (1 sentence)\n"
                    "   - Do NOT include stage directions or visual cues, just the spoken words.\n"
                    "   - STRICT: Stay under 100 words. Read it aloud — it should be under 30 seconds.\n\n"
                    "Format your response exactly as:\n"
                    "SUMMARY:\n[your summary here]\n\n"
                    "NARRATION:\n[your narration script here]\n\n"
                    f"Research paper:\n{paper_text}"
                )

                full_summary_text = ""
                async for chunk in await gemini_client.aio.models.generate_content_stream(
                    model="gemini-3.1-flash-lite-preview",
                    contents=summary_prompt,
                ):
                    if chunk.text:
                        full_summary_text += chunk.text
                        await self.send(text_data=json.dumps({
                            "websocket_type": "generate_video",
                            "status": "summarizing",
                            "chunk": chunk.text,
                        }))

                if "NARRATION:" in full_summary_text:
                    parts = full_summary_text.split("NARRATION:")
                    summary = parts[0].replace("SUMMARY:", "").strip()
                    narration_script = parts[1].strip()
                else:
                    summary = full_summary_text
                    narration_script = full_summary_text

                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "summarizing_done",
                }))

                await database_sync_to_async(lambda: Paper.objects.filter(id=paper_id).update(
                    summary=summary, narration_script=narration_script, status="summarized"
                ))()

                # ── 3. Generate Manim code with Claude Opus (streamed) ──
                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "generating_animation",
                }))

                manim_prompt = (
                    "Generate a complete Manim Community Edition Python script that creates "
                    "an animated explainer video for the following content.\n\n"
                    "IMPORTANT: This video is for SHORT-FORM VERTICAL content (Instagram Reels, "
                    "YouTube Shorts, Snapchat). The canvas is 9:16 PORTRAIT (1080x1920).\n\n"
                    "CRITICAL — THIS VIDEO HAS A SEPARATE VOICEOVER NARRATION:\n"
                    "The video will have spoken narration added on top. That means:\n"
                    "- Use MINIMAL text on screen. Only short labels, titles, numbers, or key terms.\n"
                    "- NEVER put full sentences or paragraphs on screen — the narrator says those.\n"
                    "- Think of it like a 3Blue1Brown video: the visuals SHOW, the voice EXPLAINS.\n"
                    "- A title card with 3-5 words is fine. A sentence on screen is not.\n\n"
                    "VISUAL STYLE:\n"
                    "- Prioritize diagrams, shapes, arrows, graphs, transformations, and motion.\n"
                    "- Use geometric objects to represent concepts: circles for entities, arrows for "
                    "relationships, graphs for data, grids for structures, etc.\n"
                    "- Animate things moving, morphing, growing, connecting — keep it dynamic.\n"
                    "- Use color changes and highlights to draw attention.\n"
                    "- Cover the full story: problem, approach, results, and takeaway.\n"
                    "- Build toward a satisfying visual payoff.\n\n"
                    "TECHNICAL REQUIREMENTS:\n"
                    "- Start the script with exactly these lines:\n"
                    "  from manim import *\n"
                    "  import random\n"
                    "  import math\n"
                    "  import numpy as np\n"
                    "  config.pixel_width = 1080\n"
                    "  config.pixel_height = 1920\n"
                    "  config.frame_width = 9.0\n"
                    "  config.frame_height = 16.0\n"
                    "- Single Scene class called `PaperExplainer`\n"
                    "- Do NOT set camera frame dimensions in construct() — the config above handles it\n"
                    "- Design all layouts for VERTICAL viewing — stack elements top-to-bottom, "
                    "not left-to-right. Keep content centered and away from edges.\n"
                    "- The coordinate system is 9 units wide by 16 units tall. "
                    "Center is (0,0), top is (0,8), bottom is (0,-8), left is (-4.5,0), right is (4.5,0).\n"
                    "- Use only standard Manim objects: Text, MathTex, Tex, VGroup, Arrow, Circle, "
                    "Square, Rectangle, Line, Dot, NumberPlane, Axes, etc.\n"
                    "- Use self.play() for animations, self.wait() for pauses\n"
                    "- Text on screen should be SHORT (2-5 words max per label). font_size <= 32 for labels, <= 40 for titles.\n"
                    "- Use colors: BLUE, GREEN, YELLOW, RED, WHITE, ORANGE, PURPLE, TEAL\n"
                    "- Total animation should be 20-35 seconds. Use self.wait(0.5) between scenes, not self.wait(1) or longer.\n"
                    "- Use FadeIn, Write, Transform, Create, GrowFromCenter, MoveToTarget, "
                    "AnimationGroup, Indicate, Flash, etc.\n"
                    "- Clean transitions between sections (FadeOut old content before new)\n"
                    "- Do NOT use external files, images, SVGs, or sound\n"
                    "- Do NOT use deprecated methods\n"
                    "- NEVER put non-VMobject items (like Mobject, Group, or 3D objects) into a VGroup. "
                    "VGroup only accepts VMobject subclasses (Text, MathTex, Circle, Square, Line, Arrow, "
                    "Dot, Rectangle, Polygon, etc.). If you need to group mixed types, use Group instead.\n\n"
                    "Return ONLY valid Python code. No markdown fences, no explanation. "
                    "Start directly with `from manim import *`.\n\n"
                    f"Content to animate:\n{summary}"
                )

                manim_code = ""
                async with anthropic_client.messages.stream(
                    model="claude-opus-4-20250514",
                    max_tokens=8192,
                    messages=[{"role": "user", "content": manim_prompt}],
                ) as stream:
                    async for text in stream.text_stream:
                        manim_code += text
                        await self.send(text_data=json.dumps({
                            "websocket_type": "generate_video",
                            "status": "generating_animation",
                            "chunk": text,
                        }))

                if manim_code.startswith("```"):
                    lines = manim_code.split("\n")
                    manim_code = "\n".join(lines[1:])
                if manim_code.endswith("```"):
                    manim_code = manim_code[:-3].strip()

                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "generating_animation_done",
                }))

                await database_sync_to_async(lambda: Paper.objects.filter(id=paper_id).update(
                    manim_code=manim_code, status="code_generated"
                ))()

                # ── 4. Render Manim video ──
                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "rendering",
                }))

                def _render_video(code, pid):
                    scripts_dir = os.path.join(MEDIA_DIR, "scripts")
                    videos_dir = os.path.join(MEDIA_DIR, "videos")
                    os.makedirs(scripts_dir, exist_ok=True)
                    os.makedirs(videos_dir, exist_ok=True)

                    script_path = os.path.join(scripts_dir, f"{pid}.py")
                    with open(script_path, "w") as f:
                        f.write(code)

                    final_path = os.path.join(videos_dir, f"{pid}.mp4")

                    result = subprocess.run(
                        [
                            "manim", "render",
                            "--fps", "30",
                            "-o", final_path,
                            script_path, "PaperExplainer",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )

                    if result.returncode != 0:
                        raise Exception(f"Manim rendering failed: {result.stderr[-1000:]}")

                    if not os.path.exists(final_path):
                        raise Exception("Rendered video file not found after Manim render.")

                    return f"/media/videos/{pid}.mp4"

                video_url = await asyncio.to_thread(_render_video, manim_code, paper_id)

                # ── 5. Generate narration audio with ElevenLabs TTS ──
                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "generating_narration",
                }))

                def _generate_narration_and_merge(script, pid):
                    audio_dir = os.path.join(MEDIA_DIR, "audio")
                    os.makedirs(audio_dir, exist_ok=True)
                    audio_path = os.path.join(audio_dir, f"{pid}.mp3")

                    tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
                    tts_resp = http_requests.post(
                        tts_url,
                        headers={
                            "xi-api-key": ELEVENLABS_API_KEY,
                            "Content-Type": "application/json",
                            "Accept": "audio/mpeg",
                        },
                        json={
                            "text": script[:5000],
                            "model_id": "eleven_multilingual_v2",
                            "voice_settings": {
                                "stability": 0.5,
                                "similarity_boost": 0.75,
                            },
                        },
                        timeout=120,
                    )

                    if tts_resp.status_code != 200:
                        raise Exception(f"ElevenLabs TTS failed ({tts_resp.status_code}): {tts_resp.text[:500]}")

                    with open(audio_path, "wb") as f:
                        f.write(tts_resp.content)

                    silent_video_path = os.path.join(MEDIA_DIR, "videos", f"{pid}.mp4")
                    final_path = os.path.join(MEDIA_DIR, "videos", f"{pid}_final.mp4")

                    audio_dur = float(subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries",
                         "format=duration", "-of", "csv=p=0", audio_path],
                        capture_output=True, text=True, timeout=10,
                    ).stdout.strip() or "30")

                    video_dur = float(subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries",
                         "format=duration", "-of", "csv=p=0", silent_video_path],
                        capture_output=True, text=True, timeout=10,
                    ).stdout.strip() or "30")

                    final_duration = str(max(audio_dur, video_dur))

                    merge_result = subprocess.run(
                        [
                            "ffmpeg", "-y",
                            "-stream_loop", "-1",
                            "-i", silent_video_path,
                            "-i", audio_path,
                            "-t", final_duration,
                            "-c:v", "libx264",
                            "-c:a", "aac",
                            "-map", "0:v:0",
                            "-map", "1:a:0",
                            final_path,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )

                    if merge_result.returncode != 0:
                        raise Exception(f"FFmpeg merge failed: {merge_result.stderr[-500:]}")

                    return f"/media/videos/{pid}_final.mp4"

                final_video_url = await asyncio.to_thread(
                    _generate_narration_and_merge, narration_script, paper_id
                )

                await database_sync_to_async(lambda: Paper.objects.filter(id=paper_id).update(
                    video_path=final_video_url, status="completed"
                ))()

                # ── 6. Done ──
                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "DONE",
                    "video_url": final_video_url,
                    "summary": summary,
                }))

            except Exception as e:
                print(f"Error in generate_video: {e}")
                import traceback
                traceback.print_exc()
                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "error",
                    "message": str(e),
                }))
