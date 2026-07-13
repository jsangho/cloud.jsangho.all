from heyman.adapter.outbound.n8n_email_gateway import N8nEmailGateway
from heyman.app.ports.input.email_use_case import EmailUseCase
from heyman.app.use_cases.email_interactor import EmailInteractor


def get_email_use_case() -> EmailUseCase:
    return EmailInteractor(gateway=N8nEmailGateway())
