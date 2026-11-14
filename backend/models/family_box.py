from backend.utils import streak
from pydantic import BaseModel, ConfigDict, Field

class CreateFamilyBoxBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    name: str = Field( 
                      ...,
                     min_length=2,
                     max_length=50,
                     description="Family box name",
                     )
    
    
class JoinFamilyyBoxBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    invite_code: str = Field(
        ...,
        min_length=4,
        max_length=12,
        description="Invite code to join the box"
    )
    
class LeaderboardMember(BaseModel):
    user_id: str
    name: str
    streak: int