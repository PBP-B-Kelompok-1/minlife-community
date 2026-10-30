"""
URL configuration for minlife project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static

from users.views import login_user, register_user
from posts.views import frontpage
from announcements.views import firebase_messaging_service_worker
from .views import favicon

urlpatterns = [
    path('', frontpage, name="frontpage"),
    path(
        'firebase-messaging-sw.js',
        firebase_messaging_service_worker,
        name='firebase_messaging_service_worker',
    ),
    path("ckeditor5/", include('django_ckeditor_5.urls')),
    path("api/", include('minlife.urls_api')),
    path('admin/', admin.site.urls),
    path('user/', include("users.urls")),
    path('post/', include("posts.urls")),
    path('announcements/', include("announcements.urls")),
    path('journal/', include("journal.urls")),
    path('weeklychallenge/', include("weeklychallenge.urls")),
    path('login', login_user, name="login"),
    path('register', register_user, name="register"),
    path('favicon.ico', favicon, name="favicon"),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
