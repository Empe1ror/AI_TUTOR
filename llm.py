try:
    from langchain_nvidia_ai_endpoints import ChatNVIDIA
except ImportError:
    from langchain.chat_models import ChatNVIDIA

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from prompts import prompt
from dotenv import load_dotenv
import os


load_dotenv()

nvidia_api_key = os.getenv("NVIDIA_API_KEY")
nvidia_base_url = os.getenv("NVIDIA_BASE_URL")

client = ChatNVIDIA(
    model="nvidia/nemotron-3.5-lightning-30b-a3b",
    api_key=nvidia_api_key,
    base_url=nvidia_base_url
)


prompt_template = ChatPromptTemplate.from_messages([
    (
        "system", prompt + "{student_profile}"
    ),

    # This is where previous messages will be inserted
    MessagesPlaceholder(variable_name="history"),

    # Current user message
    ("human", "{input}")
])

chain = prompt_template | client | StrOutputParser()