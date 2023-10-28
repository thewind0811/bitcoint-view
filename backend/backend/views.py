from django.contrib.auth import get_user_model, login, logout
from django.http import HttpResponse


def login_view(request, username, **kwargs):
    user, _ = get_user_model().objects.get_or_create(username=username)
    login(request, user)
    return HttpResponse()

def logout_view(request):
    logout(request)
    return HttpResponse()
