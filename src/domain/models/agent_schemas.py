import datetime

from pydantic import BaseModel, Field


class RegisterAgentRequest(BaseModel):
    agent_external_id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    group_id: str


class AssignAgentToGroupRequest(BaseModel):
    agent_id: str


class AgentResponse(BaseModel):
    id: str
    agent_external_id: str
    name: str
    created_by: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    agents: list[AgentResponse]


class AgentGroupInfo(BaseModel):
    group_id: str
    group_name: str

    model_config = {"from_attributes": True}


class UserAgentResponse(BaseModel):
    id: str
    agent_external_id: str
    name: str
    created_by: str
    created_at: datetime.datetime
    groups: list[AgentGroupInfo]

    model_config = {"from_attributes": True}


class UserAgentListResponse(BaseModel):
    agents: list[UserAgentResponse]
