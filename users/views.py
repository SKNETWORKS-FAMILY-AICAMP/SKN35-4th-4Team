from django.shortcuts import render

# Create your views here.

def main(request):
    return render(request, "users/test.html")

def login(request):
    pass

def logout(request):
    pass

def signin(request):
    pass
