from fastapi import APIRouter, Depends
from manager.adapter.inbound.api.schemas.email_schema import SendEmailRequest
from manager.app.ports.input.email_use_case import EmailUseCase
from manager.dependencies.email_provider import get_email_use_case

email_router = APIRouter(prefix="/email", tags=["email"])


@email_router.post("/faker-report")
async def send_faker_report(
    body: SendEmailRequest,
    use_case: EmailUseCase = Depends(get_email_use_case),
) -> dict:
    return await use_case.send_faker_report(to=body.to, name=body.name)
