# Healthcare EDI (X12) Parser - Prototype

A minimal web app that parses EDI X12 files into JSON and provides AI explanations via Google Gemini.

## Features

- **File/Text Input**: Paste raw EDI or type in textarea
- **Basic Parser**: Splits by `~` (segments) and `*` (elements), flat structure
- **Simple Error Detection**: Too few elements, invalid numeric fields
- **AI Explanation**: Click any segment or error to get a plain-English explanation from Gemini

## Tech Stack

- **Frontend**: Next.js (React)
- **Backend**: FastAPI (Python)
- **AI**: Google Gemini API

## Setup

### 1. Get a Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Create an API key

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

Create `.env` in the backend folder:

```
GEMINI_API_KEY=your_api_key_here
```

Run the backend:

```bash
uvicorn main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Open the app

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | /parse   | Input: `{ "raw": "ISA*00*..." }` — Returns parsed segments + errors |
| POST   | /explain | Input: `{ "type": "segment", "segment": "NM1", "elements": [...] }` or `{ "type": "error", "segment": "CLM", "error": "..." }` — Returns AI explanation |

## EDI Format (X12)

- Segments separated by `~`
- Elements within a segment separated by `*`
- First element = segment ID (e.g., ISA, NM1, CLM)

## License

MIT
