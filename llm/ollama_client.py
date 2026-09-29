# import tiktoken
from ollama import Client
import time
from settings import OLLAMA_HOST, OLLAMA_MODEL

class OllamaClient:
    def __init__(self, model_name: str | None = None, host: str | None = None):
        self.model_name = model_name or OLLAMA_MODEL
        self.host = self._resolve_host(host)
        self.client = Client(host=self.host)
        # self.context_size = context_size

    def _resolve_host(self, host: str | None) -> str:
        configured_host = (host or OLLAMA_HOST).strip()

        if not configured_host:
            return "http://127.0.0.1:11434"

        if configured_host in {"0.0.0.0", "0.0.0.0:11434"}:
            return "http://127.0.0.1:11434"

        if configured_host.startswith("http://0.0.0.0") or configured_host.startswith("https://0.0.0.0"):
            return "http://127.0.0.1:11434"

        if configured_host.startswith("http://") or configured_host.startswith("https://"):
            return configured_host

        if configured_host.startswith("localhost"):
            return f"http://{configured_host}"

        return f"http://{configured_host}"

    def generate(self, user_prompt: str, system_prompt: str | None = None) -> str:
        print("model used ", self.model_name)
        # print("user prompt is ", user_prompt)
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": user_prompt})

        # enc = tiktoken.get_encoding("cl100k_base")

        # tokens = len(enc.encode(system_prompt + prompt))

        # print("total tokens in prompt",tokens)

        try:
            start = time.perf_counter()
            response = self.client.chat(
                model=self.model_name,
                messages=messages,
                options={"temperature": 0.1},
            )
            end = time.perf_counter()
            latency = end - start
            print("response generated successfully")
            print("Latency:", latency)
            print("Input tokens:", response.get("prompt_eval_count"))
            print("Output tokens:", response.get("eval_count"))
            return response["message"]["content"]
        except Exception as e:
            print(f"Error during chat with model: {e}")
            return (
                f"Ollama is not reachable at {self.host}. "
                "Please start the Ollama service or update OLLAMA_HOST to a reachable address."
            )

# if __name__== "__main__":
#     client = OllamaClient()
#     system_prompt = "You are a helpful assistant that provides clear and concise explanations."
#     prompt = "what is Linear Regression?"
#     response = client.chat_with_model(prompt, system_prompt)
#     print(response)
