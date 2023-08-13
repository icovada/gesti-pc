from django.shortcuts import render

from django.core.serializers import deserialize
from django.contrib.auth.models import User
from .models import TelegramLink
from hr.models import PersonalEquipmentAssignmentDetail, PersonalEquipmentType
from django.contrib.auth.decorators import login_required
from tg_bot.bot import bot
from tg_bot.processors import registration_complete

# Create your views here.


@login_required
def main(request):
    users = User.objects.all()
    return render(request, 'hr/main.html', {"curpage": "volontari",
                                            "users": users})


@login_required
def detail_page(request, id):
    user = User.objects.get(id=id)
    userprofile = user.profile

    profile_fields = userprofile._meta.get_fields()
    exclude = ['fkuser', 'address', 'telegram_user', 'profile_picture']
    profile_dict = {
        x.verbose_name: getattr(userprofile, x.name)
        for x in profile_fields if x.name not in exclude
    }

    all_equipment = PersonalEquipmentType.objects.order_by('kind').all()
    all_equipment_dict = {x.kind: False for x in all_equipment}
    assigned_equipment = PersonalEquipmentAssignmentDetail.objects.filter(
        fkuser=user)

    for x in assigned_equipment:
        all_equipment_dict[x.fkequipmentkind.kind] = True

    personal_equipment_sorted = [
        (x.kind, all_equipment_dict[x.kind]) for x in all_equipment]

    return render(request, 'hr/profile.html', {"curpage": "volontari",
                                               "user": user,
                                               "profile": profile_dict,
                                               "equipment": personal_equipment_sorted})


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
