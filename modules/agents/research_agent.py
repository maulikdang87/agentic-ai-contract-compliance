from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain import hub
from modules.tools.web_search_tool import web_search
from modules.tools.compliance_checker_tool import check_compliance_rules
from modules.tools.contract_analyzer_tool import analyze_contract_compliance
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

class ResearchAgent:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )

        self.tools = [
            web_search,
            check_compliance_rules,  # Call the function to get the tool
            analyze_contract_compliance # This tool now expects both contract_text and rules_context
        ]

        self.memory = ConversationBufferMemory(
            return_messages=True,
            memory_key="chat_history"
        )

        self.agent = self._create_agent()

    def _create_agent(self):
        """Create the ReAct agent with enhanced JSON output capability"""
        prompt = PromptTemplate.from_template("""
        You are a Research Agent specialized in contract compliance analysis.

        You have access to the following tools:
        {tools}

        IMPORTANT INSTRUCTIONS:
        1. ALWAYS use the analyze_contract_compliance tool when analyzing contracts
        2. The tool requires both contract_text and rules_context parameters
        3. If rules_context seems invalid, first use check_compliance_rules to get proper rules
        4. NEVER do manual analysis - always use the available tools
        5. Follow the exact format below

        Format your response as follows:

        Question: the input question you must answer
        Thought: you should always think about what to do
        Action: the action to take, should be one of [{tool_names}]
        Action Input: the input to the action (must be properly formatted) 
        Observation: the result of the action
        ... (this Thought/Action/Action Input/Observation can repeat N times)
        Thought: I now know the final answer
        Final Answer: the final answer to the original input question

        Previous conversation:
        {chat_history}

        Question: {input}
        {agent_scratchpad}
        """)

        agent = create_react_agent(
        llm=self.llm,
        tools=self.tools,
        prompt=prompt
        )

        return AgentExecutor(
        agent=agent,
        tools=self.tools,
        memory=self.memory,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=3  # Reduced to prevent loops
        )


    def research(self, query: str) -> str:
        """Execute open-ended research query"""
        try:
            response = self.agent.invoke({"input": query})
            return response.get("output", "No output returned.")
        except Exception as e:
            return f"Error during research: {str(e)}"

    def analyze_contract(self, contract_text: str, contract_type: str = None, rules_context: str = "") -> dict:
        """
        Analyze contract compliance and return structured JSON with:
        1. Contract type detection
        2. Compliance rule extraction
        3. Risk scoring with weighted methodology
        4. Shortcoming identification
        """
        
        try:
            # Enhanced prompt for structured JSON analysis with rules context
            analysis_prompt = f"""
            Analyze the following contract text for compliance and return structured JSON output:

            CONTRACT TEXT:
            {contract_text}

            CONTRACT TYPE: {contract_type or "Unknown"}

            COMPLIANCE RULES TO CHECK AGAINST:
            {rules_context}

            ANALYSIS REQUIREMENTS:
            1. Identify the contract type (use provided type as reference)
            2. Extract all parties involved (companies, individuals with contractual obligations)
            3. Use the analyze_contract_compliance tool with both contract_text and rules_context
            4. Calculate risk score using the weighted methodology provided
            5. Identify specific shortcomings based on the rules provided
            6. Return ONLY valid JSON in the specified format - no additional text

            IMPORTANT: Use the analyze_contract_compliance tool with both contract_text and rules_context parameters.
            The rules_context contains the specific compliance rules to check against.
            """
            
            response = self.agent.invoke({"input": analysis_prompt})
            result = response.get("output", "{}")
            
            # Attempt to parse JSON response
            try:
                json_result = json.loads(result)
                
                # Ensure the result has the required structure
                if not isinstance(json_result, dict):
                    raise ValueError("Result is not a dictionary")
                
                # Add contract_type if missing
                if "document_type" not in json_result:
                    json_result["document_type"] = contract_type or "Unknown"
                
                # Ensure risk_score structure exists
                if "risk_score" not in json_result:
                    json_result["risk_score"] = {
                        "overall_score": 0,
                        "risk_level": "Unknown",
                        "breakdown": {
                            "compliance_rules_score": 0,
                            "validation_criteria_score": 0,
                            "common_violations_score": 0,
                            "regulatory_references_score": 0
                        }
                    }
                
                return json_result
                
            except (json.JSONDecodeError, ValueError) as e:
                # If JSON parsing fails, try to extract JSON from the response
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    try:
                        json_result = json.loads(json_match.group())
                        return json_result
                    except json.JSONDecodeError:
                        pass
                
                # Fallback: return error structure
                return {
                    "document_type": contract_type or "Unknown",
                    "parties_involved": [],
                    "risk_score": {
                        "overall_score": 50,
                        "risk_level": "Medium",
                        "breakdown": {
                            "compliance_rules_score": 0,
                            "validation_criteria_score": 0,
                            "common_violations_score": 0,
                            "regulatory_references_score": 0
                        }
                    },
                    "shortcomings": [{
                        "category": "SYSTEM_ERROR",
                        "issue": f"Failed to parse contract analysis: {str(e)}",
                        "severity": "High",
                        "points_deducted": 50
                    }],
                    "compliance_summary": {
                        "total_rules_checked": 0,
                        "rules_violated": 1,
                        "compliance_percentage": 0
                    }
                }
                
        except Exception as e:
            return {
                "document_type": contract_type or "Error",
                "parties_involved": [],
                "risk_score": {
                    "overall_score": 100,
                    "risk_level": "Critical",
                    "breakdown": {
                        "compliance_rules_score": 25,
                        "validation_criteria_score": 25,
                        "common_violations_score": 25,
                        "regulatory_references_score": 25
                    }
                },
                "shortcomings": [{
                    "category": "SYSTEM_ERROR",
                    "issue": f"Analysis failed: {str(e)}",
                    "severity": "Critical",
                    "points_deducted": 100
                }],
                "compliance_summary": {
                    "total_rules_checked": 0,
                    "rules_violated": 1,
                    "compliance_percentage": 0
                }
            }


        def _extract_contract_type(self, response_obj):
            """Extract contract type from LLM tool response"""
            text = response_obj.get("output", "")
            # Enhanced extraction logic
            contract_types = [
                "Employment Agreement", "Employment Contract", "Job Contract",
                "Non-Disclosure Agreement", "NDA", "Confidentiality Agreement",
                "Service Agreement", "Service Contract", "Professional Services Agreement",
                "Lease Agreement", "Rental Agreement", "Property Lease",
                "Purchase Agreement", "Sales Contract", "Buy-Sell Agreement"
            ]
            
            text_lower = text.lower()
            for contract_type in contract_types:
                if contract_type.lower() in text_lower:
                    return contract_type
            
            # Fallback to original logic
            for line in text.splitlines():
                if "contract type" in line.lower() or "this is likely a" in line.lower():
                    return line.split(":")[-1].strip().split(" ")[0]
            
            return "General Contract"

        def get_risk_level(self, score: int) -> str:
            """Convert numeric risk score to risk level"""
            if score >= 45:
                return "Critical"
            elif score >= 35:
                return "High"
            elif score >= 25:
                return "Medium"
            else:
                return "Low"
