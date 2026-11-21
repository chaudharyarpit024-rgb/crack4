
from pydantic import BaseModel, ConfigDict, Field

class CreateFamilyBoxBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    name: str = Field( 
                      ...,
                     min_length=2,
                     max_length=50,
                     description="Family box name",
                     )
    
    
class JoinFamilyBoxBody(BaseModel):
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
    calories_consumed: int
    daily_target: int
    target_percentage: int
    score: int
    rank: int
    is_me: bool = False
    