from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render
from django.db.models.fields import Field
from hr.models import PersonalEquipmentAssignmentDetail, PersonalEquipmentType

# Create your views here.


@login_required
def main(request):
    users = User.objects.all()
    return render(request, "hr/main.html", {"curpage": "volontari", "users": users})


@login_required
def detail_page(request, id):
    user = User.objects.get(id=id)
    userprofile = user.profile

    profile_fields = userprofile._meta.get_fields()
    exclude = ["fkuser", "address", "telegram_user", "profile_picture"]
    profile_dict = {
        x.verbose_name: getattr(userprofile, x.name)
        for x in profile_fields
        if x.name not in exclude and isinstance(x, Field)
    }

    all_equipment = PersonalEquipmentType.objects.order_by("kind").all()
    all_equipment_dict = {x.kind: False for x in all_equipment}
    assigned_equipment = PersonalEquipmentAssignmentDetail.objects.filter(fkuser=user)

    for x in assigned_equipment:
        all_equipment_dict[x.fkequipmentkind.kind] = True

    personal_equipment_sorted = [
        (x.kind, all_equipment_dict[x.kind]) for x in all_equipment
    ]

    all_certs = userprofile.trainingenrollment_set.filter(training_completed=True)

    return render(
        request,
        "hr/profile.html",
        {
            "curpage": "volontari",
            "user": user,
            "profile": profile_dict,
            "equipment": personal_equipment_sorted,
            "certifications": all_certs,
        },
    )
