from django.contrib import admin

from .models import CollectAttachment, CollectForm, CollectFormAdmin, CollectSubmission


class CollectFormAdminInline(admin.TabularInline):
    model = CollectFormAdmin
    extra = 0
    raw_id_fields = ('user',)
    readonly_fields = ('added_at',)


@admin.register(CollectForm)
class CollectFormModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'status', 'version', 'access_scope', 'created_by', 'updated_at')
    list_filter = ('status', 'access_scope')
    search_fields = ('title', 'description')
    filter_horizontal = ('allowed_users', 'allowed_groups', 'allowed_facilitators')
    readonly_fields = ('uid', 'created_at', 'updated_at', 'published_at', 'closed_at')
    inlines = (CollectFormAdminInline,)


@admin.register(CollectSubmission)
class CollectSubmissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'form', 'status', 'editable', 'source', 'user', 'facilitator', 'updated_at')
    list_filter = ('status', 'editable', 'source', 'form')
    search_fields = ('title', 'uuid')
    raw_id_fields = ('user', 'facilitator', 'reopened_by')
    readonly_fields = ('uuid', 'created_at', 'updated_at')


@admin.register(CollectAttachment)
class CollectAttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'form', 'submission', 'mime_type', 'size', 'created_at')
    search_fields = ('name', 'submission_uuid')
    raw_id_fields = ('submission', 'user', 'facilitator')
