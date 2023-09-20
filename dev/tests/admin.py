from django.contrib import admin
from django.contrib.admin import ModelAdmin

from .models import ScalableExample


@admin.register(ScalableExample)
class ScalableExampleAdmin(ModelAdmin):
    """Admin class"""
    list_display = ["name", "processing_timer", "acquired_by", "acquired_at"]
    ordering = ['name']
