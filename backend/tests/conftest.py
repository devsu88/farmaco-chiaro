import os

# I test devono essere deterministici e non dipendere da Qdrant/OpenRouter.
os.environ["RETRIEVAL_MODE"] = "bm25"
