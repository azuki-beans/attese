from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone

from .models import AccessRequest, CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "username", "first_name", "last_name", "access_approved", "is_staff")
    list_filter = ("access_approved", "is_staff", "is_superuser")
    fieldsets = UserAdmin.fieldsets + (
        ("Accesso dashboard", {"fields": ("access_approved",)}),
    )
    actions = ["approve_access", "revoke_access"]

    @admin.action(description="Approva accesso selezionati")
    def approve_access(self, request, queryset):
        updated = queryset.update(access_approved=True)
        # Aggiorna anche le richieste associate
        AccessRequest.objects.filter(user__in=queryset, status=AccessRequest.STATUS_PENDING).update(
            status=AccessRequest.STATUS_APPROVED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f"{updated} utenti approvati.")

    @admin.action(description="Revoca accesso selezionati")
    def revoke_access(self, request, queryset):
        updated = queryset.update(access_approved=False)
        self.message_user(request, f"{updated} utenti revocati.")


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name", "organization", "status", "created_at", "reviewed_at")
    list_filter = ("status",)
    readonly_fields = ("user", "full_name", "organization", "reason", "created_at")
    actions = ["approve_requests", "reject_requests"]

    @admin.action(description="Approva richieste selezionate")
    def approve_requests(self, request, queryset):
        for ar in queryset.filter(status=AccessRequest.STATUS_PENDING):
            ar.status = AccessRequest.STATUS_APPROVED
            ar.reviewed_at = timezone.now()
            ar.reviewed_by = request.user
            ar.save()
            ar.user.access_approved = True
            ar.user.save(update_fields=["access_approved"])
        self.message_user(request, "Richieste approvate.")

    @admin.action(description="Rifiuta richieste selezionate")
    def reject_requests(self, request, queryset):
        queryset.filter(status=AccessRequest.STATUS_PENDING).update(
            status=AccessRequest.STATUS_REJECTED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, "Richieste rifiutate.")
