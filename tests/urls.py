from django.urls import path
from django.http import HttpResponse

def test_view(request):
    return HttpResponse("Test view", status=200)

urlpatterns = [
    path('test/', test_view, name='test_view'),
]
