import datetime

from pydantic import BaseModel, Field

from src.domain.models.agent_schemas import AgentGroupInfo


class AdminAgentResponse(BaseModel):
    id: int
    agent_external_id: str
    name: str
    created_by: str
    created_at: datetime.datetime
    groups: list[AgentGroupInfo]

    model_config = {"from_attributes": True}


class AdminAgentListResponse(BaseModel):
    agents: list[AdminAgentResponse]


class AdminGroupResponse(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    member_count: int

    model_config = {"from_attributes": True}


class AdminGroupListResponse(BaseModel):
    groups: list[AdminGroupResponse]


class BulkUpdateAgentGroupsRequest(BaseModel):
    group_ids: list[int] = Field(..., min_length=1)


class BulkUpdateAgentGroupsResponse(BaseModel):
    agent: AdminAgentResponse
