# Reel Research Backend

Django backend for [Reel Research](https://github.com/michaelcliu-web/Research-Animator), which turns research papers into short animated explainer videos. It takes PDF uploads, runs the generation pipeline (Claude for the summary, storyboard, and Manim code, ElevenLabs for narration, Manim and ffmpeg for rendering), and streams progress to the frontend over a WebSocket. See the frontend README for the product overview.

## Getting Started

### Prerequisites

- Python 3.9
- PostgreSQL 15 or newer
- ffmpeg, and the system libraries [Manim](https://docs.manim.community/en/stable/installation.html) needs (Cairo, Pango). On macOS: `brew install ffmpeg cairo pango pkg-config`
- A LaTeX install for equations in scenes (e.g. `brew install --cask basictex`)
- API keys for [Anthropic](https://console.anthropic.com), [ElevenLabs](https://elevenlabs.io), and [Clerk](https://clerk.com)

### Installing

```bash
python3.9 -m venv venv39
source venv39/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in the keys
createdb app_db
python manage.py migrate
python manage.py runserver  # serves HTTP and WebSockets on port 8000
```

Then start the [frontend](https://github.com/michaelcliu-web/Research-Animator), which expects the backend at `localhost:8000`.

`docker-compose up --build` starts the API and PostgreSQL. The Docker image does not include ffmpeg, Manim's system libraries, or LaTeX yet, so video rendering only works in a local install.

## Configuration

| Variable | Purpose |
| --- | --- |
| `ENVIRONMENT` | `LOCAL` or `PRODUCTION`; picks `config/settings/local.py` or `production.py` |
| `SECRET_KEY`, `DEBUG` | Django settings |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL connection (production also accepts `DATABASE_URL`) |
| `CLERK_FRONTEND_API`, `CLERK_SECRET_KEY` | Verifying Clerk tokens and looking up user emails |
| `ANTHROPIC_API_KEY` | Summary, storyboard, Manim code, quiz, and Q&A |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | Narration (voice defaults to `21m00Tcm4TlvDq8ikWAM`) |
| `FRONTEND_URL` | Frontend origin |

## API

| Method | Route | Description |
| --- | --- | --- |
| GET | `/health/` | Health check |
| POST | `/api/papers/upload/` | Upload a PDF (`pdf_file`, multipart); returns `paper_id` |
| GET | `/api/users/me/` | Current user |
| POST | `/api/users/{clerk_id}/edit/` | Update your name or email |
| GET | `/media/<path>` | Uploaded PDFs, videos (with Range support for seeking), thumbnails |

REST requests authenticate with `Authorization: Bearer <Clerk session token>`.

### WebSocket protocol

Connect to `ws/app/?token=<Clerk session token>`. Messages are JSON, and the message type goes in `websocket_type`.

| Client sends | Server replies |
| --- | --- |
| `ping` | `pong` |
| `list_videos` | `list_videos` with `videos`: your completed papers with video, thumbnail, takeaways, quiz, reading list |
| `ask_question` with `video_id`, `question` | `ask_answer` messages: `status: "streaming"` with `chunk`, then `status: "done"` (or `error`) |
| `generate_video` with `paper_id`, `skill_level` (`5th_grade`, `10th_grade`, `college`) | `generate_video` messages with `status` (below) |

`generate_video` statuses, in order: `parsing_pdf` (with `pdf_url`), `summarizing` (with streamed `chunk`s), `summarizing_done`, `generating_storyboard`, `storyboard_done` (with `scene_count`), `processing_scene` (with `scene`, `total_scenes`, once per scene), `concatenating`, then `DONE` with `video_url`, `summary`, `key_takeaways`, `quiz`, `suggested_papers`. Any failure sends `error` with `message`.

## Project Structure

```
config/           # Settings (base.py + local/production overrides), URLs, ASGI
api/              # Users: custom user model, admin, /api/users/
clerkauth/        # Clerk token decoding, user lookup/creation, WebSocket auth middleware
core/             # Health check, media serving, Sentry helper
papers/
├── consumers.py  # WebSocket entry point; routes each websocket_type to a handler
├── handlers/     # One module per message type
├── pipeline/     # PDF → summary → storyboard → TTS → Manim → final video
└── prompts/      # All LLM prompts
deploy/           # AWS/EC2 deployment scripts (see deploy/README.md)
```

## Running the Tests

```bash
python manage.py test
```

The tests cover auth, media serving, the pipeline helpers, and every WebSocket message type end to end. Anthropic, ElevenLabs, Manim, and ffmpeg are mocked, so the tests need PostgreSQL but no API keys.

## Built With

- [Django](https://www.djangoproject.com), [Django REST Framework](https://www.django-rest-framework.org), [Channels](https://channels.readthedocs.io): API and WebSockets
- [PostgreSQL](https://www.postgresql.org): storage
- [Anthropic Claude](https://www.anthropic.com): summaries, storyboards, Manim code
- [ElevenLabs](https://elevenlabs.io): narration
- [Manim](https://www.manim.community) and [ffmpeg](https://ffmpeg.org): rendering
- [PyMuPDF](https://pymupdf.readthedocs.io): PDF text extraction
- [Clerk](https://clerk.com): authentication

## Authors

- Michael Liu
- William Du

## License

No license has been chosen yet.
