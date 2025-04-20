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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, PageBreak, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
import tempfile
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import firestore

import json
import uuid


# Load the credentials and initialize Firebase
if not firebase_admin._apps:
  cred = credentials.Certificate("/home/gautam/IITM_HACKATHON/firebase_credentials.json")
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
                st.error("Please click 'Process Documents' to process documents first.")
                return None
        
            llm = ChatNVIDIA(model="meta/llama-4-scout-17b-16e-instruct")
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
                    answer_data = [
                        [question, "N/A", "N/A", "The generated table does not have the expected structure."]
                    ]
        
            return {
                "question": question,
                "answer": answer_data,
                "source_documents": response.get("source_documents", []),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "time_taken": end-start
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
        
        question = st.text_area("Enter your question (max 250 characters):", 
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
                
            answers_to_display = []
            
            if question:
                answer = get_answer_for_question(question)
                if answer:
                    st.session_state["answers"][question] = answer
                    st.session_state["history"].append((question, answer))
                    answers_to_display.append((question, answer))
        
            for key in selected_keys:
                q = iitm_questions[key]
                answer = get_answer_for_question(q)
                if answer:
                    st.session_state["answers"][q] = answer
                    st.session_state["history"].append((q, answer))
                    answers_to_display.append((q, answer))
            
            # Display the answers
            for q, answer_data in answers_to_display:
                st.markdown(f"#### Question: {q}")
                st.table(answer_data["answer"])
                st.write(f"Time taken: {answer_data['time_taken']:.2f} seconds")
                st.markdown("---")
        
        if st.button("Generate All Answers"):
            if st.session_state["vectors"] is None:
                initialize_vectorstore()
            
            # Create a progress bar
            progress_bar = st.progress(0)
            total_questions = len(iitm_questions)
            
            # Container for results
            results_container = st.container()
            
            # Process all questions
            processed_answers = []
            
            for i, q_key in enumerate(iitm_questions.keys()):
                question = iitm_questions[q_key]
                answer = get_answer_for_question(question)
                if answer:
                    st.session_state["answers"][question] = answer
                    st.session_state["history"].append((question, answer))
                    processed_answers.append((question, answer))
                
                # Update progress bar
                progress_bar.progress((i + 1) / total_questions)
            
            # Display a success message when all questions are processed
            st.success(f"Generated answers for all {total_questions} questions!")
            
            # Display the answers in the container
            with results_container:
                for question, answer_data in processed_answers:
                    st.markdown(f"#### Question: {question}")
                    st.table(answer_data["answer"])
                    st.write(f"Time taken: {answer_data['time_taken']:.2f} seconds")
                    st.markdown("---")
        
        def coord(x, y, unit=1):
            x, y = x * unit, height -  y * unit
            return x, y            
        
        if st.button("Download"):
            def generate_pdf():
                pdf_filename = "iitm_hackathon_answers.pdf"
                doc = SimpleDocTemplate(pdf_filename, pagesize=letter)
                styles = getSampleStyleSheet()
                elements = []
        
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
    
    # Display history in sidebar
    for idx, (question, answer_data) in enumerate(st.session_state["history"], 1):
        with st.sidebar.expander(f"Q{idx}: {question}"):
            st.write(answer_data['answer'])
            
if __name__ == "__main__":
    main()
