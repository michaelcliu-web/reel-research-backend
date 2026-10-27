# App Backend

Django REST Framework backend with Clerk authentication and WebSocket support via Django Channels.

## Setup

### Prerequisites
- Python 3.9+
- PostgreSQL 15+
- A [Clerk](https://clerk.dev) account

### Local Development

1. Create a virtual environment:
```bash
python3.9 -m venv venv39
source venv39/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy the environment file and fill in your values:
```bash
cp .env.example .env
```

4. Create the database:
```bash
createdb app_db
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Create a superuser:
```bash
python manage.py createsuperuser
```

7. Run the development server:
```bash
python manage.py runserver
```

### Docker

```bash
docker-compose up --build
```

## Project Structure

```
app-backend/
├── config/           # Django project settings
│   ├── settings/
│   │   ├── base.py         # shared settings
│   │   ├── local.py        # local overrides
│   │   └── production.py   # production overrides
│   ├── asgi.py
│   ├── wsgi.py
│   └── urls.py
├── api/              # Users (custom user model, admin, /api/users/)
├── clerkauth/        # Clerk JWT decoding, user resolution, WebSocket auth middleware
├── core/             # Health check, media serving, Sentry helper
├── papers/           # Paper uploads and video generation
│   ├── consumers.py  # WebSocket entry point (ws/app/), dispatches by websocket_type
│   ├── handlers/     # One module per WebSocket message type
│   ├── pipeline/     # PDF → summary → storyboard → TTS → Manim → final video
│   └── prompts/      # All LLM prompts
├── deploy/           # Deployment scripts and configs
└── manage.py
```

Run tests with `python manage.py test`.

## API Endpoints

- `GET /health/` - Health check
- `GET /api/users/me/` - Current user
- `POST /api/users/{id}/edit/` - Update user
