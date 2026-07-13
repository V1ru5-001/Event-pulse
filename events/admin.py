from django.contrib import admin

from .models import Event, EventMedia, Category


class EventMediaInline(admin.TabularInline):
    model = EventMedia
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "organiser", "status", "start_datetime")
    list_filter = ("status", "category")
    search_fields = ("title", "location_name")
    inlines = [EventMediaInline]


admin.site.register(Category)