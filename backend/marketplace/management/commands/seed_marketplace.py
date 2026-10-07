import decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image

from marketplace.models import Client, Product, UserProfile


class Command(BaseCommand):
    help = "Seeds initial development data including an admin user and mock client stores"

    def handle(self, *args, **kwargs):
        admin_username = "admin"
        admin_email = "admin@example.com"
        admin_password = "adminpassword123"

        if not User.objects.filter(username=admin_username).exists():
            User.objects.create_superuser(admin_username, admin_email, admin_password)
            self.stdout.write(self.style.SUCCESS(f"Successfully created superuser: {admin_username}"))
        else:
            self.stdout.write(self.style.WARNING(f"Superuser {admin_username} already exists."))

        mock_data = {
            "Nike": [
                {"name": "Air Max Trainer", "price": "120.00", "status": Product.STATUS_APPROVED},
                {"name": "Running Shorts", "price": "45.00", "status": Product.STATUS_PENDING},
            ],
            "Apple": [
                {"name": "iPhone 15 Pro", "price": "999.00", "status": Product.STATUS_APPROVED},
                {"name": "MacBook Air M3", "price": "1099.00", "status": Product.STATUS_PENDING},
            ],
        }

        image_bytes = self._placeholder_png()

        for client_name, products in mock_data.items():
            client, _created = Client.objects.get_or_create(name=client_name)
            username = f"{client_name.lower()}_manager"
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(username=username, password="password123")
                UserProfile.objects.create(user=user, client=client)
                self.stdout.write(self.style.SUCCESS(f"Created client manager: {username}"))

            for prod_info in products:
                product_exists = Product.objects.filter(client=client, name=prod_info["name"]).exists()
                if product_exists:
                    continue
                new_product = Product(
                    client=client,
                    name=prod_info["name"],
                    price=decimal.Decimal(prod_info["price"]),
                    status=prod_info["status"],
                )
                filename = f"{client.slug}_{new_product.name.lower().replace(' ', '_')}.png"
                new_product.image.save(filename, ContentFile(image_bytes), save=True)
                self.stdout.write(
                    self.style.SUCCESS(f"Seeded product: {new_product.name} ({new_product.status})")
                )

        self.stdout.write(self.style.SUCCESS("Database seeding completed smoothly!"))

    def _placeholder_png(self):
        buffer = BytesIO()
        Image.new("RGB", (400, 300), color=(200, 200, 200)).save(buffer, format="PNG")
        return buffer.getvalue()
