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
    
    # Initialize session state
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = []
    
    if "final_report" not in st.session_state:
        st.session_state.final_report = None
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    # File Upload Section
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

    # Contract Analysis Section
    if st.session_state.uploaded_files and st.button("Analyze Contracts"):
        with st.spinner("Analyzing contract(s), please wait..."):
            try:
                report = orchestrator.process_contracts(st.session_state.uploaded_files)
                st.session_state.final_report = report
                st.session_state.chat_history.clear()
                st.success("Analysis complete! Scroll down to view results and ask questions.")
            except Exception as e:
                st.error(f"Analysis failed: {str(e)}")
                st.session_state.final_report = None

    # Display Analysis Report
    if st.session_state.final_report:
        st.header("2️⃣ Compliance Analysis Report")
        
        # Display report in a more user-friendly format
        with st.expander("📊 View Full Analysis Report", expanded=False):
            st.json(st.session_state.final_report)
        
        # Display key findings
        if isinstance(st.session_state.final_report, dict):
            col1, col2 = st.columns(2)
            
            with col1:
                if "contract_analysis" in st.session_state.final_report:
                    analysis = st.session_state.final_report["contract_analysis"]
                    st.subheader("📋 Contract Type")
                    st.write(analysis.get("document_type", "Unknown"))
                    
                    if "risk_assessment" in analysis:
                        risk = analysis["risk_assessment"]
                        st.subheader("⚠️ Risk Assessment")
                        st.write(f"**Risk Level:** {risk.get('risk_level', 'Unknown')}")
                        st.write(f"**Risk Score:** {risk.get('risk_score', 'N/A')}")
            
            with col2:
                if "contract_analysis" in st.session_state.final_report:
                    analysis = st.session_state.final_report["contract_analysis"]
                    if "compliance_issues" in analysis:
                        st.subheader("🚨 Compliance Issues")
                        issues = analysis["compliance_issues"]
                        if isinstance(issues, list) and issues:
                            for i, issue in enumerate(issues[:3], 1):
                                st.write(f"{i}. {issue}")
                        else:
                            st.write("No major compliance issues detected")

        # Chat Interface Section
        st.header("3️⃣ Ask Questions About the Report")
        
        # Display chat history
        # Display chat history with proper markdown rendering
        if st.session_state.chat_history:
            st.subheader("💬 Conversation History")
            for message in st.session_state.chat_history:
                if isinstance(message, HumanMessage):
                    st.write(f"**🔵 You:** {message.content}")
                elif isinstance(message, ToolMessage):
                    st.write(f"**🤖 Assistant:**")
                    st.markdown(message.content)  # Use st.markdown instead of st.write
                st.divider()  # Better visual separation

        # Question input with better placeholder
        user_question = st.text_input(
            "Enter a question about the report:",
            placeholder="e.g., What does clause 5.2 say about termination? or Summarize the key risks",
            key="question_input"
        )

        # Add button to prevent auto-submission
        ask_button = st.button("Ask Question")

        # Handle question submission ONLY when button is clicked
        if ask_button and user_question and user_question.strip():
            # Add user question to chat history
            st.session_state.chat_history.append(HumanMessage(content=user_question))

            with st.spinner("Generating answer..."):
                try:
                    # Use the dedicated chat handling method with contract text
                    reply = orchestrator.handle_chat_question(user_question, config)
                    
                    # Add bot response to history
                    st.session_state.chat_history.append(
                        ToolMessage(tool_call_id="chat_response", name="ContractAnalyst", content=reply)
                    )
                    
                    # Display the answer with markdown formatting
                    st.subheader("💡 Answer")
                    st.markdown(reply)  # Use st.markdown for proper formatting

                except Exception as e:
                    st.error(f"Error generating response: {str(e)}")
                    print(f"Chat error details: {e}")


        # Clear chat history button
        if st.session_state.chat_history:
            if st.button("🗑️ Clear Chat History"):
                st.session_state.chat_history.clear()
                st.rerun()

if __name__ == "__main__":
    main()

