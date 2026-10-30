from django.contrib import admin

from .models import JournalEntry


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "visibility", "updated_at")
    list_filter = ("visibility", "date")
    search_fields = ("user__username", "content")
    date_hierarchy = "date"
