# FastNet

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

- Subscription activation
- Subscription expiration
- Upcoming expiration
- Trial activation and expiration

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
```

## API

The main API is available under `/api/v1/`.

### Users

```text
POST /api/v1/users/register/
POST /api/v1/users/verify-email/
POST /api/v1/users/resend-code/
GET  /api/v1/users/me/

POST /api/v1/users/web/login/
POST /api/v1/users/web/verify/
POST /api/v1/users/web/refresh/

GET  /api/v1/users/ref-links/
GET  /api/v1/users/referrer-info/
```

### Subscriptions

```text
GET  /api/v1/subscriptions/
GET  /api/v1/subscriptions/plans/

POST /api/v1/subscriptions/{id}/renew/
POST /api/v1/subscriptions/{id}/regenerate/
```

### Payments

```text
POST /api/v1/payment/yookassa/create/
POST /api/v1/payment/yookassa/webhook/
```

## Authentication

The backend supports two authentication flows.

### Web application

The web client uses JWT access and refresh tokens.

```http
Authorization: Bearer <access_token>
```

### Telegram bot

Internal bot requests use a shared secret:

```http
X-Bot-Secret: <secret>
```

The backend can identify users by Telegram ID or email when requests come from
the trusted bot service.

## Local Setup

Clone the repository:

```bash
git clone https://github.com/MaximGit-tech/fastnet-backend.git
cd fastnet-backend
```

Create and activate a virtual environment:

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a PostgreSQL database and configure environment variables.

Example:

```env
SECRET_KEY=your-secret-key
DEBUG=True

DB_NAME=fastnet
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

BOT_SECRET=shared-secret
BOT_WEBHOOK_URL=http://localhost:8080/internal/notify/

EMAIL_FROM=noreply@example.com
RESEND_API_KEY=your-resend-api-key

TELEGRAM_BOT_USERNAME=your_bot
SITE_URL=http://localhost:3000

CELERY_BROKER_URL=redis://localhost:6379/0

YOOKASSA_SHOP_ID=your-shop-id
YOOKASSA_SECRET_KEY=your-secret-key
YOOKASSA_RETURN_URL_BOT=https://t.me/your_bot
YOOKASSA_RETURN_URL_WEB=http://localhost:3000/profile
```

VPN infrastructure credentials and server configuration are also supplied
through environment variables and are not stored in the repository.

Run migrations:

```bash
python manage.py migrate
```

Start the application:

```bash
python manage.py runserver
```

## Celery

Start a worker:

```bash
celery -A tgproxy worker -l info
```

Start Celery Beat for scheduled tasks:

```bash
celery -A tgproxy beat -l info
```

## Related Project

Telegram client for the service:

[fastnet-telegram-bot](https://github.com/MaximGit-tech/fastnet-telegram-bot)

## Author

**Maxim**

GitHub: [@MaximGit-tech](https://github.com/MaximGit-tech)
