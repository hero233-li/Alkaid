from typing import Any

from django.db import transaction

from apps.workflow.System_menu.models import PortalPreference, ReleaseNote
from apps.workflow.System_menu.schemas import ReleaseNoteSubmission

HOME_SHORTCUTS_KEY = "home_shortcuts"
HIDDEN_MENUS_KEY = "hidden_menus"
AUTO_EXPANDED_MENUS_KEY = "auto_expanded_menus"
DEFAULT_AUTO_EXPANDED_MENU_KEYS = ["product-data", "automation", "system"]
PROTECTED_MENU_KEYS = {"home", "settings"}


def create_release_note(submission: ReleaseNoteSubmission) -> ReleaseNote:
    return ReleaseNote.objects.create(**submission.model_dump())


def update_release_note(note: ReleaseNote, submission: ReleaseNoteSubmission) -> ReleaseNote:
    note.version = submission.version
    note.content = submission.content
    note.save(update_fields=["version", "content", "updated_at"])
    return note


def delete_release_note(note: ReleaseNote) -> None:
    note.delete()


def serialize_release_note(note: ReleaseNote) -> dict[str, Any]:
    return {
        "id": note.id,
        "version": note.version,
        "content": note.content,
        "createdAt": note.created_at.isoformat(),
        "updatedAt": note.updated_at.isoformat(),
    }


def read_menu_keys(key: str) -> list[str]:
    value = PortalPreference.objects.filter(key=key).values_list("value", flat=True).first()
    if value is None and key == AUTO_EXPANDED_MENUS_KEY:
        return DEFAULT_AUTO_EXPANDED_MENU_KEYS.copy()
    return [item for item in value or [] if isinstance(item, str)]


@transaction.atomic
def save_menu_keys(key: str, menu_keys: list[str]) -> list[str]:
    if key == HIDDEN_MENUS_KEY:
        menu_keys = [item for item in menu_keys if item not in PROTECTED_MENU_KEYS]
    preference, _ = PortalPreference.objects.select_for_update().get_or_create(
        key=key,
        defaults={"value": menu_keys},
    )
    preference.value = menu_keys
    preference.save(update_fields=["value", "updated_at"])
    return menu_keys
