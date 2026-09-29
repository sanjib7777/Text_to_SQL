from conversational_model.conversation import ConversationMessage


class ConversationMemory:

    def __init__(self, max_messages=3):

        self.max_messages = max_messages

        self.messages = {}
        self.ENABLE_CONTEXTUAL_QUESTION = False

    # =====================================================
    # Add message
    # =====================================================

    def add_message(
        self,
        session_id,
        role,
        content
    ):
        message = ConversationMessage(
            role=role,
            content=content
        )

        if session_id not in self.messages:

            self.messages[session_id] = []

        self.messages[session_id].append({
            "role": message.role,
            "content": message.content,
            "timestamp": message.timestamp,
        })

        # Keep only recent messages
        self.messages[session_id] = (
            self.messages[session_id]
            [-self.max_messages:]
        )

    # =====================================================
    # Get history
    # =====================================================

    def get_history(
        self,
        session_id
    ):

        return self.messages.get(
            session_id,
            []
        )


    def get_last_user_message(
        self,
        session_id
    ):
        if not self.ENABLE_CONTEXTUAL_QUESTION:
            return None

        history = self.messages.get(
            session_id,
            []
        )

        # Search from newest to oldest
        for message in reversed(history):

            if message.get("role") == "user":

                return message.get("content")

        # No user message found
        return None

    # =====================================================
    # Clear conversation
    # =====================================================

    def clear(
        self,
        session_id
    ):

        self.messages.pop(
            session_id,
            None
        )