from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Certification

# Create your views here.


@login_required
def main(request):
    "Show home"
    all_certs = Certification.objects.all()
    return render(
        request,
        "certifications/main.html",
        {"curpage": "certifications", "certifications": all_certs},
    )


@login_required
def detail_page(request, id):
    "Show home"
    raise NotImplementedError
    # return render(
    #     request,
    #     "certifications/main.html",
    #     {"curpage": "certifications", "certifications": all_certs},
    # )
