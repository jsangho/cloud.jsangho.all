from pydantic import BaseModel


class SendEmailRequest(BaseModel):
    to: str
    name: str = ""  # 수신자 이름 (텔레그램 보고용)
