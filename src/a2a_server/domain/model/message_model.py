import json
from pydantic import BaseModel, Field
from typing import Any, Optional, List, Literal, Union
from uuid import uuid4
from datetime import datetime, timezone

#---------------------
# Base model
# --------------------
class A2AEnvelope(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    source_agent: str
    target_agent: str
    message_type: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: Any

class A2ATextPart(BaseModel):
    kind: Literal["text"] = "text"
    text: str

class A2ADataPart(BaseModel):
    kind: Literal["data", "json"]
    data: dict[str, Any]
    
class A2AMessage(BaseModel):
    kind: str = "message"
    messageId: str = Field(default_factory=lambda: str(uuid4()))
    role: Literal["user", "agent"]  # "user" for requests, "agent" for responses
    parts: List[Union[A2ATextPart, A2ADataPart]]

    def extract_envelope_data(self) -> dict:
        part = self.parts[0]
        if isinstance(part, A2ATextPart):
            return json.loads(part.text)
        elif isinstance(part, A2ADataPart):
            return part.data
        raise ValueError("Unsupported A2A message part kind")

#---------------------
# Request model
# --------------------    
class A2AConfiguration(BaseModel):
    acceptedOutputModes: Optional[List[str]] = Field(default_factory=list)
    blocking: bool = True
        
class A2AMessageParams(BaseModel):
    configuration: Optional[A2AConfiguration] = None
    message: A2AMessage
        
class A2ARequest(BaseModel):
    id: str
    jsonrpc: str = "2.0"
    method: str = "message/send"
    params: A2AMessageParams

    def parse_domain_envelope(self) -> A2AEnvelope:
        """Helper to extract your domain A2AEnvelope handling both text and data parts."""
        # 1. Use the method you wrote inside A2AMessage
        envelope_dict = self.params.message.extract_envelope_data()
        
        # 2. Validate dictionary into A2AEnvelope
        return A2AEnvelope.model_validate(envelope_dict)
    
#---------------------
# Response model
# --------------------

class A2ATaskResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    taskId: str = Field(default_factory=lambda: str(uuid4()))
    status: str = "completed"
    message: A2AMessage
    
class A2AResponseResult(BaseModel):
    task: A2ATaskResult

class A2AResponse(BaseModel):
    id: str  # Must match the incoming request's ID
    jsonrpc: str = "2.0"
    result: A2AMessage

    @classmethod
    def create(cls, domain_envelope: Union[A2AEnvelope, BaseModel, dict, str], a2aRequest: A2ARequest) -> "A2AResponse":    
        if isinstance(domain_envelope, BaseModel):
            envelope_dict = domain_envelope.model_dump()
        elif isinstance(domain_envelope, str):
            try:
                envelope_dict = json.loads(domain_envelope)
            except json.JSONDecodeError:
                envelope_dict = {"message": domain_envelope}
        elif isinstance(domain_envelope, dict):
            envelope_dict = domain_envelope
        else:
            raise TypeError(f"Unsupported domain_envelope type: {type(domain_envelope)}")

        # decode any nested JSON-string values (e.g. data='{"VERSION": "0.1", ...}')
        for key, value in envelope_dict.items():
            if isinstance(value, str):
                try:
                    envelope_dict[key] = json.loads(value)
                except json.JSONDecodeError:
                    pass

        incoming_part = a2aRequest.params.message.parts[0]
        # If client sent A2ADataPart, respond with A2ADataPart
        if isinstance(incoming_part, A2ADataPart):
            part = A2ADataPart(
                kind="data", 
                data=envelope_dict
            )
        else:
            part = A2ATextPart(
                kind="text", 
                text=json.dumps(envelope_dict, default=str)
            )

        return cls(
            id=a2aRequest.id,
            result=A2AMessage(
                role="agent",
                parts=[part]
            )
        )