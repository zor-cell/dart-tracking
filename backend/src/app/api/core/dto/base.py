"""Shared base for wire schemas.

Serializes and parses with camelCase aliases so the JSON matches the Angular
client's DTOs, while the Python side keeps snake_case attributes.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
