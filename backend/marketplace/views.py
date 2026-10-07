import decimal

from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import login, logout
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Client, Product, UserProfile

_INPUT_CLASS = (
    "mt-1 block w-full rounded-lg border border-stone-300 bg-white px-3 py-2 "
    "text-stone-900 shadow-sm focus:border-orange-700 focus:outline-none "
    "focus:ring-2 focus:ring-orange-700/30"
)


def _style_auth_form(form):
    for field in form.fields.values():
        css = _INPUT_CLASS
        if getattr(field.widget, "input_type", "") == "checkbox":
            css = "h-4 w-4 rounded border-stone-300 text-orange-700"
        field.widget.attrs["class"] = css
    return form


def _client_for_user(user):
    try:
        return user.profile.client
    except UserProfile.DoesNotExist:
        return None


def global_catalog(request):
    products = Product.objects.filter(status=Product.STATUS_APPROVED).select_related("client")
    return render(request, "catalog.html", {"products": products})


def client_catalog(request, client_slug):
    client = get_object_or_404(Client, slug=client_slug)
    products = Product.objects.filter(client=client, status=Product.STATUS_APPROVED)
    return render(request, "catalog.html", {"products": products, "client": client})


def client_register(request):
    if request.method == "POST":
        user_form = UserCreationForm(request.POST)
        company_name = (request.POST.get("company_name") or "").strip()
        if user_form.is_valid() and company_name:
            user = user_form.save()
            client, _created = Client.objects.get_or_create(name=company_name)
            UserProfile.objects.create(user=user, client=client)
            login(request, user)
            return redirect("dashboard")
    else:
        user_form = UserCreationForm()
    return render(request, "register.html", {"form": _style_auth_form(user_form)})


def client_login(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect("dashboard")
    else:
        form = AuthenticationForm()
    return render(request, "login.html", {"form": _style_auth_form(form)})


@require_POST
def client_logout(request):
    logout(request)
    return redirect("global_catalog")


@login_required
def client_dashboard(request):
    client = _client_for_user(request.user)
    if client is None:
        return redirect("global_catalog")
    products = Product.objects.filter(client=client)
    return render(request, "dashboard.html", {"products": products, "client": client})


@login_required
def product_upload(request):
    client = _client_for_user(request.user)
    if client is None:
        return redirect("global_catalog")

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        price_raw = request.POST.get("price")
        image = request.FILES.get("image")
        try:
            price = decimal.Decimal(price_raw)
        except (TypeError, decimal.InvalidOperation):
            price = None
        if name and price is not None and price >= 0 and image:
            Product.objects.create(
                client=client,
                name=name,
                price=price,
                image=image,
                status=Product.STATUS_PENDING,
            )
            return redirect("dashboard")
    return render(request, "upload_form.html")
