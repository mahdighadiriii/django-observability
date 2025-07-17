# tests/urls.py
from django.http import HttpResponse
from django.urls import path


def test_view(request):
    return HttpResponse(status=200)


urlpatterns = [
    path("test/", test_view, name="test_view"),
]
