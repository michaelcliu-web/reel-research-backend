import json
import shutil
import tempfile
from unittest import mock

import fitz
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.core.files.base import ContentFile
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from api.models import CustomUser
from papers.consumers import AppConsumer
from papers.models import Paper
from papers.pipeline import llm, pdf
from papers.pipeline.storyboard import parse_storyboard, split_summary

PAPER_TEXT = "Attention lets every token look at every other token. " * 5


def make_pdf(text):
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), text, fontsize=8)
    data = doc.tobytes()
    doc.close()
    return data


class StoryboardTests(SimpleTestCase):
    def test_split_summary(self):
        self.assertEqual(
            split_summary("SUMMARY:\nThe summary.\n\nNARRATION:\nThe narration."),
            ("The summary.", "The narration."),
        )

    def test_split_summary_without_narration_uses_text_for_both(self):
        self.assertEqual(split_summary("just text"), ("just text", "just text"))

    def test_parse_storyboard_with_surrounding_prose(self):
        self.assertEqual(parse_storyboard('Here you go:\n[{"scene": 1}]\nEnjoy'), [{"scene": 1}])

    def test_parse_storyboard_fixes_smart_quotes_and_raw_newlines(self):
        text = '[{“narration”: "line one\nline two"}]'
        self.assertEqual(parse_storyboard(text), [{"narration": "line one\nline two"}])

    def test_parse_storyboard_empty(self):
        self.assertIsNone(parse_storyboard("  "))


class LlmHelperTests(SimpleTestCase):
    def test_extract_json_array(self):
        self.assertEqual(llm.extract_json_array('Sure! [1, 2]'), [1, 2])
        self.assertEqual(llm.extract_json_array("no array"), [])

    def test_strip_code_fences(self):
        self.assertEqual(llm.strip_code_fences("```python\nx = 1\n```\n"), "x = 1")
        self.assertEqual(llm.strip_code_fences("x = 1"), "x = 1")

    def test_ask_json_array_returns_empty_on_error(self):
        with mock.patch.object(llm, "complete", side_effect=RuntimeError("boom")):
            self.assertEqual(async_to_sync(llm.ask_json_array)("prompt"), [])


class PdfTests(SimpleTestCase):
    def test_extract_text_truncates(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(make_pdf(PAPER_TEXT))
            f.flush()
            self.assertIn("Attention lets every token", pdf.extract_text(f.name))
            with mock.patch.object(pdf, "MAX_PAPER_CHARS", 10):
                self.assertEqual(len(pdf.extract_text(f.name)), 10)


STORYBOARD = [
    {"scene": 1, "narration": "First.", "visuals": "A circle.", "duration": 4},
    {"scene": 2, "narration": "Second.", "visuals": "A square.", "duration": 6},
]


def fake_stream_text(prompt, model, max_tokens):
    """Stand-in for the Anthropic stream, keyed off each prompt's opening words."""
    if prompt.startswith("Pretend you are"):
        chunks = ["SUMMARY:\nThe summary.", "\n\nNARRATION:\nThe narration."]
    elif prompt.startswith("You are planning"):
        chunks = [json.dumps(STORYBOARD)]
    elif prompt.startswith("Generate a Manim"):
        chunks = ["```python\nclass PaperScene: pass\n```"]
    elif "key concepts" in prompt:
        chunks = ['[{"term": "Attention", "definition": "Looking around."}]']
    elif "create a quiz" in prompt:
        chunks = ['[{"question": "Q?", "options": ["a", "b", "c", "d"], "answer": 1, "explanation": "E"}]']
    elif "recommend 3-5" in prompt:
        chunks = ['[{"title": "T", "authors": "A", "year": 2017, "reason": "R"}]']
    elif prompt.startswith("You are a helpful research assistant"):
        chunks = ["Because ", "attention."]
    else:
        raise AssertionError(f"Unexpected prompt: {prompt[:80]}")

    async def gen():
        for chunk in chunks:
            yield chunk
    return gen()


class ConsumerTests(TransactionTestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root)
        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)

        patcher = mock.patch.object(llm, "stream_text", side_effect=fake_stream_text)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.user = CustomUser.objects.create(email="owner@example.com", clerk_id="user_owner")
        self.paper = Paper.objects.create(user=self.user, title="Attention")
        self.paper.pdf_file.save("attention.pdf", ContentFile(make_pdf(PAPER_TEXT)))

    async def _session(self, user, *messages, until=None):
        """Connect as `user`, send `messages`, and collect replies until `until(reply)` is true."""
        communicator = WebsocketCommunicator(AppConsumer.as_asgi(), "/ws/app/")
        communicator.scope["user"] = user
        connected, _ = await communicator.connect()
        if not connected:
            return connected, []
        replies = [await communicator.receive_json_from()]
        for message in messages:
            await communicator.send_json_to(message)
        while until and not until(replies[-1]):
            replies.append(await communicator.receive_json_from(timeout=5))
        await communicator.disconnect()
        return connected, replies

    def session(self, user, *messages, until=None):
        return async_to_sync(self._session)(user, *messages, until=until)

    def test_rejects_anonymous(self):
        connected, _ = self.session(AnonymousUser())
        self.assertFalse(connected)

    def test_ping(self):
        _, replies = self.session(self.user, {"type": "ping"}, until=lambda r: r.get("type") == "pong")
        self.assertEqual(replies, [
            {"type": "connection_established", "message": "Connected successfully"},
            {"type": "pong"},
        ])

    @mock.patch("papers.pipeline.render.concat_scenes")
    @mock.patch("papers.pipeline.render.merge_scene")
    @mock.patch("papers.pipeline.render.render_scene")
    @mock.patch("papers.pipeline.tts.synthesize_scene")
    def test_generate_video(self, synthesize_scene, render_scene, merge_scene, concat_scenes):
        synthesize_scene.side_effect = lambda text, pid, snum, hint: (f"/a/{snum}.mp3", hint + 0.5)
        render_scene.side_effect = lambda code, pid, snum: f"/v/{snum}.mp4"
        merge_scene.side_effect = lambda video, audio, pid, snum, duration: f"/v/{snum}_merged.mp4"
        concat_scenes.return_value = f"/media/videos/{self.paper.id}_final.mp4"

        _, replies = self.session(
            self.user,
            {"websocket_type": "generate_video", "paper_id": str(self.paper.id), "skill_level": "5th_grade"},
            until=lambda r: r.get("status") in ("DONE", "error"),
        )
        replies = replies[1:]

        self.assertTrue(all(r["websocket_type"] == "generate_video" for r in replies))
        statuses = [r["status"] for r in replies]
        self.assertEqual(statuses[0], "parsing_pdf")
        self.assertEqual(statuses[-1], "DONE", replies[-1])
        self.assertEqual(statuses.count("processing_scene"), 2)
        for expected in ["summarizing", "summarizing_done", "generating_storyboard", "storyboard_done", "concatenating"]:
            self.assertIn(expected, statuses)
        self.assertEqual(
            "".join(r.get("chunk", "") for r in replies if r["status"] == "summarizing"),
            "SUMMARY:\nThe summary.\n\nNARRATION:\nThe narration.",
        )
        self.assertEqual(next(r for r in replies if r["status"] == "storyboard_done")["scene_count"], 2)

        # Manim gets fence-stripped code, and each scene is cut to its narration length
        render_scene.assert_any_call("class PaperScene: pass", self.paper.id, 1)
        merge_scene.assert_any_call("/v/2.mp4", "/a/2.mp3", self.paper.id, 2, 6.5)
        concat_scenes.assert_called_once_with(["/v/1_merged.mp4", "/v/2_merged.mp4"], self.paper.id)

        done = replies[-1]
        self.assertEqual(done["video_url"], concat_scenes.return_value)
        self.assertEqual(done["summary"], "The summary.")
        self.assertEqual(done["key_takeaways"][0]["term"], "Attention")
        self.assertEqual(done["quiz"][0]["answer"], 1)
        self.assertEqual(done["suggested_papers"][0]["year"], 2017)

        self.paper.refresh_from_db()
        self.assertEqual(self.paper.status, "completed")
        self.assertEqual(self.paper.narration_script, "The narration.")
        self.assertEqual(self.paper.video_path, concat_scenes.return_value)
        self.assertEqual(self.paper.quiz, done["quiz"])

    def test_generate_video_rejects_other_users_paper(self):
        intruder = CustomUser.objects.create(email="intruder@example.com", clerk_id="user_intruder")

        _, replies = self.session(
            intruder,
            {"websocket_type": "generate_video", "paper_id": str(self.paper.id)},
            until=lambda r: r.get("status") == "error",
        )

        self.assertEqual(len(replies), 2)
        self.paper.refresh_from_db()
        self.assertEqual(self.paper.status, "uploaded")

    def test_generate_video_requires_paper_id(self):
        _, replies = self.session(self.user, {"websocket_type": "generate_video"}, until=lambda r: "status" in r)
        self.assertEqual(replies[-1], {"websocket_type": "generate_video", "status": "error", "message": "Missing paper_id."})

    def test_ask_question_streams_answer(self):
        _, replies = self.session(
            self.user,
            {"websocket_type": "ask_question", "video_id": str(self.paper.id), "question": "Why?"},
            until=lambda r: r.get("status") == "done" or "error" in r,
        )
        replies = replies[1:]

        self.assertEqual(replies[-1]["status"], "done", replies[-1])
        self.assertEqual("".join(r.get("chunk", "") for r in replies), "Because attention.")
        self.assertTrue(all(r["video_id"] == str(self.paper.id) for r in replies))

    def test_ask_question_rejects_other_users_paper(self):
        intruder = CustomUser.objects.create(email="intruder@example.com", clerk_id="user_intruder")
        _, replies = self.session(
            intruder,
            {"websocket_type": "ask_question", "video_id": str(self.paper.id), "question": "Why?"},
            until=lambda r: "error" in r,
        )
        self.assertIn("does not exist", replies[-1]["error"])

    def test_list_videos_returns_only_completed_papers(self):
        Paper.objects.filter(id=self.paper.id).update(status="completed", summary="x" * 250, video_path="")
        Paper.objects.create(user=self.user, title="Still rendering")

        _, replies = self.session(self.user, {"websocket_type": "list_videos"}, until=lambda r: "videos" in r)

        videos = replies[-1]["videos"]
        self.assertEqual([v["id"] for v in videos], [str(self.paper.id)])
        self.assertEqual(videos[0]["summary"], "x" * 200 + "...")
        self.assertEqual(videos[0]["thumbnail_url"], "")
