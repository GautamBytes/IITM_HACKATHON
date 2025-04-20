# IITM_HACKATHON

This repository contains a Streamlit application with a FastAPI backend.

## Setup Instructions

### Clone the Repository

```bash
git clone https://github.com/GautamBytes/IITM_HACKATHON.git
cd IITM_HACKATHON
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Running the Application

You'll need to run both the Streamlit frontend and FastAPI backend in separate terminals.

### Ubuntu/WSL

#### Terminal 1 (Streamlit Frontend):
```bash
python3.12 -m venv .venv
source .venv/bin/activate
streamlit run finalapp.py
```

#### Terminal 2 (FastAPI Backend):
```bash
python3.12 -m venv fastapi_env
source fastapi_env/bin/activate
uvicorn backend:app --reload
```

### Windows

#### Terminal 1 (Streamlit Frontend):
```bash
python -m venv .venv
.venv\Scripts\activate
streamlit run finalapp.py
```

#### Terminal 2 (FastAPI Backend):
```bash
python -m venv fastapi_env
fastapi_env\Scripts\activate
uvicorn backend:app --reload
```

### macOS

#### Terminal 1 (Streamlit Frontend):
```bash
python3 -m venv .venv
source .venv/bin/activate
streamlit run finalapp.py
```

#### Terminal 2 (FastAPI Backend):
```bash
python3 -m venv fastapi_env
source fastapi_env/bin/activate
uvicorn backend:app --reload
```

## Accessing the Application

Once both services are running:
- Streamlit frontend: http://localhost:8501
- FastAPI backend: http://localhost:8000
