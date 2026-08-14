from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from .models import AccessRequest


class AccessRequestView(LoginRequiredMixin, View):
    """
    Mostra la pagina di richiesta accesso se l'utente è autenticato ma non approvato.
    Se l'utente ha già inviato una richiesta, mostra lo stato.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.can_access:
            return redirect("/")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        try:
            access_request = request.user.access_request
        except AccessRequest.DoesNotExist:
            access_request = None
        return render(request, "accounts/access_request.html", {"access_request": access_request})

    def post(self, request):
        try:
            access_request = request.user.access_request
            # Già inviata
            return render(request, "accounts/access_request.html", {"access_request": access_request})
        except AccessRequest.DoesNotExist:
            pass

        full_name = request.POST.get("full_name", "").strip()
        organization = request.POST.get("organization", "").strip()
        reason = request.POST.get("reason", "").strip()

        if not full_name or not reason:
            return render(request, "accounts/access_request.html", {
                "access_request": None,
                "error": "Nome e motivazione sono obbligatori.",
                "form_data": {"full_name": full_name, "organization": organization, "reason": reason},
            })

        AccessRequest.objects.create(
            user=request.user,
            full_name=full_name,
            organization=organization,
            reason=reason,
        )
        return redirect("access_request")
