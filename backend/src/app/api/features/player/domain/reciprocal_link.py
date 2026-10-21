from enum import StrEnum


class ReciprocalLink(StrEnum):
    """What accepting an invitation can do for the inviter in the invitee's own
    address book: add a linked entry, link the unlinked one of that name, or nothing."""

    CREATE = "create"
    LINK = "link"
    NONE = "none"
