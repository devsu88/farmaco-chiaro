import os

import pytest

# I test devono essere deterministici e non dipendere da Qdrant/OpenRouter.
os.environ["RETRIEVAL_MODE"] = "bm25"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Il limiter è globale: ogni test parte da una finestra vuota."""
    from app.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()
