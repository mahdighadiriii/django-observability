# tests/urls.py
from django.urls import path
from django.http import HttpResponse

def test_view(request):
    return HttpResponse(status=200)

urlpatterns = [
    path('test/', test_view, name='test_view'),
]