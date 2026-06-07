from pydantic import BaseModel


class LoginRequest(BaseModel):
    # str instead of EmailStr: .local / internal domains are valid for this tool
    email: str
    password: str


class LoginResponse(BaseModel):
    id: str
    email: str
    full_name: str
