from io import BytesIO
from tempfile import TemporaryDirectory
from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import User
from core.models import FarmerReview
from qa.models import QACall
from qa.services import call_queue
from shop.models import Brand, Order, Product
from training.models import Attendance, County, Farmer, Topic, TrainingSession

PASSWORD = "pass-12345-Xy"


class DigicowTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.county = County.objects.create(name="Kiambu")
        cls.coord = User.objects.create_user(
            "coord", password=PASSWORD, role=User.Role.COORDINATOR, first_name="Co", last_name="Ord"
        )
        cls.trainer = User.objects.create_user("trainer", password=PASSWORD, role=User.Role.TRAINER)
        cls.other_trainer = User.objects.create_user("trainer2", password=PASSWORD, role=User.Role.TRAINER)
        cls.agent = User.objects.create_user("agent", password=PASSWORD, role=User.Role.QA)
        cls.topic = Topic.objects.create(title="Soil health", summary="Cover testing.")
        cls.session = TrainingSession.objects.create(
            topic=cls.topic, county=cls.county, trainer=cls.trainer, venue="Hall",
            date=timezone.localdate() - timedelta(days=1),
        )
        cls.brand = Brand.objects.create(name="Juanco", slug="juanco")
        cls.product = Product.objects.create(
            brand=cls.brand, name="Feed", unit="50 kg", price=Decimal("2500")
        )
        cls.farmer = Farmer.objects.create(full_name="Jane", phone="0712345678", county=cls.county)

    def login(self, user):
        self.client.force_login(user)


class PublicAndAccessTests(DigicowTestCase):
    def test_public_pages_load(self):
        for name in ["core:home", "core:about", "core:products", "core:trainings",
                     "core:contact", "accounts:login"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertContains(self.client.get(reverse("core:home")), "Hear from our trainees")
        self.assertContains(self.client.get(reverse("core:about")), "Create a farmer account")

    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_every_role_has_a_dashboard(self):
        for user in (self.coord, self.trainer, self.agent):
            self.login(user)
            self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 200, user)

    def test_farmer_can_sign_up_and_get_a_private_dashboard(self):
        response = self.client.post(
            reverse("accounts:farmer_signup"),
            {
                "username": "newfarmer",
                "first_name": "Amina",
                "last_name": "Wanjiku",
                "email": "",
                "phone": "0722333444",
                "county": self.county.pk,
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("core:dashboard"))
        user = User.objects.get(username="newfarmer")
        self.assertEqual(user.role, User.Role.FARMER)
        farmer = Farmer.objects.get(user=user)
        self.assertEqual((farmer.full_name, farmer.phone, farmer.county), (
            "Amina Wanjiku", "+254722333444", self.county
        ))
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("training:session_list")).status_code, 403)

    def test_farmer_login_is_separate_from_staff_login(self):
        user = User.objects.create_user(
            "farmerlogin",
            password=PASSWORD,
            role=User.Role.FARMER,
            phone="+254722333445",
        )
        Farmer.objects.create(
            full_name="Farmer Login",
            phone=user.phone,
            county=self.county,
            user=user,
        )

        response = self.client.post(
            reverse("accounts:farmer_login"),
            {"username": "farmerlogin", "password": PASSWORD},
        )
        self.assertRedirects(response, reverse("core:dashboard"))
        self.client.logout()
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "farmerlogin", "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "farmer sign-in page")

    def test_farmer_signup_will_not_claim_an_existing_training_record(self):
        response = self.client.post(
            reverse("accounts:farmer_signup"),
            {
                "username": "claimfarmer",
                "first_name": "Jane",
                "last_name": "Farmer",
                "email": "",
                "phone": self.farmer.phone,
                "county": self.county.pk,
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contact Digicow to verify")
        self.assertFalse(User.objects.filter(username="claimfarmer").exists())

    def test_role_restrictions(self):
        self.login(self.trainer)
        self.assertEqual(self.client.get(reverse("training:topic_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("qa:queue")).status_code, 403)
        self.login(self.agent)
        self.assertEqual(self.client.get(reverse("shop:order_list")).status_code, 403)
        self.login(self.coord)
        self.assertEqual(self.client.get(reverse("training:topic_list")).status_code, 200)

    def test_trainer_cannot_open_someone_elses_session(self):
        self.login(self.other_trainer)
        response = self.client.get(reverse("training:session_detail", args=[self.session.pk]))
        self.assertEqual(response.status_code, 404)

    def test_reports_and_exports(self):
        self.login(self.coord)
        self.assertEqual(self.client.get(reverse("core:reports")).status_code, 200)
        for name in ("core:export_attendance", "core:export_orders"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "text/csv")
        self.login(self.trainer)
        self.assertEqual(self.client.get(reverse("core:reports")).status_code, 403)

    def test_contact_form_saves_message(self):
        response = self.client.post(
            reverse("core:contact"), {"name": "Visitor", "phone": "0712 000 111", "message": "Hello"}
        )
        self.assertEqual(response.status_code, 302)

    def test_farmer_can_submit_review_for_completed_training(self):
        farmer_user = User.objects.create_user(
            "reviewfarmer",
            password=PASSWORD,
            role=User.Role.FARMER,
            phone="+254722333446",
        )
        farmer = Farmer.objects.create(
            full_name="Review Farmer",
            phone=farmer_user.phone,
            county=self.county,
            user=farmer_user,
        )
        completed_session = TrainingSession.objects.create(
            topic=self.topic,
            county=self.county,
            trainer=self.trainer,
            venue="Review field",
            date=timezone.localdate() - timedelta(days=2),
            status=TrainingSession.Status.COMPLETED,
        )
        attendance = Attendance.objects.create(session=completed_session, farmer=farmer)
        self.login(farmer_user)

        response = self.client.post(
            reverse("core:submit_review"),
            {
                "attendance": attendance.pk,
                "rating": 5,
                "comment": "The practical examples helped me plan my farm.",
            },
        )

        self.assertRedirects(response, reverse("core:home"))
        review = FarmerReview.objects.get(attendance=attendance)
        self.assertEqual(review.rating, 5)
        self.assertFalse(review.is_published)
        self.assertContains(
            self.client.get(reverse("core:home")),
            "after they’re submitted and approved",
        )

    def test_farmer_reviews_are_only_public_after_admin_publication(self):
        farmer_user = User.objects.create_user(
            "publishedfarmer",
            password=PASSWORD,
            role=User.Role.FARMER,
            phone="+254722333447",
        )
        farmer = Farmer.objects.create(
            full_name="Published Farmer",
            phone=farmer_user.phone,
            county=self.county,
            user=farmer_user,
        )
        completed_session = TrainingSession.objects.create(
            topic=self.topic,
            county=self.county,
            trainer=self.trainer,
            venue="Review field",
            date=timezone.localdate() - timedelta(days=2),
            status=TrainingSession.Status.COMPLETED,
        )
        attendance = Attendance.objects.create(session=completed_session, farmer=farmer)
        review = FarmerReview.objects.create(
            attendance=attendance,
            rating=4,
            comment="Helpful advice for my crops.",
        )
        self.assertNotContains(self.client.get(reverse("core:home")), "Helpful advice for my crops.")

        review.is_published = True
        review.save(update_fields=["is_published"])
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Helpful advice for my crops.")
        self.assertContains(response, f"Farmer, {self.county.name}")
        self.assertNotContains(response, farmer.full_name)

    def test_farmer_cannot_review_another_farmer_or_repeat_a_review(self):
        first_user = User.objects.create_user(
            "firstreviewer", password=PASSWORD, role=User.Role.FARMER, phone="+254722333448"
        )
        first_farmer = Farmer.objects.create(
            full_name="First Reviewer",
            phone=first_user.phone,
            county=self.county,
            user=first_user,
        )
        other_farmer = Farmer.objects.create(
            full_name="Other Trainee", phone="0722333449", county=self.county
        )
        attendance = Attendance.objects.create(session=self.session, farmer=other_farmer)
        self.login(first_user)
        response = self.client.post(
            reverse("core:submit_review"),
            {"attendance": attendance.pk, "rating": 5, "comment": "Not my training."},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(FarmerReview.objects.exists())

        completed_session = TrainingSession.objects.create(
            topic=self.topic,
            county=self.county,
            trainer=self.trainer,
            venue="Review field",
            date=timezone.localdate() - timedelta(days=2),
            status=TrainingSession.Status.COMPLETED,
        )
        own_attendance = Attendance.objects.create(
            session=completed_session,
            farmer=first_farmer,
        )
        FarmerReview.objects.create(
            attendance=own_attendance,
            rating=5,
            comment="Already submitted.",
        )
        response = self.client.post(
            reverse("core:submit_review"),
            {
                "attendance": own_attendance.pk,
                "rating": 3,
                "comment": "Trying a second review.",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FarmerReview.objects.count(), 1)

    def test_review_form_requires_farmer_sign_in(self):
        response = self.client.get(reverse("core:submit_review"))
        self.assertRedirects(
            response,
            f"{reverse('accounts:farmer_login')}?next={reverse('core:submit_review')}",
        )


class StaffAndFarmerTests(DigicowTestCase):
    def test_coordinator_creates_trainer_but_not_admin(self):
        self.login(self.coord)
        data = {
            "username": "newtrainer", "first_name": "New", "last_name": "Trainer",
            "email": "", "phone": "0722000111", "role": "trainer",
            "password1": "S3cure-pass-77!", "password2": "S3cure-pass-77!",
        }
        self.client.post(reverse("accounts:staff_create"), data)
        self.assertTrue(User.objects.filter(username="newtrainer", role="trainer").exists())

        data.update(username="sneaky", role="admin")
        self.client.post(reverse("accounts:staff_create"), data)
        self.assertFalse(User.objects.filter(username="sneaky").exists())
        data.update(username="publicfarmer", role="farmer")
        self.client.post(reverse("accounts:staff_create"), data)
        self.assertFalse(User.objects.filter(username="publicfarmer").exists())

    def test_duplicate_farmer_phone_is_rejected_in_any_format(self):
        self.login(self.trainer)
        response = self.client.post(
            reverse("training:farmer_create"),
            {"full_name": "Copy", "phone": "0712 345 678", "county": self.county.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Farmer.objects.count(), 1)
        self.assertEqual(Farmer.objects.get().phone, "+254712345678")


class AttendanceAndQATests(DigicowTestCase):
    def png_upload(self, name="group.png"):
        image_data = BytesIO()
        Image.new("RGB", (2, 2), color="yellow").save(image_data, format="PNG")
        return SimpleUploadedFile(name, image_data.getvalue(), content_type="image/png")

    def test_qa_queue_search_filters_farmers(self):
        Attendance.objects.create(session=self.session, farmer=self.farmer)
        other_farmer = Farmer.objects.create(
            full_name="Peter Kamau", phone="0722111222", county=self.county
        )
        Attendance.objects.create(session=self.session, farmer=other_farmer)
        self.login(self.agent)

        response = self.client.get(reverse("qa:queue"), {"q": "Jane"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["queue"]), [Attendance.objects.get(farmer=self.farmer)])
        self.assertContains(response, "Call management")
        self.assertContains(response, 'value="Jane"')

    def test_qa_history_search_finds_farmer(self):
        attendance = Attendance.objects.create(session=self.session, farmer=self.farmer)
        QACall.objects.create(attendance=attendance, agent=self.agent, outcome=QACall.Outcome.NO_ANSWER)
        self.login(self.agent)

        response = self.client.get(reverse("qa:history"), {"q": "Jane"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["calls"].count(), 1)
        self.assertContains(response, "Call management")
        self.assertContains(response, 'value="Jane"')

    def test_trainer_registers_known_and_new_farmers(self):
        self.login(self.trainer)
        response = self.client.post(
            reverse("training:attendance", args=[self.session.pk]),
            {"farmers": [self.farmer.pk], "new_farmers": "Peter Kamau, 0722 111 222\nMary, 0733000111"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.session.attendances.count(), 3)
        self.assertTrue(Farmer.objects.filter(phone="+254722111222", county=self.county).exists())

    def test_bad_new_farmer_line_is_rejected(self):
        self.login(self.trainer)
        response = self.client.post(
            reverse("training:attendance", args=[self.session.pk]),
            {"new_farmers": "No phone here"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.session.attendances.count(), 0)

    def test_trainer_can_complete_own_session(self):
        self.login(self.trainer)
        self.client.post(reverse("training:session_complete", args=[self.session.pk]))
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, TrainingSession.Status.COMPLETED)

    def test_confirmed_call_updates_attendance_and_leaves_queue(self):
        attendance = Attendance.objects.create(session=self.session, farmer=self.farmer)
        self.assertEqual(call_queue().count(), 1)
        self.login(self.agent)
        response = self.client.post(
            reverse("qa:call", args=[attendance.pk]),
            {"outcome": "confirmed", "rating": "4", "feedback": "Good", "farmer_question": "When next?"},
        )
        self.assertEqual(response.status_code, 302)
        attendance.refresh_from_db()
        self.assertEqual(attendance.status, Attendance.Status.CONFIRMED)
        call = QACall.objects.get()
        self.assertEqual((call.rating, call.farmer_question), (4, "When next?"))
        self.assertEqual(call_queue().count(), 0)

    def test_no_answer_keeps_farmer_in_queue_and_drops_rating(self):
        attendance = Attendance.objects.create(session=self.session, farmer=self.farmer)
        self.login(self.agent)
        self.client.post(
            reverse("qa:call", args=[attendance.pk]),
            {"outcome": "no_answer", "rating": "5", "feedback": "ignored"},
        )
        attendance.refresh_from_db()
        self.assertEqual(attendance.status, Attendance.Status.UNREACHABLE)
        self.assertIsNone(QACall.objects.get().rating)
        self.assertEqual(call_queue().get().attempts, 1)

    def test_coordinator_sees_call_history(self):
        self.login(self.coord)
        self.assertEqual(self.client.get(reverse("qa:history")).status_code, 200)

    def test_completed_trainings_are_grouped_by_trainer_for_qa(self):
        TrainingSession.objects.create(
            topic=self.topic,
            county=self.county,
            trainer=self.trainer,
            venue="Farm",
            date=timezone.localdate() - timedelta(days=2),
            status=TrainingSession.Status.COMPLETED,
        )
        TrainingSession.objects.create(
            topic=self.topic,
            county=self.county,
            trainer=self.other_trainer,
            venue="School",
            date=timezone.localdate() - timedelta(days=3),
            status=TrainingSession.Status.COMPLETED,
        )
        self.login(self.agent)

        response = self.client.get(reverse("qa:training_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["trainer_groups"]), 2)
        self.assertContains(response, "Trainer trainings")
        self.assertNotContains(response, "Register attendance")

    def test_trainer_cannot_access_qa_training_review(self):
        self.login(self.trainer)
        response = self.client.get(reverse("qa:training_list"))
        self.assertEqual(response.status_code, 403)

    def test_qa_can_review_one_trainee_with_a_required_reason(self):
        session = TrainingSession.objects.create(
            topic=self.topic,
            county=self.county,
            trainer=self.trainer,
            venue="Hall",
            date=timezone.localdate() - timedelta(days=1),
            status=TrainingSession.Status.COMPLETED,
        )
        attendance = Attendance.objects.create(session=session, farmer=self.farmer)
        self.login(self.agent)

        response = self.client.post(
            reverse("qa:review_trainee", args=[attendance.pk]),
            {"decision": "approved", "reason": "Photo and trainee details match."},
        )

        self.assertRedirects(response, reverse("qa:training_review", args=[session.pk]))
        attendance.refresh_from_db()
        self.assertEqual(attendance.review_status, Attendance.ReviewStatus.APPROVED)
        self.assertEqual(attendance.review_reason, "Photo and trainee details match.")
        self.assertEqual(attendance.reviewed_by, self.agent)
        self.assertIsNotNone(attendance.reviewed_at)
        self.assertEqual(attendance.status, Attendance.Status.PENDING)

        response = self.client.post(
            reverse("qa:review_trainee", args=[attendance.pk]),
            {"decision": "rejected", "reason": ""},
        )
        self.assertRedirects(response, reverse("qa:training_review", args=[session.pk]))
        attendance.refresh_from_db()
        self.assertEqual(attendance.review_status, Attendance.ReviewStatus.APPROVED)

    def test_qa_group_review_applies_decision_and_reason_to_every_trainee(self):
        session = TrainingSession.objects.create(
            topic=self.topic,
            county=self.county,
            trainer=self.trainer,
            venue="Hall",
            date=timezone.localdate() - timedelta(days=1),
            status=TrainingSession.Status.COMPLETED,
        )
        other_farmer = Farmer.objects.create(
            full_name="Peter Kamau", phone="0722111222", county=self.county
        )
        attendances = [
            Attendance.objects.create(session=session, farmer=farmer)
            for farmer in (self.farmer, other_farmer)
        ]
        self.login(self.agent)

        response = self.client.post(
            reverse("qa:review_training_group", args=[session.pk]),
            {"decision": "rejected", "reason": "The submitted group photo is unclear."},
        )

        self.assertRedirects(response, reverse("qa:training_review", args=[session.pk]))
        for attendance in attendances:
            attendance.refresh_from_db()
            self.assertEqual(attendance.review_status, Attendance.ReviewStatus.REJECTED)
            self.assertEqual(attendance.review_reason, "The submitted group photo is unclear.")
            self.assertEqual(attendance.reviewed_by, self.agent)
            self.assertIsNotNone(attendance.reviewed_at)

    def test_trainer_uploads_group_photo_and_photo_is_access_controlled(self):
        with TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                self.login(self.trainer)
                response = self.client.post(
                    reverse("training:attendance", args=[self.session.pk]),
                    {"group_photo": self.png_upload()},
                )
                self.assertRedirects(
                    response, reverse("training:session_detail", args=[self.session.pk])
                )
                self.session.refresh_from_db()
                self.assertTrue(self.session.group_photo)

                response = self.client.get(reverse("qa:training_photo", args=[self.session.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "image/png")
                self.assertTrue(b"".join(response.streaming_content).startswith(b"\x89PNG"))

                self.login(self.other_trainer)
                self.assertEqual(
                    self.client.get(
                        reverse("qa:training_photo", args=[self.session.pk])
                    ).status_code,
                    404,
                )

    def test_qa_review_page_shows_photo_and_trainee_list(self):
        session = TrainingSession.objects.create(
            topic=self.topic,
            county=self.county,
            trainer=self.trainer,
            venue="Hall",
            date=timezone.localdate() - timedelta(days=1),
            status=TrainingSession.Status.COMPLETED,
        )
        Attendance.objects.create(session=session, farmer=self.farmer)
        self.login(self.agent)

        response = self.client.get(reverse("qa:training_review", args=[session.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trainee list")
        self.assertContains(response, 'type="radio"')
        self.assertContains(response, self.farmer.full_name)
        self.assertContains(response, "No group photo uploaded")


class OrderTests(DigicowTestCase):
    def order_data(self, **overrides):
        data = {
            "farmer": self.farmer.pk, "session": "", "delivery_location": "Gate", "notes": "",
            "items-TOTAL_FORMS": "4", "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1", "items-MAX_NUM_FORMS": "1000",
            "items-0-product": self.product.pk, "items-0-quantity": "3",
        }
        for i in (1, 2, 3):
            data[f"items-{i}-product"] = ""
            data[f"items-{i}-quantity"] = ""
        data.update(overrides)
        return data

    def test_trainer_places_order_and_price_is_frozen(self):
        self.login(self.trainer)
        response = self.client.post(reverse("shop:order_create"), self.order_data())
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get()
        self.assertEqual(order.trainer, self.trainer)
        self.assertEqual(order.total, Decimal("7500"))
        self.product.price = Decimal("9999")
        self.product.save()
        self.assertEqual(Order.objects.get().total, Decimal("7500"))

    def test_duplicate_product_lines_are_rejected(self):
        self.login(self.trainer)
        data = self.order_data(**{"items-1-product": self.product.pk, "items-1-quantity": "1"})
        response = self.client.post(reverse("shop:order_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)

    def test_order_needs_at_least_one_item(self):
        self.login(self.trainer)
        data = self.order_data(**{"items-0-product": "", "items-0-quantity": ""})
        response = self.client.post(reverse("shop:order_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)

    def test_status_workflow_and_permissions(self):
        self.login(self.trainer)
        self.client.post(reverse("shop:order_create"), self.order_data())
        order = Order.objects.get()

        # A trainer cannot approve their own order.
        response = self.client.post(reverse("shop:order_status", args=[order.pk, "approved"]))
        self.assertEqual(response.status_code, 403)

        # Another trainer cannot even see it.
        self.login(self.other_trainer)
        self.assertEqual(self.client.get(reverse("shop:order_detail", args=[order.pk])).status_code, 404)

        # The coordinator approves and delivers it, but cannot skip steps.
        self.login(self.coord)
        self.client.post(reverse("shop:order_status", args=[order.pk, "delivered"]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.client.post(reverse("shop:order_status", args=[order.pk, "approved"]))
        self.client.post(reverse("shop:order_status", args=[order.pk, "delivered"]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)

    def test_trainer_can_cancel_own_pending_order(self):
        self.login(self.trainer)
        self.client.post(reverse("shop:order_create"), self.order_data())
        order = Order.objects.get()
        self.client.post(reverse("shop:order_status", args=[order.pk, "cancelled"]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
