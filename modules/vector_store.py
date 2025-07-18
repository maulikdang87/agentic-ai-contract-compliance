import sqlite3
import sys
import os
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.tools.retriever import create_retriever_tool
import nest_asyncio
nest_asyncio.apply()

# SQLite workaround
try:
    import sqlite3
except ImportError:
    import pysqlite3
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

load_dotenv()


loader = TextLoader("./sample_data/rules.txt")
docs = loader.load()

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1024,
    chunk_overlap=256
)

splits = text_splitter.split_documents(docs)



product_store = Chroma.from_documents(
    documents=splits,
    embedding=GoogleGenerativeAIEmbeddings(model="models/embedding-001"),   
    persist_directory="./chroma_product_db",
)

get_compliance_rules = create_retriever_tool(
    product_store.as_retriever(search_kwargs={"k": 2}),
    name="get_compliance_rules",
    description="Retrieve relevant compliance rules from the vector database according to the contract text"
)



# results = get_compliance_rules.invoke("Retrieve relevant compliance rules for employment agreement")



