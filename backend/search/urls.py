"""
URL configuration for search app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SearchTaskViewSet

router = DefaultRouter()
router.register(r'tasks', SearchTaskViewSet, basename='searchtask')

urlpatterns = [
    path('', include(router.urls)),
]

