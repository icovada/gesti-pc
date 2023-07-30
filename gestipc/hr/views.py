from django.shortcuts import render

from django.contrib.auth.models import User

# Create your views here.


def main(request):
    users = User.objects.all()
    return render(request, 'hr/main.html', {"curpage": "volontari",
                                            "users": users})


def detail_page(request, id):
    user = User.objects.get(id=id)

    return render(request, 'hr/profile.html', {"curpage": "volontari",
                                               "user": user})
