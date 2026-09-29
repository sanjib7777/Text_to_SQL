from sentence_transformers import SentenceTransformer


class EmbeddingModel:

    def __init__(self,model_name: str = "BAAI/bge-m3"):

        print("Loading embedding model...")
        self.model = SentenceTransformer(model_name)
        print("Embedding model loaded.")

    def embed(self, text: str):

        embedding = self.model.encode(
            text,
            normalize_embeddings=True
        )
        

        return embedding.tolist()