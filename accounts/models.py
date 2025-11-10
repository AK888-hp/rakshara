from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import random


# ---------------------- School Model ----------------------
class School(models.Model):
    name = models.CharField(max_length=255, unique=True)
    school_code = models.CharField(max_length=20, unique=True)  # e.g., PPS
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


# ---------------------- Custom User ----------------------
class User(AbstractUser):
    is_student = models.BooleanField(default=False)
    is_teacher = models.BooleanField(default=False)
    school = models.ForeignKey('School', on_delete=models.SET_NULL, null=True, blank=True)

    is_verified = models.BooleanField(default=False)  # ✅ new
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)

    def generate_otp(self):
        """Generate 6-digit OTP and store it temporarily."""
        otp = str(random.randint(100000, 999999))
        self.otp = otp
        from django.utils import timezone
        self.otp_created_at = timezone.now()
        self.save()
        return otp

# ---------------------- Student Profile ----------------------
class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    roll_no = models.CharField(max_length=50)
    dob = models.DateField(null=True, blank=True)
    height_cm = models.FloatField(null=True, blank=True)
    weight_kg = models.FloatField(null=True, blank=True)
    personal_contact = models.CharField(max_length=20, blank=True)
    parent_contact = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    class_name = models.CharField(max_length=50)
    section = models.CharField(max_length=10)
    student_code = models.CharField(max_length=50, unique=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if self.user and self.user.school:
            school_code = (self.user.school.school_code or self.user.school.name[:3]).lower()
            class_code = str(self.class_name).lower().replace(" ", "")
            section_code = str(self.section).lower()
            roll_code = str(self.roll_no).zfill(2)

            base_code = f"{school_code}{class_code}{section_code}{roll_code}"

            similar_codes = StudentProfile.objects.filter(student_code__startswith=base_code).exclude(pk=self.pk)
            if similar_codes.exists():
                count = similar_codes.count() + 1
                self.student_code = f"{base_code}-{count}"
            else:
                self.student_code = base_code
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.student_code}"


# ---------------------- Teacher Profile ----------------------
class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    contact = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    verification_id = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.get_full_name()} (Teacher)"


# ---------------------- Notifications ----------------------
class Notification(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'is_teacher': True}, null=True, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"To {self.teacher} - {self.message[:40]}..."


# ---------------------- Join Requests ----------------------
class JoinRequest(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'is_teacher': True})
    class_name = models.CharField(max_length=50)
    section = models.CharField(max_length=10)
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        status = "✅ Approved" if self.approved else "⏳ Pending"
        return f"{self.student.user.username} → {self.teacher.username} ({status})"
