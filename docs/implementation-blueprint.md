# Implementation blueprint

This file is a **build specification**, not day-to-day project documentation. For how the product works and how to run it, see [README.md](../README.md).

The snippets below are the intended Django + Docker layout. Application code is not checked into the repo yet; use this spec when scaffolding.

This specification details a multi-tenant marketplace using **Django (Python)** with its built-in server-side rendering (HTML templates) and a **PostgreSQL** database, orchestrated completely inside **Docker**. It includes an automated seeder that provisions default superadmin profiles and mock stores directly on launch.

---

## 1. Project Directory Structure
Generate the workspace layout exactly as configured below:
```text
my-marketplace/
├── docker-compose.yml
├── README.md
├── media/
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── entrypoint.sh
    ├── manage.py
    ├── core/
    │   ├── __init__.py
    │   ├── settings.py
    │   ├── urls.py
    │   └── wsgi.py
    ├── marketplace/
    │   ├── __init__.py
    │   ├── admin.py
    │   ├── apps.py
    │   ├── models.py
    │   ├── urls.py
    │   ├── views.py
    │   └── management/
    │       ├── __init__.py
    │       └── commands/
    │           ├── __init__.py
    │           └── seed_marketplace.py
    └── templates/
        ├── base.html
        ├── catalog.html
        ├── dashboard.html
        ├── login.html
        ├── register.html
        └── upload_form.html
```

---

## 2. Docker Infrastructure Scaffolding

### `backend/requirements.txt`
```text
Django>=5.0,<6.0
psycopg2-binary>=2.9
Pillow>=10.0
```

### `backend/Dockerfile`
```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends     build-essential     libpq-dev     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

COPY . /app/

ENTRYPOINT ["/app/entrypoint.sh"]
```

### `backend/entrypoint.sh`
```bash
#!/bin/sh
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Seeding development data (Superadmin & Mock Clients)..."
python manage.py seed_marketplace

echo "Starting development server..."
python manage.py runserver 0.0.0.0:8000
```

### `docker-compose.yml`
```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data/
    environment:
      - POSTGRES_DB=marketplace_db
      - POSTGRES_USER=postgres_user
      - POSTGRES_PASSWORD=securepassword123
    ports:
      - "5432:5432"

  web:
    build: ./backend
    command: /app/entrypoint.sh
    volumes:
      - ./backend:/app
      - ./media:/app/media
    ports:
      - "8000:8000"
    environment:
      - POSTGRES_DB=marketplace_db
      - POSTGRES_USER=postgres_user
      - POSTGRES_PASSWORD=securepassword123
      - DB_HOST=db
    depends_on:
      - db

volumes:
  postgres_data:
```

---

## 3. Core Django Settings & Routing

### `backend/core/settings.py` (Appended Configurations)
Ensure `'marketplace'` is added to `INSTALLED_APPS`, and append these configurations to the bottom of the file:
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'marketplace_db'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres_user'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'securepassword123'),
        'HOST': os.environ.get('DB_HOST', 'db'),
        'PORT': '5432',
    }
}

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
```

### `backend/core/urls.py`
```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('marketplace.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

## 4. Application Implementation (`marketplace/`)

### `backend/marketplace/models.py`
```python
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify

class Client(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.client.name if self.client else 'Global Admin'}"

class Product(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')

    def __str__(self):
        return f"{self.name} ({self.status}) - {self.client.name}"
```

### `backend/marketplace/admin.py`
```python
from django.contrib import admin
from .models import Client, UserProfile, Product

@admin.action(description="Approve selected products for public storefront")
def approve_products(modeladmin, request, queryset):
    queryset.update(status='APPROVED')

@admin.action(description="Reject selected products")
def reject_products(modeladmin, request, queryset):
    queryset.update(status='REJECTED')

class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'price', 'status']
    list_filter = ['status', 'client']
    search_fields = ['name', 'client__name']
    actions = [approve_products, reject_products]

admin.site.register(Client)
admin.site.register(UserProfile)
admin.site.register(Product, ProductAdmin)
```

### `backend/marketplace/urls.py`
```python
from django.urls import path
from . import views

urlpatterns = [
    path('', views.global_catalog, name='global_catalog'),
    path('store/<slug:client_slug>/', views.client_catalog, name='client_catalog'),
    path('portal/register/', views.client_register, name='register'),
    path('portal/login/', views.client_login, name='login'),
    path('portal/logout/', views.client_logout, name='logout'),
    path('portal/dashboard/', views.client_dashboard, name='dashboard'),
    path('portal/upload/', views.product_upload, name='product_upload'),
]
```

### `backend/marketplace/views.py`
```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.decorators import login_required
from .models import Product, Client, UserProfile

def global_catalog(request):
    products = Product.objects.filter(status='APPROVED')
    return render(request, 'catalog.html', {'products': products})

def client_catalog(request, client_slug):
    client = get_object_or_404(Client, slug=client_slug)
    products = Product.objects.filter(client=client, status='APPROVED')
    return render(request, 'catalog.html', {'products': products, 'client': client})

def client_register(request):
    if request.method == 'POST':
        user_form = UserCreationForm(request.POST)
        company_name = request.POST.get('company_name')
        if user_form.is_valid() and company_name:
            user = user_form.save()
            client, created = Client.objects.get_or_create(name=company_name)
            UserProfile.objects.create(user=user, client=client)
            login(request, user)
            return redirect('dashboard')
    else:
        user_form = UserCreationForm()
    return render(request, 'register.html', {'form': user_form})

def client_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def client_logout(request):
    logout(request)
    return redirect('global_catalog')

@login_required
def client_dashboard(request):
    try:
        client = request.user.profile.client
        products = Product.objects.filter(client=client)
    except UserProfile.DoesNotExist:
        return redirect('global_catalog')
    return render(request, 'dashboard.html', {'products': products, 'client': client})

@login_required
def product_upload(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        price = request.POST.get('price')
        image = request.FILES.get('image')
        if name and price and image:
            Product.objects.create(
                client=request.user.profile.client,
                name=name,
                price=price,
                image=image,
                status='PENDING'
            )
            return redirect('dashboard')
    return render(request, 'upload_form.html')
```

### `backend/marketplace/management/commands/seed_marketplace.py`
```python
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from marketplace.models import Client, UserProfile, Product
import decimal

class Command(BaseCommand):
    help = 'Seeds initial development data including an admin user and mock client stores'

    def handle(self, *args, **kwargs):
        admin_username = 'admin'
        admin_email = 'admin@example.com'
        admin_password = 'adminpassword123'

        if not User.objects.filter(username=admin_username).exists():
            User.objects.create_superuser(admin_username, admin_email, admin_password)
            self.stdout.write(self.style.SUCCESS(f"Successfully created superuser: {admin_username}"))
        else:
            self.stdout.write(self.style.WARNING(f"Superuser {admin_username} already exists."))

        mock_data = {
            'Nike': [
                {'name': 'Air Max Trainer', 'price': '120.00', 'status': 'APPROVED'},
                {'name': 'Running Shorts', 'price': '45.00', 'status': 'PENDING'}
            ],
            'Apple': [
                {'name': 'iPhone 15 Pro', 'price': '999.00', 'status': 'APPROVED'},
                {'name': 'MacBook Air M3', 'price': '1099.00', 'status': 'PENDING'}
            ]
        }

        dummy_pixel_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00 \x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'

        for client_name, products in mock_data.items():
            client, created = Client.objects.get_or_create(name=client_name)
            
            username = f"{client_name.lower()}_manager"
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(username=username, password='password123')
                UserProfile.objects.create(user=user, client=client)
                self.stdout.write(self.style.SUCCESS(f"Created client manager: {username}"))

            for prod_info in products:
                product_exists = Product.objects.filter(client=client, name=prod_info['name']).exists()
                if not product_exists:
                    new_product = Product(
                        client=client,
                        name=prod_info['name'],
                        price=decimal.Decimal(prod_info['price']),
                        status=prod_info['status']
                    )
                    new_product.image.save(
                        f"{client.slug}_{new_product.name.lower().replace(' ', '_')}.png",
                        ContentFile(dummy_pixel_data),
                        save=True
                    )
                    self.stdout.write(self.style.SUCCESS(f"Seeded product: {new_product.name} ({new_product.status})"))

        self.stdout.write(self.style.SUCCESS("Database seeding completed smoothly!"))
```

---

## 5. Front-End Templates UI (`templates/`)

### `backend/templates/base.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Tenant Marketplace</title>
    <style>
        body { font-family: sans-serif; margin: 0; padding: 20px; background: #f9f9f9; }
        nav { background: #333; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        nav a { color: white; margin-right: 15px; text-decoration: none; font-weight: bold; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 20px; }
        .card { background: white; padding: 15px; border: 1px solid #ddd; border-radius: 5px; text-align: center; }
        .card img { max-width: 100%; height: 150px; object-fit: cover; }
        .badge { display: inline-block; padding: 5px 10px; border-radius: 3px; font-size: 12px; color: white; font-weight: bold; }
        .PENDING { background: #e67e22; } .APPROVED { background: #2ecc71; } .REJECTED { background: #e74c3c; }
        form { background: white; padding: 20px; max-width: 400px; border-radius: 5px; border: 1px solid #ddd; }
        input, button { width: 100%; padding: 10px; margin: 10px 0; box-sizing: border-box; }
        button { background: #007bff; color: white; border: none; cursor: pointer; font-weight: bold; }
    </style>
</head>
<body>
    <nav>
        <a href="{% url 'global_catalog' %}">Public Storefront</a>
        {% if user.is_authenticated %}
            <a href="{% url 'dashboard' %}">My Dashboard</a>
            <a href="{% url 'logout' %}">Logout ({{ user.username }})</a>
        {% else %}
            <a href="{% url 'login' %}">Client Login</a>
            <a href="{% url 'register' %}">Register Company</a>
        {% endif %}
    </nav>
    {% block content %}{% endblock %}
</body>
</html>
```

### `backend/templates/catalog.html`
```html
{% extends 'base.html' %}
{% block content %}
    <h1>{% if client %}{{ client.name }} Storefront{% else %}All Featured Products{% endif %}</h1>
    <div class="grid">
        {% for product in products %}
            <div class="card">
                <img src="{{ product.image.url }}" alt="{{ product.name }}">
                <h3>{{ product.name }}</h3>
                <p>${{ product.price }}</p>
                <small>Sold by: <a href="{% url 'client_catalog' product.client.slug %}">{{ product.client.name }}</a></small>
            </div>
        {% empty %}
            <p>No products are currently available.</p>
        {% endfor %}
    </div>
{% endblock %}
```

### `backend/templates/dashboard.html`
```html
{% extends 'base.html' %}
{% block content %}
    <h1>{{ client.name }} Dashboard</h1>
    <p><a href="{% url 'product_upload' %}"><button style="width: auto;">+ Upload New Product</button></a></p>
    <h2>Managed Products Inventory</h2>
    <div class="grid">
        {% for product in products %}
            <div class="card">
                <img src="{{ product.image.url }}" alt="{{ product.name }}">
                <h3>{{ product.name }}</h3>
                <p>${{ product.price }}</p>
                <span class="badge {{ product.status }}">{{ product.status }}</span>
            </div>
        {% empty %}
            <p>You haven't uploaded any products yet.</p>
        {% endfor %}
    </div>
{% endblock %}
```

### `backend/templates/register.html`
```html
{% extends 'base.html' %}
{% block content %}
    <h2>Register a New Client Profile</h2>
    <form method="POST">
        {% csrf_token %}
        <label>Company Name:</label>
        <input type="text" name="company_name" required placeholder="e.g. Acme Corp">
        {{ form.as_p }}
        <button type="submit">Create Account & Storefront</button>
    </form>
{% endblock %}
```

### `backend/templates/login.html`
```html
{% extends 'base.html' %}
{% block content %}
    <h2>Client Portal Login</h2>
    <form method="POST">
        {% csrf_token %}
        {{ form.as_p }}
        <button type="submit">Login</button>
    </form>
{% endblock %}
```

### `backend/templates/upload_form.html`
```html
{% extends 'base.html' %}
{% block content %}
    <h2>Upload New Product</h2>
    <form method="POST" enctype="multipart/form-data">
        {% csrf_token %}
        <label>Product Name</label>
        <input type="text" name="name" required>
        <label>Price ($)</label>
        <input type="number" step="0.01" name="price" required>
        <label>Product Image</label>
        <input type="file" name="image" accept="image/*" required>
        <button type="submit">Submit for Verification</button>
    </form>
{% endblock %}
```

---

## 6. Setup & Execution Instructions

1. **Start Environment Layers:** Run the build command to spin up the infrastructure container layers:
   ```bash
   docker-compose up --build
   ```
2. **Review Default Mock Credentials:** Once execution finishes, you can access the environment immediately using these auto-seeded mock system profiles:

| Interface Context | Destination Target | Username Credentials | Password Auth |
| :--- | :--- | :--- | :--- |
| **Global Admin Panel** | `http://localhost:8000/admin/` | `admin` | `adminpassword123` |
| **Nike Store Workspace** | `http://localhost:8000/portal/login/` | `nike_manager` | `password123` |
| **Apple Store Workspace** | `http://localhost:8000/portal/login/` | `apple_manager` | `password123` |
