from pydantic import EmailStr

from app.api.features.auth.dto.identity_confirmation import IdentityConfirmationDto


class EmailChangeDto(IdentityConfirmationDto):
    new_email: EmailStr
