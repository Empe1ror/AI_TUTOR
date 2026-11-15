from llm import profile_client

r = profile_client.invoke("Write 10 multiple-choice questions about artificial intelligence as JSON, each with 4 options, the correct index, and an explanation.")
print("CONTENT:", repr(r.content[:300]))
print("EXTRA:", {k: str(v)[:200] for k, v in r.additional_kwargs.items()})
print("META:", r.response_metadata)