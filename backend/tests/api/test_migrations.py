from alembic import command

from tests.api.support import alembic_config


def test_migrations_match_the_models(client):
    command.check(alembic_config())
