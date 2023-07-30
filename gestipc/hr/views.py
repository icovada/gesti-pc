from django.shortcuts import render

from django.contrib.auth.models import User

# Create your views here.

def main(request):
    users = User.objects.all()
    return render(request, 'hr/main.html', {"users": users})
