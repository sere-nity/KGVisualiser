# Knowledge Graph Visualizer

This project is a full-stack application for extracting, visualizing knowledge graphs from PDF. It leverages AI and graph technologies to help users explore relationships within their documents.

---

## Features

- **Upload PDFs/CSVs:** Extracts text and data from uploaded files.
- **AI-Powered Knowledge Graphs:** Uses LLMs to generate and query knowledge graphs from document content.
- **Interactive Visualization:** Visualizes knowledge graphs in the browser using Cytoscape.js.
- **Conversational Interface:** Chat with your documents to extract insights.

---

## Tech Stack

- **Frontend:** Next.js (React, TypeScript, Cytoscape.js)
- **Backend:** FastAPI (Python)
- **Database:** SQLAlchemy (default: PostgreSQL)
- **AI/LLM:** OpenAI API (configurable via environment variables)

---

## Prerequisites

- **Node.js** (v18+ recommended)
- **npm** (v9+ recommended)
- **Python** (v3.9+ recommended)
- **pip** (Python package manager)
- **OpenAI API Key** (for LLM features)

---

## LOCAL Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ai-dashboard.git
cd ai-dashboard
```

### 2. Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt  # If requirements.txt exists, otherwise install FastAPI, SQLAlchemy, etc.
cp .env.example .env             # Create and edit your .env file with your OpenAI key and DB settings
uvicorn main:app --reload        # Starts FastAPI on http://localhost:8000
```

### 3. Frontend Setup

```bash
cd ../frontend
npm install
npm run dev                      # Starts Next.js on http://localhost:3000
```

---

## Environment Variables

- **Backend (`backend/.env`):**
  - `OPENAI_API_KEY=your_openai_key`
  - `DATABASE_URL=sqlite:///./test.db` (or your preferred DB)

- **Frontend:** (if needed, e.g., for API URLs)
  - `NEXT_PUBLIC_API_URL=http://localhost:8000`

---

## Usage

1. Start both backend and frontend servers as above.
2. Open [http://localhost:3000](http://localhost:3000) in your browser.
3. Upload a PDF or CSV, visualize the knowledge graph, and interact via chat.

---

