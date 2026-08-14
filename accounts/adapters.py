from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.core.exceptions import PermissionDenied


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Accetta il login Google solo per utenti già esistenti con is_staff=True.
    Chiunque altro riceve un errore 403 — nessun nuovo account viene creato automaticamente.
    """

    def pre_social_login(self, request, sociallogin):
        email = sociallogin.account.extra_data.get("email", "").lower()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise PermissionDenied
        if not user.is_staff:
            raise PermissionDenied
