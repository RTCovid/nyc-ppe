import re

from django.core.exceptions import ValidationError
from allauth.account.adapter import DefaultAccountAdapter


class ClosedAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False


class CharacterComplexityValidator:
    PATTERN = r"^(?=.*[A-Za-z].*)(?=.*[0-9{}\[\],.<>;:\'\"?\/|\\`~!@#$^&*()_\-+=].*).*$"

    def __init__(self, min_length=8):
        self.min_length = min_length

    def validate(self, password, user=None):
        if re.search(self.PATTERN, password) is None:
            raise ValidationError(
                "This password must contain at least one letter and one number or special character.",
                code="password_needs_special_characters",
            )

    def get_help_text(self):
        return "Your password must contain at least one letter and one number or special character ({}\[\],.<>;:'\"?/|\`~!@#$^&*()_\-+=)"
