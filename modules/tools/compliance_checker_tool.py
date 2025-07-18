from langchain_core.tools import tool
from langchain.tools.retriever import create_retriever_tool
from modules.vector_store import get_compliance_rules

@tool
def check_compliance_rules(query: str) -> str:
    """
    Retrieve relevant compliance rules from the vector database according to the contract type.
    pass the contract type as a string to the tool.
    it will return the relevant compliance rules for the contract type.
    Use this to find specific compliance requirements and risk indicators.
    """
    try:
        docs = get_compliance_rules.invoke(query)

        # If docs is a string, just return it
        if isinstance(docs, str):
            return docs

        # If docs is a list, extract page_content
        results = []
        for i, doc in enumerate(docs, 1):
            # Defensive: handle both Document and string
            content = getattr(doc, "page_content", str(doc))
            results.append(f"Rule {i}: {content}")

        return "\n\n".join(results) if results else "No relevant compliance rules found"

    except Exception as e:
        return f"Error retrieving compliance rules: {str(e)}"

