from django.shortcuts import render
from django.http import HttpResponse

class OidcView():
    def login(request):
        return render(request, 'login.html')
