from django.shortcuts import render

# Create your views here.

def home(request):
    "Show home"
    return render(request, "core/style.html")
