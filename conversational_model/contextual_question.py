from llm.ollama_client import OllamaClient

class ContextualQuestionBuilder:

    def __init__(self):

        self.llm = OllamaClient()

    def build(
        self,
        question,
        history
    ):

        if not history:

            return question

        history_text = []

        for message in history:

            if message.get("role") != "user": 
                continue 
            content = message.get("content", "").strip() 
            if content: 
                history_text.append( f"USER: {content}" )

        # If there are no previous user messages 
        if not history_text: 
            return question

        conversation_history = "\n".join( history_text )

        prompt = f"""
Rewrite the latest user question into a
self-contained question using the conversation history.

Do not answer the question.

Do not generate SQL.

Preserve all important information such as:
company code, date range, item, customer,
department, filters, etc.

CONVERSATION HISTORY:

{conversation_history}

LATEST USER QUESTION:

{question}

Return ONLY the rewritten question.
"""
        print("prompt for contextual question is ", prompt)
        response = self.llm.chat_with_model(
            user_prompt=prompt
        ).strip()
        print("response for contextual question is ", response)

        # If the LLM returned a failure token or an obviously invalid
        # rewrite (e.g., "I don't know 2"), fall back to the original
        # question instead of propagating the failure token.
        if not response:
            return question

        lowered = response.strip().lower()

        if lowered.startswith("i don't know") or lowered.startswith('i do not know'):
            return question

        # Very short or nonsense rewrites are also ignored
        if len(response.strip()) < 3:
            return question

        return response