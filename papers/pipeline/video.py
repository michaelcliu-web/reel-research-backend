import asyncio

from channels.db import database_sync_to_async

from papers.models import Paper
from papers.pipeline import llm, pdf, render, tts
from papers.pipeline.extras import generate_extras
from papers.pipeline.storyboard import parse_storyboard, split_summary
from papers.prompts.audience import audience_for
from papers.prompts.manim import scene_prompt
from papers.prompts.storyboard import storyboard_prompt
from papers.prompts.summary import summary_prompt


async def generate_video(paper, skill_level, emit):
    """Turn a paper into a narrated video, reporting progress via `await emit(status, **fields)`.

    Raises on any failure; the caller decides how to report it.
    """
    audience = audience_for(skill_level)
    paper_id = paper.id

    # ── 1. Parse PDF ──
    await emit("parsing_pdf", pdf_url=paper.pdf_file.url)

    paper_text = await asyncio.to_thread(pdf.extract_text, paper.pdf_file.path)
    if len(paper_text.strip()) < 100:
        raise ValueError("Could not extract meaningful text from the PDF.")

    # ── 2. Summarize (streamed) ──
    await emit("summarizing")

    full_summary_text = ""
    async for text in llm.stream_text(summary_prompt(audience, paper_text), llm.FAST_MODEL, 4096):
        full_summary_text += text
        await emit("summarizing", chunk=text)

    summary, narration_script = split_summary(full_summary_text)

    await emit("summarizing_done")

    await database_sync_to_async(lambda: Paper.objects.filter(id=paper_id).update(
        summary=summary, narration_script=narration_script, status="summarized"
    ))()

    # ── 3. Generate storyboard ──
    # Break the summary into scenes, each with its own narration text, visual
    # concept, and estimated duration, so visuals can be timed to the speech.
    await emit("generating_storyboard")

    storyboard = None
    storyboard_text = await llm.complete(storyboard_prompt(audience, summary), llm.SMART_MODEL, 64000)
    try:
        storyboard = parse_storyboard(storyboard_text)
    except Exception as e:
        print(f"Storyboard parse failed: {e}\nRaw output: {storyboard_text[:300]}")

    if not storyboard:
        raise Exception(f"Failed to generate a valid storyboard after retries. Last output: {storyboard_text[:300]}")

    await emit("storyboard_done", scene_count=len(storyboard))

    # ── 4. Process all scenes in parallel: TTS → Manim code → render → merge ──
    # Each scene's pipeline is independent, so all scenes run concurrently.
    # Within a scene, TTS still runs first to get the exact duration before
    # Manim codegen, preserving the audio-sync guarantee.
    tts_semaphore = asyncio.Semaphore(tts.MAX_CONCURRENT_REQUESTS)
    total_scenes = len(storyboard)

    async def process_scene(scene, scene_num):
        await emit("processing_scene", scene=scene_num, total_scenes=total_scenes)

        async with tts_semaphore:
            audio_path, exact_duration = await asyncio.to_thread(
                tts.synthesize_scene, scene["narration"], paper_id, scene_num, float(scene.get("duration", 5))
            )

        manim_code = await llm.complete(
            scene_prompt(exact_duration, scene["visuals"], scene["narration"]), llm.SMART_MODEL, 64000
        )
        manim_code = llm.strip_code_fences(manim_code)

        scene_video_path = await asyncio.to_thread(render.render_scene, manim_code, paper_id, scene_num)
        return await asyncio.to_thread(
            render.merge_scene, scene_video_path, audio_path, paper_id, scene_num, exact_duration
        )

    scene_final_paths = await asyncio.gather(*[
        process_scene(scene, i + 1) for i, scene in enumerate(storyboard)
    ])

    # ── 5. Concatenate all scene clips into the final video ──
    await emit("concatenating")
    final_video_url = await asyncio.to_thread(render.concat_scenes, scene_final_paths, paper_id)

    # ── 6. Generate key takeaways, quiz and suggested papers in parallel ──
    key_takeaways, quiz, suggested_papers = await generate_extras(audience, summary)

    await database_sync_to_async(lambda: Paper.objects.filter(id=paper_id).update(
        video_path=final_video_url, status="completed",
        key_takeaways=key_takeaways, quiz=quiz, suggested_papers=suggested_papers
    ))()

    # ── 7. Done ──
    await emit(
        "DONE",
        video_url=final_video_url,
        summary=summary,
        key_takeaways=key_takeaways,
        quiz=quiz,
        suggested_papers=suggested_papers,
    )
