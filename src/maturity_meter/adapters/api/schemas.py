"""Request and response schemas for the web API adapter.

Schemas define the public JSON contract for API routes. Keeping them separate
from route functions makes the API easier to document, test, and evolve.
"""

from pydantic import BaseModel


class ProcessRequest(BaseModel):
    """Request payload for processing text.

    Parameters
    ----------
    text : str
        Text to process.
    """

    text: str


class ProcessResponse(BaseModel):
    """Response payload for processed text.

    Parameters
    ----------
    input_text : str
        Text received by the service.
    output_text : str
        Processed text returned by the service.
    """

    input_text: str
    output_text: str
