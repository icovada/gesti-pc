from django.shortcuts import render

from django.contrib.auth.models import User
from .models import TelegramLink
from core.models import Profile
from django.contrib.auth.decorators import login_required
from pcroncellobot.bot import bot
from pcroncellobot.processors import registration_complete

# Create your views here.

@login_required
def main(request):
    users = User.objects.all()
    return render(request, 'hr/main.html', {"curpage": "volontari",
                                            "users": users})


@login_required
def detail_page(request, id):
    user = User.objects.get(id=id)

    return render(request, 'hr/profile.html', {"curpage": "volontari",
                                               "user": user})

@login_required
def link_tg(request, uuid):
    try:
        tg_link = TelegramLink.objects.get(security_code=uuid)
    except TelegramLink.DoesNotExist:
        return render(request, 'hr/tg_link_invalid.html')

    profile = request.user.profile

    profile.telegram_user = tg_link.telegram_user
    profile.save()

    tg_link.delete()

    registration_complete(bot, request.user)

    return render(request, 'hr/tg_link_success.html')