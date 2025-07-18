# modules/tools/contract_analyzer_tool.py
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
import json
import os

class ComplianceAnalysis(BaseModel):
    """Structured output for contract compliance analysis"""
    document_type: str = Field(description="Type of contract being analyzed")
    parties_involved: list = Field(description="List of parties in the contract")
    compliant_items: list = Field(description="List of compliant requirements")
    missing_items: list = Field(description="List of missing requirements")
    risk_factors: list = Field(description="Identified risk factors")
    risk_score: float = Field(description="Risk score from 0-100")
    shortcomings: list = Field(description="Detailed shortcomings found")

@tool(args_schema=None)
def analyze_contract_compliance(contract_text: str = '', rules_context: str = '') -> str:
    """
    Analyze contract text against compliance rules and return structured analysis.

    Args:
        contract_text: The contract text to analyze
        rules_context: The compliance rules to check against

    Returns:
        JSON string with detailed compliance analysis
    """
    try:
        # Fix for markdown-wrapped JSON input
        if contract_text.startswith("```json") or contract_text.startswith("```"):
            contract_text = contract_text.strip("` ")
        if rules_context.startswith("```json") or rules_context.startswith("```"):
            rules_context = rules_context.strip("` ")

        # Parse embedded dict if necessary
        try:
            if isinstance(contract_text, str) and contract_text.strip().startswith("{") and 'contract_text' in contract_text:
                parsed = json.loads(contract_text)
                contract_text = parsed.get("contract_text", contract_text)
                rules_context = parsed.get("rules_context", rules_context)
        except Exception as unwrap_err:
            print(f"Error unwrapping contract_text: {unwrap_err}")
            print(f"Contract text: {contract_text}")
            print(f"Rules context: {rules_context}")

        # Initialize the LLM
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )

        # Create analysis prompt
        analysis_prompt = PromptTemplate(
            template="""
            You are a legal compliance expert. Analyze the contract against the provided rules.

            CONTRACT TEXT:
            {contract_text}

            COMPLIANCE RULES:
            {rules_context}

            ANALYSIS REQUIREMENTS:
            1. Extract parties involved (companies, individuals)
            2. Identify missing elements based on rules
            3. Calculate risk score using this methodology:
               - Each missing compliance rule = 10 points
               - Critical missing elements = 15 points each
               - Documentation deficiencies = 8 points each
            4. List specific shortcomings with categories

            Return ONLY a valid JSON object with this structure:
            {{
              "document_type": "Employment Agreement",
              "parties_involved": [
                {{"name": "Company Name", "role": "Employer", "type": "entity"}},
                {{"name": "Employee Name", "role": "Employee", "type": "individual"}}
              ],
              "risk_score": {{
                "overall_score": 65,
                "risk_level": "Medium",
                "breakdown": {{
                  "compliance_rules_score": 30,
                  "validation_criteria_score": 20,
                  "common_violations_score": 10,
                  "regulatory_references_score": 5
                }}
              }},
              "shortcomings": [
                {{
                  "category": "COMPLIANCE_RULES",
                  "issue": "Missing termination clause",
                  "severity": "High",
                  "points_deducted": 15
                }}
              ],
              "compliance_summary": {{
                "total_rules_checked": 10,
                "rules_violated": 3,
                "compliance_percentage": 70
              }}
            }}
            """,
            input_variables=["contract_text", "rules_context"]
        )

        # Execute the analysis
        chain = analysis_prompt | llm
        result = chain.invoke({
            "contract_text": contract_text[:2000],
            "rules_context": rules_context
        })

        # Clean the response
        response_text = result.content if hasattr(result, 'content') else str(result)

        # Extract JSON if wrapped in markdown
        if "```json" in response_text and "```" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()

        # Validate JSON
        try:
            json.loads(response_text)
            return response_text
        except json.JSONDecodeError:
            return json.dumps({
                "document_type": "Unknown",
                "parties_involved": [],
                "risk_score": {
                    "overall_score": 50,
                    "risk_level": "Medium",
                    "breakdown": {
                        "compliance_rules_score": 20,
                        "validation_criteria_score": 15,
                        "common_violations_score": 10,
                        "regulatory_references_score": 5
                    }
                },
                "shortcomings": [{
                    "category": "SYSTEM_ERROR",
                    "issue": "JSON parsing failed",
                    "severity": "Medium",
                    "points_deducted": 50
                }],
                "compliance_summary": {
                    "total_rules_checked": 1,
                    "rules_violated": 1,
                    "compliance_percentage": 0
                }
            })

    except Exception as e:
        return json.dumps({
            "document_type": "Error",
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
        })
