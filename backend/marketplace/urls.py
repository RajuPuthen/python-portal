from django.urls import path

from . import views

urlpatterns = [
    path("", views.global_catalog, name="global_catalog"),
    path("store/<slug:client_slug>/", views.client_catalog, name="client_catalog"),
    path("portal/register/", views.client_register, name="register"),
    path("portal/login/", views.client_login, name="login"),
    path("portal/logout/", views.client_logout, name="logout"),
    path("portal/dashboard/", views.client_dashboard, name="dashboard"),
    path("portal/upload/", views.product_upload, name="product_upload"),
]
