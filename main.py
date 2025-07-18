import streamlit as st
import tempfile
import os
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
import uuid
# Import your orchestrator and research agent
from modules.agents.research_agent import ResearchAgent
from modules.agents.orchestration_agent import ContractComplianceOrchestrator

# Set page config
st.set_page_config(page_title="Contract Compliance Analysis", layout="wide")

def save_uploaded_file(uploaded_file) -> str:
    """Save uploaded file to a temp directory and returns the path."""
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

@st.cache_resource(show_spinner=False)
def get_orchestrator() -> ContractComplianceOrchestrator:
    research_agent = ResearchAgent()
    orchestrator = ContractComplianceOrchestrator(research_agent)
    return orchestrator

def main():
    st.title("🏛️ Contract Compliance Analysis")

    orchestrator = get_orchestrator()
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = []
    if "final_report" not in st.session_state:
        st.session_state.final_report = None
    if "chat_history" not in st.session_state:  # We'll store messages as langchain messages, starting empty
        st.session_state.chat_history = []

    st.header("1️⃣ Upload Contract Files (PDF, DOCX, TXT)")
    uploaded_files = st.file_uploader(
        "Upload one or more contract files",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="Supported formats: PDF, DOCX, TXT"
    )

    if uploaded_files:
        # Save files to temp and build input list
        st.session_state.uploaded_files = []
        for file in uploaded_files:
            path = save_uploaded_file(file)
            st.session_state.uploaded_files.append({
                "file_name": file.name,
                "file_path": path
            })
        st.success(f"{len(uploaded_files)} file(s) uploaded and saved!")

    if st.session_state.uploaded_files and st.button("Analyze Contracts"):
        with st.spinner("Analyzing contract(s), please wait..."):
            report = orchestrator.process_contracts(st.session_state.uploaded_files)
            st.session_state.final_report = report
            st.session_state.chat_history.clear()
        st.success("Analysis complete! Scroll down to view results and ask questions.")

    # Show Analysis Report
    if st.session_state.final_report:
        st.header("2️⃣ Compliance Analysis Report")
        st.json(st.session_state.final_report)

        st.header("3️⃣ Ask Questions About the Report")

        # Collect user question
        user_question = st.text_input("Enter a question about the report and hit Enter:")

        if user_question:
            # Append user question as HumanMessage
            st.session_state.chat_history.append(HumanMessage(content=user_question))

            with st.spinner("Generating answer..."):
                # Update state messages with new user question
                # Our orchestrator expects the chat_interface node to process these messages
                last_state = {
                    "uploaded_files": st.session_state.uploaded_files,
                    "processed_documents": [],
                    "contract_type": st.session_state.final_report.get("contract_analysis", {}).get("document_type", "General"),
                    "extracted_text": None,
                    "compliance_rules": None,
                    "analysis_results": st.session_state.final_report.get("contract_analysis"),
                    "final_report": st.session_state.final_report,
                    "messages": st.session_state.chat_history,
                    "current_step": "ask_followup",
                    "processing_complete": True
                }

                # Run just the chat_interface node via a graph invoke trick
                # Note: This assumes you can directly access the graph nodes; else create a method in orchestrator
                updated_state = orchestrator.graph.invoke(last_state, config=config)

                # Extract the ToolMessage response
                response_msgs = [m for m in updated_state["messages"] if isinstance(m, ToolMessage)]
                if response_msgs:
                    reply = response_msgs[-1].content
                else:
                    reply = "Sorry, I could not generate an answer to that question."

                # Append bot response to history
                st.session_state.chat_history.append(
                    ToolMessage(tool_call_id="", name="ResearchAgent", content=reply)
                )

            st.markdown(f"**Answer:** {reply}")

if __name__ == "__main__":
   
    main()

