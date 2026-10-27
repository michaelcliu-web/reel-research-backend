import json
import os
import re as _re
import subprocess
import asyncio

import fitz  # PyMuPDF
import anthropic
import requests as http_requests
import environ

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

env = environ.Env()
env.read_env()

anthropic_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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
                        "id", "title", "summary", "video_path", "created_at", "key_takeaways", "quiz", "suggested_papers"
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
                            "summary": (p["summary"] or "")[:200] + ("..." if len(p["summary"] or "") > 200 else ""),
                            "video_url": p["video_path"],
                            "thumbnail_url": thumb_url,
                            "created_at": p["created_at"].isoformat(),
                            "key_takeaways": p["key_takeaways"] or [],
                            "quiz": p["quiz"] or [],
                            "suggested_papers": p["suggested_papers"] or [],
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

                async with anthropic_client.messages.stream(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": qa_prompt}],
                ) as stream:
                    async for text in stream.text_stream:
                        await self.send(text_data=json.dumps({
                            "websocket_type": "ask_answer",
                            "video_id": video_id,
                            "status": "streaming",
                            "chunk": text,
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
            paper_id = data.get("paper_id")
            if not paper_id:
                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "error",
                    "message": "Missing paper_id.",
                }))
                return
            skill_level = data.get("skill_level", "college")

            _audience = {
                "5th_grade": (
                    "a curious 5th grader (age 10-11) with no scientific background. "
                    "Use simple everyday words, short sentences, and fun analogies. "
                    "Avoid all jargon. If a technical term is unavoidable, immediately explain it "
                    "with a concrete real-world comparison a child would recognise."
                ),
                "10th_grade": (
                    "a 10th grade high school student (age 15-16) who has taken basic science and maths. "
                    "You can use common scientific terms but explain anything advanced. "
                    "Relate ideas to things they have seen in school (algebra, basic physics, biology). "
                    "Keep it engaging without over-simplifying."
                ),
                "college": (
                    "a college-educated adult or undergraduate with general scientific literacy. "
                    "You can use technical terminology, discuss methodology, and include quantitative details. "
                    "Assume comfort with maths and scientific reasoning. Prioritise depth and precision."
                ),
            }.get(skill_level, "a college-educated adult with general scientific literacy.")

            try:
                # ── 1. Parse PDF ──
                from papers.models import Paper
                paper = await database_sync_to_async(Paper.objects.get)(id=paper_id, user=self.user)
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

                # ── 2. Summarize (streamed) ──
                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "summarizing",
                }))

                summary_prompt = (
                    "Pretend you are a talented individual creating visual explanations for research papers "
                    "to the general public. You are someone like Grant Sanderson (3Blue1Brown), someone who "
                    "seeks to develop a strong intuition in the viewer for the subject. You are enthusiastic, "
                    "passionate, and interested in the ideas of the paper.\n\n"
                    f"YOUR AUDIENCE: You are explaining this to {_audience} "
                    "Tailor every word of your explanation — vocabulary, depth, analogies, and examples — to this audience.\n\n"
                    "Read the research paper below and create two things:\n\n"
                    "1. SUMMARY: Follow this three-step structure:\n\n"
                    "Step 1 — Exigence (heavily use the abstract):\n"
                    "   - Does the paper need contextualizing? Contextualize as needed.\n"
                    "   - Summarize the problem. Talk about why it is relevant in the field where the problem resides.\n"
                    "   - Set up the mechanisms needed to solve the problem as the paper discusses it.\n\n"
                    "Step 2 — Solution:\n"
                    "   - Find the key revelation(s) to the problem. What is novel about this paper specifically? "
                    "These are the AHA! moments.\n"
                    "   - Talk about what is groundbreaking about this novel discovery and how it improves on "
                    "previous progress on the subject.\n"
                    "   - Go through the technical details — raw formulas, mathematics, the science, and why it "
                    "works. The goal is to create an intuitive understanding for the reader.\n"
                    "   - Use good visuals and explanations. The visual is the most important part. Be concise, "
                    "but don't be afraid to be wordy or descriptive. The goal is to elucidate the paper as "
                    "clearly as possible to the viewer.\n\n"
                    "Step 3 — Conclusion:\n"
                    "   - What are the impacts of this novel discovery?\n"
                    "   - Don't be afraid to say what is still unknown and what is known.\n"
                    "   - What problems are still not fully resolved by the paper?\n"
                    "   - What are future steps for this paper?\n\n"
                    "2. NARRATION: A spoken narration of 200-280 words (80-110 seconds when read aloud). "
                    "Structure it as:\n"
                    "   - Hook (first 5-10 seconds): One question or surprising fact.\n"
                    "   - Exigence: Briefly set up the problem and why it matters.\n"
                    "   - The AHA moment(s): Walk through the key discovery and how it works.\n"
                    "   - Conclusion: Impacts, open questions, and future directions.\n"
                    "   - Do NOT include stage directions or visual cues, just the spoken words.\n"
                    "   - STRICT: 200-280 words. Read it aloud — it must be 80-110 seconds.\n\n"
                    "Format your response exactly as:\n"
                    "SUMMARY:\n[your summary here]\n\n"
                    "NARRATION:\n[your narration script here]\n\n"
                    f"Research paper:\n{paper_text}"
                )

                full_summary_text = ""
                async with anthropic_client.messages.stream(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=4096,
                    messages=[{"role": "user", "content": summary_prompt}],
                ) as stream:
                    async for text in stream.text_stream:
                        full_summary_text += text
                        await self.send(text_data=json.dumps({
                            "websocket_type": "generate_video",
                            "status": "summarizing",
                            "chunk": text,
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

                # ── 3. Generate storyboard ──
                # Ask Claude to break the summary into 4-6 scenes, each with its own
                # narration text, visual concept, and estimated duration. This is the
                # key change: instead of one big Manim script + one audio file merged
                # after the fact, we plan the timing upfront so visuals sync to speech.
                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "generating_storyboard",
                }))

                storyboard_prompt = (
                    "You are planning a short animated explainer video for a research paper. "
                    f"YOUR AUDIENCE: {_audience} Match the narration language and visual complexity to this audience.\n\n"
                    "Break the following summary into scenes mirroring the structure of the summary for a 60-120 second vertical video. This should be 1-3 scenes for step 1, 6-8 scenes for step 2, 1-3 scenes for step 3.\n\n"
                    "For each scene provide:\n"
                    "- narration: Elucidated spoken text for that scene\n"
                    "- visuals: A concise description of what to animate, be as descriptive as possible for the best intuitive understanding for the viewer.\n"
                    "- specifics: Make sure to be descriptive when explaining the core of the paper. Try and include raw formulas, mathematics, the science, the change in thinking, and why it works in the animations.\n"
                    "- NEVER repeat long formulas, constants, or in speech. ONLY have it on the screen as necessary.\n"
                    "- duration: Make sure to be descriptive and create an intuitive understanding when possible, but be sure to keep it to around 60-120 seconds.\n\n"
                    f"Reminder: MAKE SURE to follow the instructions in {_audience}.\n"
                    "Return ONLY a valid JSON array. No markdown, no explanation. Example:\n"
                    '[{"scene": 1, "narration": "...", "visuals": "...", "specifics": "...", "duration": 5}]\n\n'
                    f"Summary:\n{summary}"
                )

                def _sanitize_json_strings(text):
                    """Escape literal newlines/tabs inside JSON string values."""
                    result = []
                    in_string = False
                    escape_next = False
                    for ch in text:
                        if escape_next:
                            result.append(ch)
                            escape_next = False
                        elif ch == '\\' and in_string:
                            result.append(ch)
                            escape_next = True
                        elif ch == '"':
                            in_string = not in_string
                            result.append(ch)
                        elif in_string and ch == '\n':
                            result.append('\\n')
                        elif in_string and ch == '\t':
                            result.append('\\t')
                        elif in_string and ch == '\r':
                            pass
                        else:
                            result.append(ch)
                    return ''.join(result)

                def _try_parse_storyboard(text):
                    """Extract and parse JSON array from LLM output, with sanitization fallback."""
                    if not text.strip():
                        return None
                    json_match = _re.search(r'\[.*\]', text, _re.DOTALL)
                    raw = json_match.group() if json_match else text
                    raw = raw.replace('\u201c', '"').replace('\u201d', '"')
                    raw = raw.replace('\u2018', "'").replace('\u2019', "'")
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError:
                        return json.loads(_sanitize_json_strings(raw))

                storyboard = None
                storyboard_text = ""
                async with anthropic_client.messages.stream(
                    model="claude-opus-5-5",
                    max_tokens=64000,
                    messages=[{"role": "user", "content": storyboard_prompt}],
                ) as stream:
                    async for text in stream.text_stream:
                        storyboard_text += text
                try:
                    storyboard = _try_parse_storyboard(storyboard_text)
                except (json.JSONDecodeError, Exception) as e:
                    print(f"Storyboard parse failed: {e}\nRaw output: {storyboard_text[:300]}")

                if not storyboard:
                    raise Exception(f"Failed to generate a valid storyboard after retries. Last output: {storyboard_text[:300]}")

                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "storyboard_done",
                    "scene_count": len(storyboard),
                }))

                # ── 4. Process all scenes in parallel: TTS → Manim code → render → merge ──
                # Each scene's pipeline is independent, so all scenes run concurrently.
                # Within a scene, TTS still runs first to get the exact duration before
                # Manim codegen, preserving the audio-sync guarantee.

                def _scene_tts(narration_text, pid, snum, hint):
                    audio_dir = os.path.join(MEDIA_DIR, "audio")
                    os.makedirs(audio_dir, exist_ok=True)
                    audio_path = os.path.join(audio_dir, f"{pid}_scene{snum}.mp3")
                    tts_resp = http_requests.post(
                        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
                        headers={
                            "xi-api-key": ELEVENLABS_API_KEY,
                            "Content-Type": "application/json",
                            "Accept": "audio/mpeg",
                        },
                        json={
                            "text": narration_text,
                            "model_id": "eleven_multilingual_v2",
                            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                        },
                        timeout=60,
                    )
                    if tts_resp.status_code != 200:
                        raise Exception(f"ElevenLabs TTS failed ({tts_resp.status_code}): {tts_resp.text[:300]}")
                    with open(audio_path, "wb") as f:
                        f.write(tts_resp.content)
                    dur_result = subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries",
                         "format=duration", "-of", "csv=p=0", audio_path],
                        capture_output=True, text=True, timeout=10,
                    )
                    duration = float(dur_result.stdout.strip() or str(hint))
                    return audio_path, duration

                def _render_scene(code, pid, snum):
                    scripts_dir = os.path.join(MEDIA_DIR, "scripts")
                    videos_dir = os.path.join(MEDIA_DIR, "videos")
                    os.makedirs(scripts_dir, exist_ok=True)
                    os.makedirs(videos_dir, exist_ok=True)
                    script_path = os.path.join(scripts_dir, f"{pid}_scene{snum}.py")
                    with open(script_path, "w") as f:
                        f.write(code)
                    scene_video_path = os.path.join(videos_dir, f"{pid}_scene{snum}.mp4")
                    result = subprocess.run(
                        ["manim", "render", "--fps", "30", "-o", scene_video_path,
                         script_path, "PaperScene"],
                        capture_output=True, text=True, timeout=120,
                    )
                    if result.returncode != 0:
                        raise Exception(f"Scene {snum} render failed: {result.stderr[-500:]}")
                    if not os.path.exists(scene_video_path):
                        raise Exception(f"Scene {snum} video not found after render.")
                    return scene_video_path

                def _merge_scene(video_path, aud_path, pid, snum, duration):
                    videos_dir = os.path.join(MEDIA_DIR, "videos")
                    merged_path = os.path.join(videos_dir, f"{pid}_scene{snum}_merged.mp4")
                    result = subprocess.run(
                        [
                            "ffmpeg", "-y",
                            "-stream_loop", "-1", "-i", video_path,
                            "-i", aud_path,
                            "-t", str(duration),
                            "-c:v", "libx264", "-c:a", "aac",
                            "-map", "0:v:0", "-map", "1:a:0",
                            merged_path,
                        ],
                        capture_output=True, text=True, timeout=60,
                    )
                    if result.returncode != 0:
                        raise Exception(f"Scene {snum} merge failed: {result.stderr[-300:]}")
                    return merged_path

                # ElevenLabs plans cap concurrent requests (typically 2).
                tts_semaphore = asyncio.Semaphore(2)

                async def _process_one_scene(scene, scene_num, total_scenes, pid):
                    scene_narration = scene["narration"]
                    scene_visuals = scene["visuals"]
                    hint_dur = float(scene.get("duration", 5))

                    await self.send(text_data=json.dumps({
                        "websocket_type": "generate_video",
                        "status": "processing_scene",
                        "scene": scene_num,
                        "total_scenes": total_scenes,
                    }))

                    # TTS first — need the exact duration before generating Manim code.
                    # Semaphore ensures at most 3 TTS calls run concurrently.
                    async with tts_semaphore:
                        audio_path, exact_duration = await asyncio.to_thread(
                            _scene_tts, scene_narration, pid, scene_num, hint_dur
                        )

                    scene_manim_prompt = (
                        "Generate a Manim Community Edition Python script for ONE scene of an animated explainer video.\n\n"
                        "Start with exactly:\n"
                        "  from manim import *\n"
                        "  import numpy as np\n"
                        "  config.pixel_width = 1080\n"
                        "  config.pixel_height = 1920\n"
                        "  config.frame_width = 9.0\n"
                        "  config.frame_height = 16.0\n\n"
                        f"SCENE DURATION: {exact_duration:.1f} seconds total. "
                        f"All animations + self.wait() calls must sum to exactly {exact_duration:.1f} seconds.\n\n"
                        f"VISUAL CONCEPT: {scene_visuals}\n"
                        f"NARRATION (context only, do NOT display on screen): {scene_narration}\n\n"
                        "RULES:\n"
                        "- Single Scene class called `PaperScene`\n"
                        "- Minimal text (2-5 words max per label, font_size <= 36)\n"
                        "- Portrait layout: stack top-to-bottom, keep content centered\n"
                        "- Use diagrams, shapes, arrows, motion to show the concept visually\n"
                        "- VGroup only accepts VMobjects; use Group for mixed types. NEVER pass a Group into a VGroup — Group is not a VMobject and will raise TypeError.\n"
                        "- No external files, images, or sound\n"
                        "MANIM API (critical — avoid these common mistakes):\n"
                        "- NEVER call .fade_out(), .fade_in(), .show(), or .hide() as methods on objects — these do not exist.\n"
                        "- ALWAYS use self.play(FadeOut(obj)), self.play(FadeIn(obj)), self.play(Create(obj)), etc.\n"
                        "- NEVER use ShowCreation() — use Create() instead.\n"
                        "- NEVER use TextMobject() or TexMobject() — use Text() or MathTex() instead.\n"
                        "- NEVER use Tex() — it requires a full LaTeX installation and frequently fails. Use MathTex() for equations or Text() for plain text.\n"
                        "- NEVER use SVGMobject, ImageMobject, or any mobject that loads from a file — no external assets are available.\n"
                        "- NEVER call .normalize() on a numpy array — numpy arrays have no such method. Use Manim's standalone normalize() function instead: normalize(vec_a - vec_b).\n"
                        "- NEVER use .set_width(x, stretch=True) or .set_height(x, stretch=True) — the stretch kwarg was removed. Use .stretch_to_fit_width(x) or .stretch_to_fit_height(x) instead.\n"
                        "- MathTex() only: keep expressions simple and self-contained (e.g. MathTex(r'E = mc^2')). "
                        "NEVER put raw text prose, multi-line environments (align, array, tabular), or custom LaTeX packages inside MathTex — they will fail to compile. "
                        "If unsure whether LaTeX will compile, use Text() instead.\n"
                        "- NEVER use Write() on a Group or non-VMobject — Write() only works on VMobjects (Text, MathTex, shapes). Use FadeIn() for Groups.\n"
                        "- NEVER use DrawBorderThenFill() on Text or MathTex — only use it on filled shapes like Circle, Square, Rectangle.\n"
                        "- NEVER use GrowFromCenter() or GrowFromEdge() on a Group — use FadeIn() or AnimationGroup(FadeIn(obj) for obj in group) instead.\n"
                        "- NEVER use Create() or ShowCreation() on a VGroup or any object that contains non-VMobject children — use FadeIn() instead.\n"
                        "- NEVER use ShowCreation() at all — it is deprecated. Use Create() for VMobjects or FadeIn() as a universal fallback.\n"
                        "- When in doubt about whether an animation supports a Mobject, use FadeIn()/FadeOut() — they work on ALL Mobject types without raising NotImplementedError.\n"
                        "- NEVER use ThreeDScene or any 3D scene class — always subclass Scene or MovingCameraScene only. ThreeDScene uses ThreeDCamera which lacks .frame and is incompatible with standard camera moves.\n"
                        "- NEVER use self.camera.frame unless the scene subclasses MovingCameraScene. For plain Scene, do not animate the camera at all.\n"
                        "- NEVER use self.time — Scene objects have no .time attribute. To track elapsed time in an updater, accumulate dt: define elapsed=[0.0] outside the updater, then inside do elapsed[0] += dt and use elapsed[0] for time-based calculations.\n"
                        "- COLORS: Only these colors have letter variants (A-E): BLUE, GREEN, RED, YELLOW, PURPLE, TEAL, MAROON, GOLD. "
                        "ORANGE, PINK, WHITE, BLACK, GREY/GRAY have NO letter variants — use ORANGE not ORANGE_C, PINK not PINK_A, etc. "
                        "There is NO 'BRIGHT_' prefix in Manim — BRIGHT_RED, BRIGHT_BLUE, BRIGHT_GREEN, etc. do NOT exist. Use RED, BLUE, GREEN or their letter variants (e.g. RED_A through RED_E) instead.\n"
                        "- interpolate_color is a standalone function, NOT a method on color objects. Use interpolate_color(color1, color2, alpha) — never color.interpolate_color(...).\n"
                        "SCREEN MANAGEMENT (critical — prevents overlapping objects):\n"
                        "- Each scene should show ONE idea at a time. Before introducing new objects, FadeOut everything currently on screen.\n"
                        "- NEVER let more than 3-4 objects be visible simultaneously — the screen gets cluttered fast in portrait mode.\n"
                        "- Use self.play(FadeOut(*self.mobjects)) to clear the entire screen at once before a new visual idea.\n"
                        "- Space objects vertically with at least 0.8 units of gap between them. Portrait frame is 16 units tall — use it top to bottom.\n"
                        "- Place title/header elements near the top (y > 4), main visuals in the center (-2 < y < 2), and supporting labels near the bottom (y < -3).\n"
                        "- After placing each object, mentally check it does not overlap any existing object before animating it in.\n"
                        "LABEL POSITIONING (critical — this is a common source of bugs):\n"
                        "- NEVER use hardcoded coordinates to place a label near an object.\n"
                        "- ALWAYS use .next_to(object, direction, buff=0.2) to attach a label to its subject.\n"
                        "- Valid directions: UP, DOWN, LEFT, RIGHT, UR, UL, DR, DL.\n"
                        "- If a label must sit inside or centered on an object, use label.move_to(object.get_center()).\n"
                        "- When an object moves, update the label using .next_to() inside the animation or with an UpdateFromFunc.\n"
                        "- Return ONLY valid Python. No markdown fences, no explanation.\n"
                    )

                    scene_manim_code = ""
                    async with anthropic_client.messages.stream(
                        model="claude-opus-5-5",
                        max_tokens=64000,
                        messages=[{"role": "user", "content": scene_manim_prompt}],
                    ) as stream:
                        async for text in stream.text_stream:
                            scene_manim_code += text

                    scene_manim_code = scene_manim_code.strip()
                    if scene_manim_code.startswith("```"):
                        scene_manim_code = "\n".join(scene_manim_code.split("\n")[1:])
                    scene_manim_code = scene_manim_code.strip()
                    if scene_manim_code.endswith("```"):
                        scene_manim_code = "\n".join(scene_manim_code.split("\n")[:-1]).strip()

                    scene_video_path = await asyncio.to_thread(
                        _render_scene, scene_manim_code, pid, scene_num
                    )
                    merged_path = await asyncio.to_thread(
                        _merge_scene, scene_video_path, audio_path, pid, scene_num, exact_duration
                    )
                    return merged_path

                total_scenes = len(storyboard)
                scene_final_paths = await asyncio.gather(*[
                    _process_one_scene(scene, i + 1, total_scenes, paper_id)
                    for i, scene in enumerate(storyboard)
                ])

                # ── 5. Concatenate all scene clips into the final video ──
                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "concatenating",
                }))

                def _concat_scenes(paths, pid):
                    videos_dir = os.path.join(MEDIA_DIR, "videos")
                    concat_list = os.path.join(videos_dir, f"{pid}_concat.txt")
                    final_path = os.path.join(videos_dir, f"{pid}_final.mp4")
                    with open(concat_list, "w") as f:
                        for p in paths:
                            f.write(f"file '{p}'\n")
                    result = subprocess.run(
                        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                         "-i", concat_list, "-c", "copy", final_path],
                        capture_output=True, text=True, timeout=120,
                    )
                    if result.returncode != 0:
                        raise Exception(f"Concat failed: {result.stderr[-300:]}")
                    os.remove(concat_list)
                    return f"/media/videos/{pid}_final.mp4"

                final_video_url = await asyncio.to_thread(_concat_scenes, scene_final_paths, paper_id)

                # ── 6. Generate key takeaways + quiz in parallel ──
                async def _gen_takeaways():
                    prompt = (
                        f"Based on the following research paper summary, produce a JSON array of 5-7 key concepts. "
                        f"Each entry must have:\n"
                        f'  "term": the concept name (2-5 words)\n'
                        f'  "definition": a plain-language explanation (1-2 sentences, written for {_audience})\n'
                        f"Return ONLY a valid JSON array. No markdown, no explanation.\n"
                        f'Example: [{{"term": "Neural Network", "definition": "A system loosely inspired by the brain..."}}]\n\n'
                        f"Summary:\n{summary}"
                    )
                    try:
                        text_out = ""
                        async with anthropic_client.messages.stream(
                            model="claude-haiku-4-5-20251001",
                            max_tokens=1024,
                            messages=[{"role": "user", "content": prompt}],
                        ) as stream:
                            async for chunk in stream.text_stream:
                                text_out += chunk
                        m = _re.search(r'\[.*\]', text_out, _re.DOTALL)
                        return json.loads(m.group()) if m else []
                    except Exception:
                        return []

                async def _gen_quiz():
                    prompt = (
                        f"Based on the following research paper summary, create a quiz of 3-5 multiple-choice questions "
                        f"to test comprehension of the key ideas. Write the questions for {_audience}.\n"
                        f"Each question must have:\n"
                        f'  "question": the question text\n'
                        f'  "options": an array of exactly 4 answer strings (do NOT include A/B/C/D prefixes)\n'
                        f'  "answer": the 0-based index of the correct option\n'
                        f'  "explanation": one sentence explaining why the answer is correct\n'
                        f"Return ONLY a valid JSON array. No markdown, no extra text.\n"
                        f'Example: [{{"question": "What does a neural network do?", "options": ["Stores data", "Learns patterns", "Manages memory", "Encrypts files"], "answer": 1, "explanation": "Neural networks learn patterns from training data."}}]\n\n'
                        f"Summary:\n{summary}"
                    )
                    try:
                        text_out = ""
                        async with anthropic_client.messages.stream(
                            model="claude-haiku-4-5-20251001",
                            max_tokens=1024,
                            messages=[{"role": "user", "content": prompt}],
                        ) as stream:
                            async for chunk in stream.text_stream:
                                text_out += chunk
                        m = _re.search(r'\[.*\]', text_out, _re.DOTALL)
                        return json.loads(m.group()) if m else []
                    except Exception:
                        return []

                async def _gen_suggested_papers():
                    prompt = (
                        f"Based on the following research paper summary, recommend 3-5 real, published papers "
                        f"that a reader should explore next to deepen their understanding of this topic.\n"
                        f"Each recommendation must have:\n"
                        f'  "title": the full paper title\n'
                        f'  "authors": author(s) as a short string (e.g. "LeCun et al." or "Smith & Jones")\n'
                        f'  "year": publication year as a number\n'
                        f'  "reason": one sentence explaining how it complements or extends this paper\n'
                        f"Return ONLY a valid JSON array. No markdown, no extra text.\n"
                        f'Example: [{{"title": "Attention Is All You Need", "authors": "Vaswani et al.", "year": 2017, "reason": "Introduces the transformer architecture that this paper builds upon."}}]\n\n'
                        f"Summary:\n{summary}"
                    )
                    try:
                        text_out = ""
                        async with anthropic_client.messages.stream(
                            model="claude-haiku-4-5-20251001",
                            max_tokens=1024,
                            messages=[{"role": "user", "content": prompt}],
                        ) as stream:
                            async for chunk in stream.text_stream:
                                text_out += chunk
                        m = _re.search(r'\[.*\]', text_out, _re.DOTALL)
                        return json.loads(m.group()) if m else []
                    except Exception:
                        return []

                key_takeaways, quiz, suggested_papers = await asyncio.gather(
                    _gen_takeaways(), _gen_quiz(), _gen_suggested_papers()
                )

                _kt, _qz, _sp = key_takeaways, quiz, suggested_papers
                await database_sync_to_async(lambda: Paper.objects.filter(id=paper_id).update(
                    video_path=final_video_url, status="completed",
                    key_takeaways=_kt, quiz=_qz, suggested_papers=_sp
                ))()

                # ── 7. Done ──
                await self.send(text_data=json.dumps({
                    "websocket_type": "generate_video",
                    "status": "DONE",
                    "video_url": final_video_url,
                    "summary": summary,
                    "key_takeaways": key_takeaways,
                    "quiz": quiz,
                    "suggested_papers": suggested_papers,
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
