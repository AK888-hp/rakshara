from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib import messages
from .forms import StudentSignUpForm, TeacherSignUpForm
from .models import School, StudentProfile, User, TeacherProfile, Notification, JoinRequest
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout as django_logout
from .utils import send_teacher_otp_email
from django.utils import timezone
from datetime import timedelta
from .models import User
import random
from django.conf import settings
from django.core.mail import send_mail


# 🧩 STUDENT REGISTRATION
def student_register(request):
    if request.method == "POST":
        form = StudentSignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_student = True
            user.school = form.cleaned_data['school']
            user.save()

            # Update student profile
            profile = user.student_profile
            profile.roll_no = form.cleaned_data.get('roll_no')
            profile.dob = form.cleaned_data.get('dob')
            profile.height_cm = form.cleaned_data.get('height_cm')
            profile.weight_kg = form.cleaned_data.get('weight_kg')
            profile.personal_contact = form.cleaned_data.get('personal_contact')
            profile.parent_contact = form.cleaned_data.get('parent_contact')
            profile.address = form.cleaned_data.get('address')
            profile.class_name = form.cleaned_data.get('class_name')
            profile.section = form.cleaned_data.get('section')
            profile.save()

            # ✅ Notify teachers (create join request)
            teachers = TeacherProfile.objects.filter(user__school=user.school)
            found = False
            for teacher in teachers:
                if teacher.user.classes_teaching.filter(class_name=profile.class_name, section=profile.section).exists():
                    Notification.objects.create(
                        teacher=teacher.user,
                        message=f"🆕 New student {user.get_full_name() or user.username} requested to join class {profile.class_name}-{profile.section}."
                    )
                    JoinRequest.objects.create(
                        student=profile,
                        teacher=teacher.user,
                        class_name=profile.class_name,
                        section=profile.section
                    )
                    found = True
            if not found:
                Notification.objects.create(
                    message=f"🆕 New student {user.get_full_name() or user.username} registered (no assigned teacher yet)."
                )

            login(request, user)
            messages.success(request, f"✅ Account created successfully! Your Student ID: {profile.student_code}")
            return redirect('student_dashboard')
        messages.error(request, "Please correct the errors below.")
    else:
        form = StudentSignUpForm()
    return render(request, 'accounts/student_register.html', {'form': form})


# 🧩 TEACHER REGISTRATION
from django.core.mail import send_mail
from django.conf import settings

def teacher_register(request):
    if request.method == "POST":
        form = TeacherSignUpForm(request.POST)
        if form.is_valid():
            verification_id = form.cleaned_data['verification_id']
            school = form.cleaned_data['school']

            if school.school_code != verification_id:
                form.add_error('verification_id', '❌ Verification ID does not match school records')
            else:
                user = form.save(commit=False)
                user.is_teacher = True
                user.school = school
                user.is_active = False  # ⛔ deactivate until OTP verified
                user.save()

                # Save profile details
                profile = user.teacher_profile
                profile.contact = form.cleaned_data.get('contact')
                profile.address = form.cleaned_data.get('address')
                profile.verification_id = verification_id
                profile.save()

                # ✅ Generate and send OTP
                otp = user.generate_otp()
                subject = "Teacher Account Verification OTP"
                message = f"Dear {user.username},\n\nYour OTP for verification is: {otp}\n\nPlease enter this to activate your account."
                send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email])

                request.session['pending_teacher_id'] = user.id
                messages.info(request, "📧 OTP sent to your registered email. Please verify to activate your account.")
                return redirect('verify_teacher_otp')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = TeacherSignUpForm()

    return render(request, 'accounts/teacher_register.html', {'form': form})

# 🏠 HOME
def home(request):
    user = request.user
    if user.is_authenticated:
        if getattr(user, "is_teacher", False):
            return redirect('teacher_dashboard')
        elif getattr(user, "is_student", False):
            return redirect('student_dashboard')
    return render(request, 'home.html')




def login_view(request):
    if request.method == "POST":
        username_or_id = request.POST.get("username")
        password = request.POST.get("password")

        user = None

        # 1️⃣ Try authenticating with username
        user = authenticate(request, username=username_or_id, password=password)

        # 2️⃣ If failed, check if it's a student ID
        if user is None:
            from accounts.models import StudentProfile
            try:
                student = StudentProfile.objects.get(student_code=username_or_id)
                user = authenticate(request, username=student.user.username, password=password)
            except StudentProfile.DoesNotExist:
                user = None

        # 3️⃣ If user found
        if user is not None:
            if getattr(user, "is_teacher", False):
                # ✅ Generate OTP for teachers
                otp = str(random.randint(100000, 999999))
                user.otp = otp
                user.save()

                # Send OTP via email
                subject = "Login Verification OTP"
                message = f"Dear {user.username},\n\nYour OTP for login is: {otp}\n\nUse this to complete your login."
                send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email])

                # Store session to verify later
                request.session['pending_login_user_id'] = user.id
                messages.info(request, "📧 OTP sent to your email. Please verify to complete login.")
                return redirect('verify_teacher_login_otp')

            elif getattr(user, "is_student", False):
                # ✅ Students log in directly (no OTP)
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect('student_dashboard')
            else:
                # Generic fallback for admins
                login(request, user)
                return redirect('home')

        else:
            messages.error(request, "❌ Invalid username, student ID, or password.")

    return render(request, "accounts/login.html")

# 🚪 LOGOUT
def logout_view(request):
    django_logout(request)
    messages.info(request, "👋 You have been logged out successfully.")
    return redirect('home')
from django.shortcuts import get_object_or_404




# -----------------------------------------
# 🔐 VERIFY OTP (Teacher Signup)
# -----------------------------------------
def verify_teacher_signup_otp(request):
    """Handles OTP verification for newly registered teachers."""
    teacher_id = request.session.get('pending_teacher_id')
    if not teacher_id:
        messages.error(request, "No registration in progress.")
        return redirect('teacher_register')

    user = get_object_or_404(User, id=teacher_id)

    if request.method == "POST":
        entered_otp = request.POST.get("otp")
        if entered_otp == user.otp:
            # ✅ Activate teacher account
            user.is_active = True
            user.is_verified = True
            user.otp = None
            user.save()

            # ✅ Remove pending session
            del request.session['pending_teacher_id']

            # ✅ Auto-login after verification
            login(request, user)
            messages.success(request, f"✅ Welcome, {user.username}! Your account is verified and active.")
            return redirect('teacher_dashboard')
        else:
            messages.error(request, "❌ Invalid OTP. Please try again.")

    return render(request, 'accounts/verify_teacher_otp.html', {'email': user.email})


# -----------------------------------------
# 🔐 VERIFY OTP (Teacher Login)
# -----------------------------------------
def verify_teacher_login_otp(request):
    """Handles OTP verification for teachers during login."""
    user_id = request.session.get('pending_login_user_id')
    if not user_id:
        messages.error(request, "No OTP verification in progress.")
        return redirect('login')

    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        entered_otp = request.POST.get("otp")
        if entered_otp == user.otp:
            user.otp = None
            user.save()

            # ✅ Log in teacher and clean session
            login(request, user)
            del request.session['pending_login_user_id']
            messages.success(request, f"✅ Welcome back, {user.username}!")
            return redirect('teacher_dashboard')
        else:
            messages.error(request, "❌ Invalid OTP. Please try again.")

    return render(request, 'accounts/verify_teacher_otp.html', {'email': user.email})
