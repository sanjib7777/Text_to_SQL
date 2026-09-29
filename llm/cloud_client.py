from openai import OpenAI
import time
from settings import (
    NARAROUTER_API_KEY,
    NARAROUTER_BASE_URL,
    XKIRO_API_KEY,
    XKIRO_BASE_URL,
)

class CloudLLM:

    def __init__(self, model_name: str = None, platform: str = "naraRouter"):

        if platform == "naraRouter":
            base_url = NARAROUTER_BASE_URL
            api_key = NARAROUTER_API_KEY
            if not api_key:
                raise ValueError("NARAROUTER_API_KEY must be set when using the naraRouter platform")
        elif platform == "xkiro":
            base_url = XKIRO_BASE_URL
            api_key = XKIRO_API_KEY
            if not api_key:
                raise ValueError("XKIRO_API_KEY must be set when using the xkiro platform")
        else:
            raise ValueError("platform must be either 'naraRouter' or 'xkiro'")

        self.model_name = model_name
        self.platform = platform
        self.last_usage = None

        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )

    def generate(
        self,
        user_prompt: str,
        system_prompt: str
    ):
        print("Model used is: ", self.model_name)

        # start = time.perf_counter()

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            temperature=0.1
        )

        # self.last_usage = response.usage

        # end = time.perf_counter()

        # latency = end - start

        # print("Latency:", latency)

        return response.choices[0].message.content