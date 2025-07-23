
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Annotated, List, Dict, Any, Optional
import operator
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage
from modules.agents.document_processor import DocumentProcessor
from modules.agents.research_agent import ResearchAgent
from dotenv import load_dotenv
import os
import google.generativeai as genai

class ContractAnalysisState(TypedDict):
    uploaded_files: List[Dict[str, Any]]
    processed_documents: List[Dict[str, Any]]
    contract_type: Optional[str]
    extracted_text: Optional[str]
    compliance_rules: Optional[str]
    analysis_results: Optional[Dict[str, Any]]
    final_report: Optional[Dict[str, Any]]
    messages: Annotated[List[AnyMessage], operator.add]
    current_step: str
    processing_complete: bool

class ContractComplianceOrchestrator:
    def __init__(self, research_agent: ResearchAgent):
        self.research_agent = research_agent
        self.document_processor = DocumentProcessor()
        self.memory = MemorySaver()
        
        # Store current session data for chat
        self.current_files = []
        self.current_contract_type = None
        self.current_analysis = None
        self.current_report = None
        self.current_extracted_text = None  # This will store the full contract text
        self.current_compliance_rules = None
        
        load_dotenv()
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("Gemini API key is required. Set GOOGLE_API_KEY environment variable or pass it directly.")
        
        genai.configure(api_key=api_key)
        self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        
        self.graph = self._build_graph()        # Main analysis graph
        self.chat_graph = self._build_chat_graph()  # Chat-only graph
        
    def _call_gemini(self, prompt: str, max_tokens: int = 500) -> str:
        """Helper method to call Gemini API with error handling"""
        try:
            response = self.gemini_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.1
                )
            )
            return response.text.strip()
        except Exception as e:
            print(f"Gemini API error: {e}")
            return "Error occurred while processing request"

    def _build_graph(self) -> StateGraph:
        """Main processing graph for contract analysis"""
        g = StateGraph(ContractAnalysisState)
        g.add_node("process_docs", self._node_process_docs)
        g.add_node("detect_type", self._node_detect_type)
        g.add_node("get_rules", self._node_get_rules)
        g.add_node("run_analysis", self._node_run_analysis)
        
        g.add_edge(START, "process_docs")
        g.add_edge("process_docs", "detect_type")
        g.add_edge("detect_type", "get_rules")
        g.add_edge("get_rules", "run_analysis")
        g.add_edge("run_analysis", END)
        
        return g.compile(checkpointer=self.memory)

    def _build_chat_graph(self) -> StateGraph:
        """Separate graph for chat interactions only"""
        chat_g = StateGraph(ContractAnalysisState)
        chat_g.add_node("chat_interface", self._node_chat_interface)
        chat_g.add_edge(START, "chat_interface")
        chat_g.add_edge("chat_interface", END)
        return chat_g.compile()

    def _node_process_docs(self, s: ContractAnalysisState) -> ContractAnalysisState:
        print("Processing documents...")
        docs = []
        for f in s["uploaded_files"]:
            text = self.document_processor.extract_text(f["file_path"])
            docs.append({"file_name": f["file_name"], "text": text})
        
        # Store for later chat use
        self.current_files = s["uploaded_files"]
        
        s.update({
            "processed_documents": docs,
            "extracted_text": docs[0]["text"] if docs else None,
            "current_step": "processed",
            "messages": [SystemMessage(content="Documents processed.")]
        })
        
        # Store extracted text for chat - FULL CONTRACT TEXT
        self.current_extracted_text = s["extracted_text"]
        print(f"Stored contract text length: {len(self.current_extracted_text) if self.current_extracted_text else 0} characters")
        return s

    def _node_detect_type(self, s: ContractAnalysisState) -> ContractAnalysisState:
        print("Detecting contract type...")
        text = s["extracted_text"]
        ct = self.document_processor.extract_metadata(text).get("contract_type", "General")
        
        # Store for later chat use
        self.current_contract_type = ct
        
        s.update({
            "contract_type": ct, 
            "current_step": "type_detected",
            "messages": [SystemMessage(content=f"Contract type: {ct}")]
        })
        return s

    def _node_get_rules(self, s: ContractAnalysisState) -> ContractAnalysisState:
        print("Retrieving compliance rules...")
        q = f"Retrieve compliance rules for {s['contract_type']}"
        rules = self.research_agent.research(q)
        
        # Store for later chat use
        self.current_compliance_rules = rules
        
        s.update({
            "compliance_rules": rules, 
            "current_step": "rules_retrieved",
            "messages": [SystemMessage(content="Compliance rules retrieved.")]
        })
        return s

    def _node_run_analysis(self, s: ContractAnalysisState) -> ContractAnalysisState:
        """Node for running the research agent analysis with proper rules context"""
        print("Running contract analysis...")
        try:
            contract_text = s.get("extracted_text", "")
            contract_type = s.get("contract_type", "General")
            compliance_rules = s.get("compliance_rules", "")
            
            if not contract_text:
                raise ValueError("No contract text available for analysis")
            
            # Call the research agent's analyze_contract method with rules context
            result = self.research_agent.analyze_contract(
                contract_text=contract_text,
                contract_type=contract_type,
                rules_context=compliance_rules
            )
            
            # Store for later chat use
            self.current_analysis = result
            self.current_report = result
            
            s.update({
                "analysis_results": result,
                "final_report": result,
                "processing_complete": True,
                "messages": [SystemMessage(content="Analysis complete.")]
            })
            return s
            
        except Exception as e:
            error_result = {
                "status": "error",
                "error": str(e),
                "document_type": "Error",
                "risk_assessment": {
                    "risk_score": 100,
                    "risk_level": "Critical"
                }
            }
            
            self.current_analysis = error_result
            self.current_report = error_result
            
            s.update({
                "analysis_results": error_result,
                "final_report": error_result,
                "processing_complete": True,
                "messages": [SystemMessage(content=f"Analysis failed: {str(e)}")]
            })
            return s

    def _node_chat_interface(self, s: ContractAnalysisState) -> ContractAnalysisState:
        """Enhanced chat interface with markdown formatting"""
        print(f"Chat interface called with {len(s['messages'])} messages")
        
        # Get the last human message
        human_messages = [m for m in s["messages"] if isinstance(m, HumanMessage)]
        if not human_messages:
            print("No human messages found")
            return s
        
        last_message = human_messages[-1]
        print(f"Processing question: {last_message.content[:100]}...")
        
        # Get contract analysis and full contract text
        contract_analysis = s.get("final_report") or self.current_report or {}
        contract_type = s.get("contract_type") or self.current_contract_type or "Unknown"
        full_contract_text = s.get("extracted_text") or self.current_extracted_text or ""
        
        # Truncate contract text if too long (keep first 3000 chars for context)
        contract_excerpt = full_contract_text[:3000] + "..." if len(full_contract_text) > 3000 else full_contract_text
        
        # Build detailed context with both analysis AND contract text
        context_parts = []
        if isinstance(contract_analysis, dict):
            if "contract_analysis" in contract_analysis:
                analysis = contract_analysis["contract_analysis"]
                context_parts.append(f"Contract Type: {analysis.get('document_type', contract_type)}")
                
                if "risk_assessment" in analysis:
                    risk = analysis["risk_assessment"]
                    context_parts.append(f"Risk Level: {risk.get('risk_level', 'Unknown')}")
                    context_parts.append(f"Risk Score: {risk.get('risk_score', 'N/A')}")
                
                if "compliance_issues" in analysis:
                    issues = analysis["compliance_issues"]
                    if isinstance(issues, list) and issues:
                        context_parts.append(f"Key Issues: {', '.join(issues[:3])}")
                
                if "recommendations" in analysis:
                    recs = analysis["recommendations"]
                    if isinstance(recs, list) and recs:
                        context_parts.append(f"Recommendations: {', '.join(recs[:2])}")
        
        context_summary = "\n".join(context_parts) if context_parts else str(contract_analysis)[:1000]
        
        # Create enhanced prompt with MARKDOWN formatting instructions
        prompt = f"""You are an expert contract analysis assistant. Answer the user's question using MARKDOWN formatting for better readability.

    User Question: {last_message.content}

    CONTRACT ANALYSIS SUMMARY:
    {context_summary}

    ACTUAL CONTRACT TEXT (First 3000 characters):
    {contract_excerpt}

    FULL ANALYSIS DATA:
    {str(contract_analysis)[:1000]}

    FORMATTING INSTRUCTIONS:
    - Use markdown headers (##, ###) to structure your response
    - Use **bold** for important terms, amounts, and key points
    - Use bullet points (-) for lists
    - Use > blockquotes for direct contract quotes
    - Use `code formatting` for specific clause references
    - Keep response concise but comprehensive
    - Structure information logically with clear sections

    Example format:
    ## Answer Summary
    Brief overview of the answer

    ### Key Findings
    - **Important Point 1**: Details
    - **Important Point 2**: Details

    ### Contract Reference
    > "Direct quote from contract"

    ### Analysis
    Brief analysis based on findings

    Answer in markdown format:"""
        
        # Get response from Gemini with higher token limit
        resp = self._call_gemini(prompt, max_tokens=600)
        
        # Enhanced fallback using research agent with contract text
        if resp.startswith("Error occurred") or not resp.strip():
            print("Gemini failed, using research agent fallback")
            fallback_prompt = f"""
            Answer this question about the contract using markdown formatting: {last_message.content}
            
            Contract Text: {contract_excerpt}
            Analysis: {str(contract_analysis)[:1000]}
            
            Use markdown headers, bold text, bullet points, and blockquotes for better formatting.
            Keep the response structured and concise.
            """
            resp = self.research_agent.research(fallback_prompt)
        
        # Add response to messages
        tool_message = ToolMessage(tool_call_id="chat_response", name="ContractAnalyst", content=resp)
        s["messages"].append(tool_message)
        
        print(f"Generated markdown response: {resp[:100]}...")
        return s


    def handle_chat_question(self, user_question: str, config: dict) -> str:
        """Handle a single chat question using the dedicated chat graph with full contract context"""
        print(f"Handling chat question: {user_question[:100]}...")
        
        try:
            # Create state for chat with stored session data INCLUDING contract text
            chat_state = ContractAnalysisState(
                uploaded_files=[],  # Not needed for chat
                processed_documents=[],
                contract_type=self.current_contract_type,
                extracted_text=self.current_extracted_text,  # INCLUDE FULL CONTRACT TEXT
                compliance_rules=self.current_compliance_rules,
                analysis_results=self.current_analysis,
                final_report=self.current_report,
                messages=[HumanMessage(content=user_question)],
                current_step="chat",
                processing_complete=True
            )
            
            # Use the dedicated chat graph
            result = self.chat_graph.invoke(chat_state, config=config)
            
            # Extract the response from tool messages
            tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
            if tool_messages:
                response = tool_messages[-1].content
                print(f"Chat response generated successfully: {response[:100]}...")
                return response
            else:
                print("No tool messages found in chat result")
                return "Sorry, I could not generate an answer to that question."
                
        except Exception as e:
            print(f"Chat error: {e}")
            return f"Sorry, I encountered an error while processing your question: {str(e)}"

    def process_contracts(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process contracts using the main analysis graph"""
        print("Starting contract processing...")
        
        init = ContractAnalysisState(
            uploaded_files=files,
            processed_documents=[],
            contract_type=None,
            extracted_text=None,
            compliance_rules=None,
            analysis_results=None,
            final_report=None,
            messages=[],
            current_step="start",
            processing_complete=False
        )
        
        config = {"configurable": {"thread_id": "unique_session_id"}}
        result = self.graph.invoke(init, config=config)
        
        print("Contract processing completed")
        return result["final_report"]
