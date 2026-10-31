# Digicow

A Django system supporting farmer training, follow-up, community accounts and farm product orders across Kenya. The public website uses a white and yellow theme.

## What it does

| Part | Who uses it | What happens |
|---|---|---|
| **Public website** | Farmers and visitors | Home, About, Products, upcoming trainings, contact form, and farmer account sign-up/sign-in |
| **Training** | Coordinator, trainers | Coordinators set topics and schedule sessions. Trainers deliver sessions, register attendees and upload a group photo. |
| **QA review and calls** | Q&A agents | Completed trainings are grouped by trainer for review. Agents can approve or reject individual trainees or the whole group with a reason, then call farmers to confirm attendance and collect feedback. |
| **Orders** | Trainers, coordinator | Trainers record product orders. The coordinator approves and marks orders delivered. |
| **Reports** | Coordinator | Attendance confirmation per session, reach by county, orders by brand, plus CSV downloads. |

### Roles

* **Administrator**: everything, plus the Django admin at `/admin/`.
* **Training coordinator**: topics, sessions, farmers, orders, Q&A history, reports and staff accounts.
* **Trainer**: own sessions, attendance registration and group-photo uploads, farmers, own orders.
* **Q&A agent**: trainer training reviews, group photos, trainee decisions, call queue, call history and farmers.
* **Farmer**: own farmer account and training history, plus upcoming sessions.

## Run it on your computer (VS Code)

Open the `digicow` folder in VS Code, open the terminal (**Terminal > New Terminal**) and run:

```bash
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt

python manage.py makemigrations accounts core training qa shop
python manage.py migrate
python manage.py seed_reference_data
python manage.py createsuperuser
python manage.py runserver
```

Then open http://127.0.0.1:8000/ and sign in. Staff accounts are created by a coordinator; farmers can sign up from the public website.

If VS Code asks which Python interpreter to use, choose the one inside `.venv`.

### Run the tests

```bash
python manage.py test
```

## Setting it up for real use

1. Sign in at `/admin/` with your superuser account.
2. **Brands**: edit Juanco, CKL, Greenlife and Asili and add descriptions.
3. **Products**: add each real product with its brand, pack size and price in KES.
4. As coordinator, add staff at **Staff > Add staff member**, then add topics and schedule sessions.
5. Trainers can add attendance and a group photo from each session's attendance page. QA reviews completed trainings.
6. If a farmer's phone is already on an older training record, verify their identity before linking the farmer profile to their account in Django admin.
7. Farmers with a linked account can review completed trainings they attended. Reviews stay private until an administrator publishes them from **Farmer reviews** in Django admin.

`seed_reference_data` creates county and brand reference records only. It does not create sample users, products, farmers or training sessions.

## Project layout

```
digicow/       settings, root URLs
accounts/      staff and farmer accounts, authentication, role permissions
core/          public pages, dashboards, reports and CSV exports, contact form
training/      counties, topics, sessions, farmers, attendance and group photos
qa/            training reviews, confirmation calls and the call queue
shop/          brands, products, orders and order items
templates/     all HTML      static/   CSS and JS
```

## Going live

* Set environment variables: `DJANGO_SECRET_KEY` (a long random value), `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS=yourdomain.com`, and `DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain.com`.
* Use PostgreSQL instead of SQLite (change `DATABASES` in `digicow/settings.py`).
* Run `python manage.py collectstatic` and serve `staticfiles/` with your web server (or add WhiteNoise).
* Set persistent storage for `MEDIA_ROOT` and back up uploaded training group photos. Serve these photos through the authenticated QA photo endpoint rather than exposing the media directory directly.
* Run the app with a production server such as gunicorn, behind HTTPS.
* Back up the database regularly.
