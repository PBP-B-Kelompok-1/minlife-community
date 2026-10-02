from django.shortcuts import render

# Create your views here.
def frontpage(request):
    context = { "tes": "tes" }
    return render(request, "posts/frontpage.html", context)