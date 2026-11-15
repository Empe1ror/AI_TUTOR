try:
    from langchain_nvidia_ai_endpoints import ChatNVIDIA
except ImportError:
    from langchain.chat_models import ChatNVIDIA

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from prompts import prompt, RAG_INSTRUCTIONS
from dotenv import load_dotenv
import os


load_dotenv()

nvidia_api_key = os.getenv("NVIDIA_API_KEY")
nvidia_base_url = os.getenv("NVIDIA_BASE_URL")

client = ChatNVIDIA(
    model="nvidia/nemotron-3.5-lightning-30b-a3b",
    api_key=nvidia_api_key,
    base_url=nvidia_base_url,
    max_tokens=4096,
    temperature=0.6,
)

profile_client = ChatNVIDIA(
    model="nvidia/nemotron-3.5-lightning-30b-a3b",
    api_key=nvidia_api_key,
    base_url=nvidia_base_url,
    max_tokens=4096,
    temperature=0,
)


prompt_template = ChatPromptTemplate.from_messages([
    (
        "system", prompt + "{student_profile}" + RAG_INSTRUCTIONS
    ),

    # This is where previous messages will be inserted
    MessagesPlaceholder(variable_name="history"),

    # Current user message
    ("human", "{input}")
]).partial(context="No uploaded documents.")  # default keeps the CLI (app.py) working

chain = prompt_template | client | StrOutputParser()