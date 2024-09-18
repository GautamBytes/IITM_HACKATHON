# Clause-Crafters: Turning Your Documents into Chatty Friends!

## Introduction
Welcome to Clause-Crafters! This application processes documents and provides answers to your queries by extracting relevant information from the given PDFs. Follow the instructions below to set up and run the app.

## Prerequisites
- Python 3.12 installed on your system
- Virtual environment setup

## Setup and Running the Application

### Step 2: Create and Activate Virtual Environments

#### Terminal 1: Streamlit Environment
1. Create a virtual environment:
    ```bash
    python -m venv .venv
    ```

2. Activate the virtual environment:
    - On Windows:
      ```bash
      .venv\Scripts\activate
      ```
    - On macOS/Linux:
      ```bash
      source .venv/bin/activate
      ```

3. Install the required packages:
    ```bash
    pip install -r requirements.txt and pip install -r requirements_Frontend.txt #or simply run one command-->pip install -r requirements1.txt
    ```

#### Terminal 2: FastAPI Backend Environment
1. Create and activate the virtual environment:

# Create the FastAPI backend virtual environment
python -m venv fastapi_env

    - On Windows:
      ```bash
      fastapi_env\Scripts\activate
      ```
    - On macOS/Linux:
      ```bash
      source fastapi_env/bin/activate
      ```

2. Install the required packages:
    ```bash
    pip install -r requirements_Backend.txt #or simply run one command-->pip install -r requirements1.txt
    ```

### Step 3: Start the FastAPI Backend
In Terminal 2, navigate to the backend directory (if applicable) and start the FastAPI backend:

```bash
uvicorn backend:app --reload
```

### Step 4: Run the Streamlit Application
In Terminal 1, run the Streamlit app:

```bash
streamlit run finalapp.py
```

## Usage
Once the app is running, open the provided URL (usually `http://localhost:8501`) in your web browser. You can start asking questions and view the answers extracted from the provided PDFs.

## Troubleshooting
If you encounter any issues, ensure that all dependencies are installed correctly and the virtual environments are activated. Check for any error messages in the terminal and resolve any missing dependencies or configuration issues.









