# Matcher Service using FastAPI
# matcher_rest_api.py
import sys
from typing import Optional, List

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, model_validator

from ollama_matcher import process_request_with_chunking

# 1. Define Custom Exceptions for Clear Error Handling

class MatcherLogicError(Exception):
    """
    Custom exception for errors raised from the core matching logic in `ollama_matcher` script.
    Allows for distinction between the kinds of errors instead of a generic `Exception`.
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

# 2. Define Data Structures with Pydantic for Validation

class MatcherRequest(BaseModel):
    """
    Defines the structure and validation rules for an incoming match request.
    FastAPI will automatically reject any request that doesn't conform to this structure.
    """
    
    # Set up type-hinting
    cell_type_requested: Optional[str] = None
    cell_type_list: Optional[List[str]] = None
    species_requested: Optional[str] = None
    species_list: Optional[List[str]] = None
    binding_molecule_requested: Optional[str] = None
    binding_molecule_list: Optional[List[str]] = None

    # Custom Validation
    @model_validator(mode='after')
    def check_paired_fields(self) -> 'MatcherRequest':
        """
        Custom Validator 1: Ensures that if a '_requested' field is provided, 
        its corresponding '_list' is also provided.
        """
        if self.cell_type_requested is not None and not self.cell_type_list:
            raise ValueError("If 'cell_type_requested' is provided, 'cell_type_list' must also be provided and non-empty.")
        if self.species_requested is not None and not self.species_list:
            raise ValueError("If 'species_requested' is provided, 'species_list' must also be provided and non-empty.")
        if self.binding_molecule_requested is not None and not self.binding_molecule_list:
            raise ValueError("If 'binding_molecule_requested' is provided, 'binding_molecule_list' must also be provided and non-empty.")
        return self

    @model_validator(mode='after')
    def check_at_least_one_pair(self) -> 'MatcherRequest':
        """
        Custom Validator 2: Ensures the request is not empty and contains at least one
        valid pair of fields to match.
        """
        if not any([self.cell_type_requested, self.species_requested, self.binding_molecule_requested]):
            raise ValueError("Request must contain at least one category to match (e.g. 'cell_type_requested').")
        return self

class MatcherResponse(BaseModel):
    """
    Defines the structure of a successful response. 
    FastAPI uses this to serialize the output JSON.
    """
    matcher_version: str
    cell_type_actual: Optional[str] = None
    species_actual: Optional[str] = None
    binding_molecule_actual: Optional[str] = None

# Create the FastAPI Application

app = FastAPI(
    title="GAME Matcher API",
    description="A RESTful API for the GAME Matcher module, \
        which helps with automated task-alignment of biological terms using a local LLM.",
    version="2.0.0"
)

# 4. Define a Custom Exception Handler
# Safety net function -- If a `MatcherLogicError` occurs anywhere, don't just crash.
# Instead run this function to create a clean error response

@app.exception_handler(MatcherLogicError)
async def matcher_logic_exception_handler(request: Request, exc: MatcherLogicError):
    """
    Catches errors from the core matching logic and returns a structured 
    500 Internal Server Error response.
    """
    return JSONResponse(
        status_code=500,
        content={"error": "Matcher Server Internal Error", "detail": exc.message},
    )

# 5. Define the API Endpoint

@app.post("/match", response_model=MatcherResponse)
async def perform_match(request: MatcherRequest):
    """
    Receives a request, processes it using the locall LLM chunking logic,
    and returns the best match found for each category.
    """
    # FastAPI and Pydantic have already performed all initial validation.
    print(f"Received valid match request: {request.model_dump(exclude_unset=True)}")

    # Convert the Pydantic model back to a dictionary for the existing function.
    request_data = request.model_dump(exclude_unset=True)

    try:
        # Call the Matcher process function -- core logic
        response_data = process_request_with_chunking(request_data)
        
    except Exception as e:
        # If the core logic fails, raise our custom exception.
        # The handler above will catch this and return a clean JSON error.
        print(f"Error during call to matching logic: {e}")
        raise MatcherLogicError(message=f"An unexpected error occurred in the matching engine: {e}")

    print(f"Sending response: {response_data}")

    # Return the result. FastAPI automatically converts it to a JSON response.
    return MatcherResponse(**response_data)

# 6. Run the API Server

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Invalid argument(s): Requires <application_name> <host_ip> <port>")
        sys.exit(1)

    HOST = sys.argv[1]
    PORT = int(sys.argv[2])

    # Uvicorn is a high-performance server that runs the FastAPI application.
    # This single line replaces the entire `run_matcher` and `handle_client` functions.
    uvicorn.run("matcher_rest_api:app", host=HOST, port=PORT, reload=True)