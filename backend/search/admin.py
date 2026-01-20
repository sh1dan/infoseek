"""
Admin configuration for search app.
"""
from django.contrib import admin
from .models import SearchTask, SearchResult


@admin.register(SearchTask)
class SearchTaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'keyword', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['keyword', 'id']
    readonly_fields = ['id', 'created_at']


@admin.register(SearchResult)
class SearchResultAdmin(admin.ModelAdmin):
    list_display = ['id', 'task', 'title', 'source_url', 'created_at']
    list_filter = ['created_at', 'task']
    search_fields = ['title', 'source_url', 'task__keyword']
    readonly_fields = ['created_at']

