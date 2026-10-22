from django import forms
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.utils.translation import gettext_lazy as _

from authentication.models import Facilitator, PlatformAccessToken


class FacilitatorForm(forms.ModelForm):
    class Meta:
        model = Facilitator
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].required = False
        self.fields['password'].widget.attrs['placeholder'] = _('Default value: ChangeItNow[code]')
        self.fields['code'].required = False


class FacilitatorAdmin(admin.ModelAdmin):
    form = FacilitatorForm
    readonly_fields = ('no_sql_user', 'no_sql_pass', 'no_sql_db_name')
    list_filter = [
        'active',
    ]

    search_fields = [
        'no_sql_user',
        'no_sql_db_name',
        'username',
        'code',
        'active',
    ]

    list_display = [
        'no_sql_user',
        'no_sql_db_name',
        'username',
        'code',
        'active',
        'user',
    ]


class LogEntryAdmin(admin.ModelAdmin):
    list_filter = [
        'content_type',
        'action_flag'
    ]

    search_fields = [
        'user__username',
        'object_repr',
        'change_message'
    ]

    list_display = [
        'action_time',
        'user',
        'content_type',
        'action_flag',
        'change_message'
    ]

    def queryset(self, request):
        return super().queryset(request).prefetch_related('content_type')



class PlatformAccessTokenAdmin(admin.ModelAdmin):
    """Sessions du mobile (jetons valables sur le DCC, le SIG et le MGP) : consultation et révocation. Le jeton lui-même
    n'est pas connu (seule son empreinte est rangée)."""
    list_display = ['username', 'email', 'account_kind', 'client', 'created_at', 'last_used_at', 'expires_at', 'revoked_at']
    list_filter = ['account_kind', 'client']
    search_fields = ['username', 'email']
    readonly_fields = [f.name for f in PlatformAccessToken._meta.fields if f.name != 'revoked_at']

    def has_add_permission(self, request):
        return False

admin.site.register(Facilitator, FacilitatorAdmin)
admin.site.register(LogEntry, LogEntryAdmin)
admin.site.register(PlatformAccessToken, PlatformAccessTokenAdmin)
