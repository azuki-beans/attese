from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """
    Estende AbstractUser aggiungendo il flag access_approved.
    Gli utenti nuovi che accedono con Google vengono creati con access_approved=False.
    Lo staff e i superuser hanno sempre accesso.
    """
    access_approved = models.BooleanField(
        default=False,
        verbose_name="Accesso approvato",
        help_text="Se abilitato, l'utente può accedere alla dashboard.",
    )

    class Meta:
        verbose_name = "Utente"
        verbose_name_plural = "Utenti"

    @property
    def can_access(self):
        return self.is_staff or self.is_superuser or self.access_approved


class AccessRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "In attesa"),
        (STATUS_APPROVED, "Approvata"),
        (STATUS_REJECTED, "Rifiutata"),
    ]

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="access_request",
    )
    full_name = models.CharField(max_length=200, verbose_name="Nome e cognome")
    organization = models.CharField(max_length=200, blank=True, verbose_name="Ente / Organizzazione")
    reason = models.TextField(verbose_name="Motivazione richiesta")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_requests",
    )

    class Meta:
        verbose_name = "Richiesta di accesso"
        verbose_name_plural = "Richieste di accesso"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} – {self.get_status_display()}"
