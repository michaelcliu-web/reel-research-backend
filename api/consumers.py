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
                    "You are an expert science communicator like Grant Sanderson (3Blue1Brown). "
                    "Read this research paper and create two things:\n\n"
                    "1. SUMMARY: A clear, engaging summary that explains the paper's key concepts, "
                    "methodology, and findings in a way that a college student could understand. "
                    "Use analogies and simple language. About 400-600 words.\n\n"
                    "2. NARRATION: A narration script for a 2-3 minute animated explainer video. "
                    "Write it as if you're narrating a 3Blue1Brown video — conversational, "
                    "curious, building intuition step by step. Do NOT include stage directions "
                    "or visual cues, just the spoken words.\n\n"
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
                    "an animated explainer video for the following content. The animation should be "
                    "visually engaging and educational, like a 3Blue1Brown video.\n\n"
                    "REQUIREMENTS:\n"
                    "- Import: `from manim import *`\n"
                    "- Single Scene class called `PaperExplainer`\n"
                    "- Use only standard Manim objects: Text, MathTex, Tex, VGroup, Arrow, Circle, "
                    "Square, Rectangle, Line, Dot, NumberPlane, Axes, etc.\n"
                    "- Use self.play() for animations, self.wait() for pauses\n"
                    "- Keep text readable: font_size <= 36 for body, <= 48 for titles\n"
                    "- Use colors: BLUE, GREEN, YELLOW, RED, WHITE, ORANGE, PURPLE, TEAL\n"
                    "- Total animation should be 60-90 seconds\n"
                    "- Include a title card, then break down key concepts visually\n"
                    "- Use FadeIn, Write, Transform, Create, GrowFromCenter, etc.\n"
                    "- Clean transitions between sections (FadeOut old content before new)\n"
                    "- Do NOT use external files, images, SVGs, or sound\n"
                    "- Do NOT use deprecated methods\n"
                    "- Must render with: manim render -ql script.py PaperExplainer\n\n"
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
                            "manim", "render", "-ql",
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

                await database_sync_to_async(lambda: Paper.objects.filter(id=paper_id).update(
                    video_path=video_url, status="completed"
                ))()

                # ── 6. Done ──
                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "DONE",
                    "video_url": video_url,
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
