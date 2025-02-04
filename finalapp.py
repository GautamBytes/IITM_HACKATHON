import streamlit as st
import os
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings, ChatNVIDIA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from dotenv import load_dotenv
from unidecode import unidecode
from datetime import datetime
import time
import requests
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, PageBreak, Image, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
from PIL import Image as PILImage
import speech_recognition as sr
from gtts import gTTS
import tempfile
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import firestore

import json
import uuid


# Load the credentials and initialize Firebase
if not firebase_admin._apps:
  cred = credentials.Certificate("C:/Users/manch/Downloads/NLP_TOOL_12/NLP_TOOL/firebase_credentials.json")
  firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()


# New functions for collaborative review
def get_or_create_session_id():
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    return st.session_state.session_id

# Save an annotation in Firestore
def save_annotation(session_id, annotation):
    # Reference to the collection
    collection_ref = db.collection('annotations')
    # Add a new document to the collection with the session_id as a field
    collection_ref.add({
        'session_id': session_id,
        'annotation': annotation
    })

# Get annotations for a session_id
def get_annotations(session_id):
    # Reference to the collection
    collection_ref = db.collection('annotations')
    # Query the collection for documents with the specified session_id
    query = collection_ref.where('session_id', '==', session_id).stream()
    
    annotations = []
    for doc in query:
        annotations.append(doc.to_dict()['annotation'])
    
    return annotations

#For document tone
def basic_sentiment_analysis(text):
    # Lists of positive and negative words often found in contracts
    positive_words = ['agree', 'benefit', 'cooperate', 'fair', 'mutual', 'reasonable']
    negative_words = ['terminate', 'breach', 'dispute', 'penalty', 'litigation', 'liability']

    # Convert text to lowercase for easier comparison
    text = text.lower()

    # Count occurrences of positive and negative words
    positive_count = sum(text.count(word) for word in positive_words)
    negative_count = sum(text.count(word) for word in negative_words)

    # Determine overall sentiment
    if positive_count > negative_count:
        return "Positive", positive_count, negative_count
    elif negative_count > positive_count:
        return "Negative", positive_count, negative_count
    else:
        return "Neutral", positive_count, negative_count

def display_basic_sentiment(contract_text):
    sentiment, pos_count, neg_count = basic_sentiment_analysis(contract_text)
    
    st.subheader("Basic Contract Sentiment Analysis")
    st.write(f"Overall Sentiment: {sentiment}")
    st.write(f"Positive word count: {pos_count}")
    st.write(f"Negative word count: {neg_count}")
    st.write("Note: This is a very basic analysis and should not be considered as legal advice.")


# Voice command functions
def recognize_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.sidebar.write("Listening... Speak now.")
        audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
        st.sidebar.write("Processing speech...")
    
    try:
        text = recognizer.recognize_google(audio)
        return text
    except sr.UnknownValueError:
        st.sidebar.error("Sorry, I couldn't understand that.")
        return None
    except sr.RequestError:
        st.sidebar.error("Sorry, there was an error processing your speech.")
        return None
    
def text_to_speech(text):
    tts = gTTS(text=text, lang='en')
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        tts.save(fp.name)
        return fp.name
    
# Function to handle speech recognition in a separate thread
def speech_recognition_thread():
    while st.session_state.voice_mode:
        spoken_question = recognize_speech()
        if spoken_question:
            st.session_state.question = spoken_question
            st.experimental_rerun()


# Load the logo image
logo_path = "Team_images/logo.png"

logo_base64 = None
if os.path.exists(logo_path):
    logo_image = PILImage.open(logo_path)
    import base64
    from io import BytesIO

    def image_to_base64(img):
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

    logo_base64 = image_to_base64(logo_image)

if logo_base64:
    st.markdown(
        f"""
        <div style="display: flex; justify-content: center; align-items: center; background-color: transparent; padding: -250px 0;">
            <img src="data:image/png;base64,{logo_base64}" style="height: 280px; width: auto;">
        </div>
        """,
        unsafe_allow_html=True
    )

width, height = A4
styles = getSampleStyleSheet()
styleN = styles["BodyText"]
styleN.alignment = TA_LEFT
styleBH = styles["Normal"]
styleBH.alignment = TA_CENTER

load_dotenv()
os.environ['NVIDIA_API_KEY'] = os.getenv("NVIDIA_API_KEY")

# Session State Initialization
if "vectors" not in st.session_state:
    st.session_state["vectors"] = None
if "answers" not in st.session_state:
    st.session_state["answers"] = {}
if "history" not in st.session_state:
    st.session_state["history"] = []
if "selected_question" not in st.session_state:
    st.session_state["selected_question"] = None
if "shareable_link" not in st.session_state:
    st.session_state["shareable_link"] = None
if 'voice_mode' not in st.session_state:
    st.session_state.voice_mode = False
if 'question' not in st.session_state:
    st.session_state.question = ''
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = []

st.markdown("""
    <style>
        body {
            background-color: #121212;
            color: #e0e0e0;
        }
        .main-title {
            text-align: center;
            font-size: 2.5em;
            margin-top: -70px;
            color: #ffffff;
        }
        .sidebar .sidebar-content {
            background-color: #1e1e1e;
            color: #e0e0e0;
        }
        .sidebar-header {
            font-size: 1.5em;
            margin-bottom: 10px;
            color: #bb86fc;
        }
        .question-title {
            font-size: 1.2em;
            font-weight: bold;
            color: #bb86fc;
        }
        .stTextArea textarea {
            background-color: #1e1e1e;
            color: #e0e0e0;
        }
        .stButton button {
            background-color: #424046;
            color: white;
        }
        .stMultiselect [role="combobox"] {
            background-color: #1e1e1e;
            color: #e0e0e0;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-title'>Clause-Crafters: Turning Your Documents into Chatty Friends!</h1>", unsafe_allow_html=True)

# Predefined questions from IITM_questions PDF
iitm_questions = {
    "1": "What are the additional documents that have to be read along with the Standard General Conditions of Contract?",
    "2": "What is the impact of breaching the contract conditions on subcontracting?",
    "3": "What is the deadline to submit the proposed project schedule?",
    "4": "What determines the completion of performance of the contract?",
    "5": "Can the stones/rocks/boulders obtained during excavation be used for construction if found technically satisfactory?",
    "6": "Does the contract document contain a 'third-party liability relationship' provision?"
}

def main():
    st.markdown(
    """
    <h2 style='text-align: center; font-size: 32px; color: white;'>
    Contract Review and Q&A System
    </h2>
    """,
    unsafe_allow_html=True
)


     # Sidebar for mode selection
    mode = st.sidebar.radio("Select Mode", ["Q&A", "Collaborative Review"])

    if mode == "Q&A":
        st.header("Contract Q&A")
    
        def initialize_vectorstore():
            with st.spinner("Processing documents, please wait..."):
                embeddings = NVIDIAEmbeddings()
                all_docs = []
        
                # Process the default GCC analysis PDF
                default_pdf = "./pdf_folder/GCC_analysis(IITM).pdf"
                if os.path.exists(default_pdf):
                    loader = PyPDFLoader(default_pdf)
                    docs = loader.load()
                    all_docs.extend(docs)
        
                # Process uploaded files
                for uploaded_file in st.session_state.uploaded_files:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                        temp_file.write(uploaded_file.getvalue())
                        temp_file_path = temp_file.name
        
                    loader = PyPDFLoader(temp_file_path)
                    docs = loader.load()
                    all_docs.extend(docs)
                    os.unlink(temp_file_path)  # Remove the temporary file
        
                # Split documents
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=50)
                final_documents = text_splitter.split_documents(all_docs)
        
                st.session_state["vectors"] = FAISS.from_documents(final_documents, embeddings)
        
        # File uploader
        uploaded_files = st.file_uploader("Upload additional PDF documents", type="pdf", accept_multiple_files=True)
        if uploaded_files:
            st.session_state.uploaded_files = uploaded_files
            st.success(f"{len(uploaded_files)} file(s) uploaded successfully!")
        
        # Initialize or update vector store
        if st.button("Process Documents"):
            initialize_vectorstore()
            st.success("Documents processed successfully!")
        
        
        def get_answer_for_question(question):
            if st.session_state["vectors"] is None:
                st.error("Please click 'Submit' to process documents first.")
                return None
        
            llm = ChatNVIDIA(model="meta/llama3-70b-instruct")
            prompt_template_str = """Extract the relevant clauses from the context to answer the given question in the following tabular format:
        
        | Question | Reference Clause | Clause Extraction | Summary |
        | --- | --- | --- | --- |
        | {question} | | | |
        
        If the context does not contain enough information to answer the question, write "The document does not contain enough information to answer this question." in the Summary column.
        
        Context:
        {context}
        """
            prompt_template = ChatPromptTemplate.from_template(template=prompt_template_str)
            chain_type_kwargs = {"prompt": prompt_template}
        
            qa_chain = RetrievalQA.from_chain_type(
                llm=llm,
                chain_type="stuff",
                retriever=st.session_state["vectors"].as_retriever(),
                chain_type_kwargs=chain_type_kwargs
            )
        
            with st.spinner(f"Generating answer for your question..."):
                start = time.process_time()
                response = qa_chain(question)
                end = time.process_time()
        
                # Extract the table from the response
                table_lines = response['result'].split('\n')
                table_data = []
                for line in table_lines:
                    row = line.split('|')
                    if len(row) > 1:
                        table_data.append([col.strip() for col in row[1:-1]])
        
                # Display the table
                st.markdown("#### Answer")
                st.table(table_data)
        
                st.write(f"Time taken: {end-start:.2f} seconds")
        
                print("table_data", table_data)
        
                # Check if table_data has at least 3 elements and each element has at least 4 sub-elements
                if len(table_data) > 2 and all(len(row) > 3 for row in table_data):
                    # Create a list with the desired format
                    answer_data = [
                        [question, 
                        table_data[2][1], # Reference Clause
                        table_data[2][2], # Clause Extraction
                        table_data[2][3]] # Summary
                    ]
                else:
                    st.error("The generated table does not have the expected structure.")
                    answer_data = [
                        [question, "N/A", "N/A", "The generated table does not have the expected structure."]
                    ]
        
            return {
                "question": question,
                "answer": answer_data,
                "source_documents": response.get("source_documents", []),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        
        # Function to save chat history and get a shareable link
        def save_chat_history():
            if not st.session_state["history"]:
                st.error("No chat history to save.")
                return
            url = "http://localhost:8000/save_chat/"
            history_data = [{"question": qa[0], "answer": qa[1]['answer']} for qa in st.session_state["history"]]
            response = requests.post(url, json={"history": history_data})
            if response.status_code == 200:
                shareable_link = response.json().get("url")
                st.session_state["shareable_link"] = shareable_link
                st.success("Chat history saved successfully!")
                st.write(f"Shareable Link: {shareable_link}")
            else:
                st.error("Failed to save chat history.")
        
        # Layout for main input area
        st.markdown("## Ask Your Question")
        
        # Add a prominent button for voice input
        if st.button("🎤 Voice Input"):
            spoken_question = recognize_speech()
            if spoken_question:
                st.session_state.question = spoken_question
        
        question = st.text_area("Enter your question (max 250 characters) or use voice input:", 
                                value=st.session_state.question,
                                max_chars=250, height=100)
        
        st.markdown("### Predefined Questions")
        selected_keys = st.multiselect(
            "Select questions:",
            options=list(iitm_questions.keys()),
            format_func=lambda x: iitm_questions[x]
        )
        
        if st.button("Submit"):
            if st.session_state["vectors"] is None:
                initialize_vectorstore()
            if question:
                answer = get_answer_for_question(question)
                if answer:
                    st.session_state["answers"][question] = answer
                    st.session_state["history"].append((question, answer))
        
                    # Text-to-speech for the answer if voice mode is enabled
                    if st.session_state.voice_mode:
                        summary = answer['answer'][0][3] if len(answer['answer'][0]) > 3 else "No summary available."
                        audio_file = text_to_speech(summary)
                        st.audio(audio_file)
                        os.unlink(audio_file)  # Clean up the temporary file
        
            for key in selected_keys:
                question = iitm_questions[key]
                answer = get_answer_for_question(question)
                if answer:
                    st.session_state["answers"][question] = answer
                    st.session_state["history"].append((question, answer))
        
        if st.button("Generate All Answers"):
            if st.session_state["vectors"] is None:
                initialize_vectorstore()
            for q_key in iitm_questions.keys():
                question = iitm_questions[q_key]
                answer = get_answer_for_question(question)
                if answer:
                    st.session_state["answers"][question] = answer
                    st.session_state["history"].append((question, answer))
        
        def coord(x, y, unit=1):
            x, y = x * unit, height -  y * unit
            return x, y            
        
        if st.button("Download"):
            def generate_pdf():
                pdf_filename = "iitm_hackathon_answers.pdf"
                doc = SimpleDocTemplate(pdf_filename, pagesize=letter)
                styles = getSampleStyleSheet()
                elements = []
        
                # Define a custom style for the team information
                custom_style = ParagraphStyle(
                    name='CustomStyle',
                    fontSize=15,
                    spaceAfter=12,  # Space between paragraphs
                )
        
                # Define a style for the team name with larger font and centered alignment
                team_name_style = ParagraphStyle(
                    name='TeamNameStyle',
                    fontSize=32,
                    alignment=1,  # Center alignment
                    spaceAfter=24,  # Space after the team name
                )
        
                # Add the team name at the top with the new style
                elements.append(Paragraph("Team Name: Clause-Crafters", team_name_style))
                elements.append(Spacer(1, 24))  # Add space after the title
        
                # Team images and names
                team_images = [
                    {"image": "Team_images/gautam.jpg", "name": "Gautam Manchandani (TL)"},
                    {"image": "Team_images/madhur.jpg", "name": "Madhur Thareja"},
                    {"image": "Team_images/ishita.jpg", "name": "Ishita Sharma"},
                    {"image": "Team_images/palak.jpg", "name": "Palak Kumari"}
                ]
        
                # Add team member images and names
                for member in team_images:
                    try:
                        elements.append(Image(member["image"], width=1.5 * inch, height=1.5 * inch))
                        elements.append(Paragraph(member["name"], custom_style))
                        elements.append(Spacer(1, 12))
                    except Exception as e:
                        st.error(f"Error loading image {member['image']}: {e}")
        
                elements.append(PageBreak())
        
                title_style = styles['Title']
                title_style.fontSize = 24  # Increase font size of the title
                title_style.alignment = 1
                elements.append(Paragraph("IITM Hackathon Answers", title_style))
                elements.append(Spacer(1, 24))  # Add space after the main title
        
                for _, data in st.session_state["answers"].items():
                    if data["answer"]:
                        answer_data = data["answer"][0]
                        table_data = [['Question', 'Reference Clause', 'Clause Extraction', 'Summary']]
        
                        if len(answer_data) >= 4:
                            table_data.append([
                                Paragraph(answer_data[0], styleN), Paragraph(answer_data[1], styleN),
                                Paragraph(answer_data[2], styleN), Paragraph(answer_data[3], styleN)
                            ])
                        else:
                            table_data.append([
                                Paragraph(data["question"], styleN), 
                                Paragraph("", styleN),
                                Paragraph("", styleN),
                                Paragraph("The document does not contain enough information to answer this question.", styleN)
                            ])
        
                        table = Table(table_data, colWidths=4*[1.5*inch])
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                            ('VALIGN',(0,0),(-1, -1),'TOP'),
                        ]))
                        elements.append(table)
                        elements.append(PageBreak())
                        c = canvas.Canvas("a.pdf", pagesize=A4)
                        table.wrapOn(c, width, height)
                        table.drawOn(c, *coord(1.8, 9.6, inch))
                        c.save()
        
                doc.build(elements)
                return pdf_filename
        
            if st.session_state["answers"]:
                pdf_file = generate_pdf()
                with open(pdf_file, "rb") as file:
                    st.download_button(
                        label="Download PDF",
                        data=file,
                        file_name="iitm_hackathon_answers.pdf",
                        mime="application/pdf"
                    )
            else:
                st.error("No answers available to download.")
        
        if st.button("Share chat"):
            save_chat_history()
        
        # Add a text area for feedback
        st.markdown("### Give Feedback")
        feedback = st.text_input("Enter your feedback (max 120 words):", max_chars=120)
        
        # Add a button to submit feedback
        if st.button("Send"):
            if feedback:
                st.success("Thanks for your feedback, your feedback helps us improve!")
            else:
                st.warning("Please enter your feedback before submitting.")

    elif mode == "Collaborative Review":
        st.header("Collaborative Contract Review")
    
        # Get or create session ID
        session_id = get_or_create_session_id()
    
        # Display session ID for sharing
        st.sidebar.write(f"Session ID: {session_id}")
    
        # Option to join an existing session
        join_session = st.sidebar.text_input("Join existing session (enter session ID):")
        if join_session:
            session_id = join_session
    
        # Display the contract text (you'll need to load this from your document)
        contract_text = st.text_area("Contract Text", "This is a sample contract text. Replace this with actual contract content.", height=300)
    
        # Display basic sentiment analysis
        if contract_text:
            display_basic_sentiment(contract_text)
    
        # Annotation input
        annotation = st.text_input("Add your annotation:")
        if st.button("Submit Annotation"):
            if annotation:
                save_annotation(session_id, {
                    'text': annotation,
                    'user': st.session_state.get('user_name', 'Anonymous')
                })
                st.success("Annotation added successfully!")
    
        # Display annotations
        st.subheader("Annotations")
        annotations = get_annotations(session_id)
        
        if annotations:
            for annotation in annotations:
                st.text(f"{annotation['user']}: {annotation['text']}")
        else:
            st.info("No annotations yet.")
    
        # Real-time updates
        if st.button("Refresh Annotations"):
            annotations = get_annotations(session_id)
            st.success("Annotations refreshed!")
    
        
    # Sidebar content
    st.sidebar.header("Made with 💜")
    st.sidebar.header("History")
    
    # Voice command support in sidebar
    st.sidebar.title("Voice Commands")
    st.session_state.voice_mode = st.sidebar.checkbox("Enable Voice Mode", value=st.session_state.voice_mode)
    
    if st.session_state.voice_mode:
        if st.sidebar.button("Start Listening"):
            spoken_question = recognize_speech()
            if spoken_question:
                st.session_state.question = spoken_question
    
    # Modify the part where answers are displayed to include a "Read Answer" button
    for idx, (question, answer_data) in enumerate(st.session_state["history"], 1):
        with st.sidebar.expander(f"Q{idx}: {question}"):
            st.write(answer_data['answer'])
            if st.button(f"🔊 Read Answer {idx}"):
                summary = answer_data['answer'][0][3] if len(answer_data['answer'][0]) > 3 else "No summary available."
                audio_file = text_to_speech(summary)
                st.audio(audio_file, format='audio/mp3')
                os.unlink(audio_file)  # Clean up the temporary file
if __name__ == "__main__":
    main()