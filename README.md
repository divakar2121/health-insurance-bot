# Health Insurance Chatbot

AI-powered health insurance advisor for Indian clients. Upload PDF documents, ask questions, and get answers based on your documents.

## Features
- Upload PDF policy documents
- Automatic text chunking and storage in SQL
- LLM-powered Q&A using free models (OpenRouter)
- Q&A history saved in database
- Modern dark theme UI

## Tech Stack
- Flask (Backend)
- SQLAlchemy (Database - SQLite for dev, PostgreSQL for production)
- OpenRouter API (Free LLM access)
- Gunicorn (Production server)

## Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy env file and add your API key
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY

# Run
python app.py
```

## Deployment to Render (Free)

1. Push code to GitHub
2. Go to [Render](https://render.com) and sign up
3. Create new Web Service
4. Connect your GitHub repo
5. Configure:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`
6. Add Environment Variables:
   - `OPENROUTER_API_KEY` - Get from https://openrouter.ai/
   - `DATABASE_URL` - Leave empty for SQLite (free) or use Render's free PostgreSQL
7. Deploy!

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | Your API key from OpenRouter (free tier available) |
| `DATABASE_URL` | PostgreSQL connection string (optional, defaults to SQLite) |
| `SECRET_KEY` | Random secret for sessions |

## Usage

1. Open the app in your browser
2. Upload a PDF (insurance policy document)
3. Ask questions about the policy
4. View Q&A history in the sidebar