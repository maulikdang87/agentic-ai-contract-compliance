# orchestration_agent.py
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Annotated, List, Dict, Any, Optional
import operator
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage
from modules.agents.document_processor import DocumentProcessor
from modules.agents.research_agent import ResearchAgent

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
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        g = StateGraph(ContractAnalysisState)
        g.add_node("process_docs", self._node_process_docs)
        g.add_node("detect_type", self._node_detect_type)
        g.add_node("get_rules", self._node_get_rules)
        g.add_node("run_analysis", self._node_run_analysis)
        g.add_node("chat_interface", self._node_chat_interface)
        g.add_edge(START, "process_docs")
        g.add_edge("process_docs", "detect_type")
        g.add_edge("detect_type", "get_rules")
        g.add_edge("get_rules", "run_analysis")
        # After analysis, allow up to one chat follow-up before END
        g.add_conditional_edges(
            "run_analysis",
            lambda s: "ask_followup" if not s["processing_complete"] else END,
            {"ask_followup": "chat_interface", END: END}
        )
        g.add_edge("chat_interface", END)
        return g.compile(checkpointer=self.memory)

    def _node_process_docs(self, s: ContractAnalysisState) -> ContractAnalysisState:
        docs = []
        for f in s["uploaded_files"]:
            text = self.document_processor.extract_text(f["file_path"])
            docs.append({"file_name": f["file_name"], "text": text})
        s.update({
            "processed_documents": docs,
            "extracted_text": docs[0]["text"] if docs else None,
            "current_step": "processed",
            "messages": [SystemMessage(content="Documents processed.")]
        })
        return s

    def _node_detect_type(self, s: ContractAnalysisState) -> ContractAnalysisState:
        text = s["extracted_text"]
        ct = self.document_processor.extract_metadata(text).get("contract_type", "General")
        # optionally refine with research agent
        s.update({"contract_type": ct, "current_step": "type_detected",
                  "messages": [SystemMessage(content=f"Contract type: {ct}")]})
        return s

    def _node_get_rules(self, s: ContractAnalysisState) -> ContractAnalysisState:
        q = f"Retrieve compliance rules for {s['contract_type']}"
        rules = self.research_agent.research(q)
        s.update({"compliance_rules": rules, "current_step": "rules_retrieved",
                  "messages": [SystemMessage(content="Compliance rules retrieved.")]})
        return s

    def _node_run_analysis(self, s: ContractAnalysisState) -> ContractAnalysisState:
        """Node for running the research agent analysis with proper rules context"""
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
                rules_context=compliance_rules  # Pass the compliance rules as context
            )
            
            s.update({
                "analysis_results": result,
                "final_report": result,
                "processing_complete": True,
                "messages": [SystemMessage(content="Analysis complete.")]
            })
            return s
            
        except Exception as e:
            s.update({
                "analysis_results": {
                    "status": "error",
                    "error": str(e),
                    "document_type": "Error",
                    "risk_assessment": {
                        "risk_score": 100,
                        "risk_level": "Critical"
                    }
                },
                "final_report": {
                    "status": "error",
                    "error": str(e)
                },
                "processing_complete": True,
                "messages": [SystemMessage(content=f"Analysis failed: {str(e)}")]
            })
            return s


    def _node_chat_interface(self, s: ContractAnalysisState) -> ContractAnalysisState:
        # Expects last message from user in s["messages"]
        last = s["messages"][-1]
        if isinstance(last, HumanMessage):
            prompt = (
                "User follow-up: "
                f"{last.content}\n"
                f"Refer to report: {s['final_report']}"
            )
            resp = self.research_agent.research(prompt)
            s["messages"].append(ToolMessage(tool_call_id="", name="", content=resp))
        return s

    def process_contracts(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
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
        return result["final_report"]
