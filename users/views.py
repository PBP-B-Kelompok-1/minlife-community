from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

def show_profile(request, user_id):
    # TODO
    return redirect("")
    
@login_required
def show_my_profile(request):
    # TODO
    return redirect("")

def login_user(request):
    # TODO
    return redirect("")

def register_user(request):
    # TODO
    return redirect("")