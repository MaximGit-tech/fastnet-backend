Backend service for FastNet, a subscription-based VPN platform.

The service handles user registration, authentication, subscription lifecycle,
payments, referral logic, VPN configuration management and communication with
the Telegram bot.

## Tech Stack

- Python
- Django
- Django REST Framework
- PostgreSQL
- Celery
- django-celery-beat
- JWT authentication
- YooKassa API
- Resend API
- HTTP / REST API
- Paramiko / SSH
- Gunicorn

## Features

### User management

- Registration by email
- Email verification with one-time codes
- Telegram account linking
- JWT authentication for the web application
- Shared-secret authentication for the Telegram bot
- User blocking support
- Referral links for web and Telegram registrations

### Subscription management

- Multiple subscription plans
- Trial subscriptions
- Subscription activation and renewal
- Automatic expiration handling
- Subscription key regeneration
- Referral bonuses
- Notifications before subscription expiration

### Payments

Integration with YooKassa:

- Payment creation
- Payment status processing through webhooks
- Subscription activation after successful payment
- Support for both new subscriptions and renewals

### Background tasks

Celery is used for scheduled and background operations:

- Expiring subscription deactivation
- Upcoming expiration notifications
- Trial expiration notifications
- Synchronization of subscription state with the VPN infrastructure

### VPN infrastructure integration

The backend communicates with the VPN management panel and infrastructure to:

- Create VPN clients
- Renew existing clients
- Disable expired clients
- Generate subscription configurations
- Regenerate subscription links
- Store generated subscription files on a remote server through SSH/SFTP

### Telegram bot integration

The backend sends internal events to the Telegram bot, including:

- subscription activation
- subscription expiration
- upcoming expiration
- trial activation / expiration

Communication between services is protected using a shared secret.

## Project Structure

```text
fastnet-backend/
├── apps/
│   ├── users/          # registration, authentication, referrals
│   ├── subscriptions/  # plans and subscription lifecycle
│   ├── payments/       # YooKassa integration
│   ├── vpn/            # VPN infrastructure integration
│   ├── admin_panel/    # administrative functionality
│   └── utils/          # shared authentication and service utilities
├── tgproxy/
│   ├── settings.py
│   ├── urls.py
│   └── celery.py
├── manage.py
└── requirements.txt
