from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib import messages
from .forms import StudentSignUpForm, TeacherSignUpForm, StudentProfileEditForm
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
from django.utils import translation


# 🧩 STUDENT REGISTRATION
def student_register(request):
    if request.method == "POST":
        form = StudentSignUpForm(request.POST) 
        if form.is_valid():
            user = form.save(commit=False)
            user.is_student = True
            user.school = form.cleaned_data['school']
            user.save()

            profile = user.student_profile
            profile.roll_no = form.cleaned_data.get('roll_no')
            profile.dob = form.cleaned_data.get('dob')
            profile.height_cm = form.cleaned_data.get('height_cm')
            profile.weight_kg = form.cleaned_data.get('weight_kg')
            profile.personal_contact = form.cleaned_data.get('personal_contact')
            
            parent_email = request.POST.get('parent_email')
            if parent_email:
                profile.parent_contact = parent_email.strip()

            profile.address = form.cleaned_data.get('address')
            profile.class_name = form.cleaned_data.get('class_name')
            profile.section = form.cleaned_data.get('section')
            profile.save()
            
            teachers = TeacherProfile.objects.filter(user__school=user.school)
            found = False
            for teacher in teachers:
                if teacher.user.classes_teaching.filter(
                    class_name=profile.class_name,
                    section=profile.section
                ).exists():
                    Notification.objects.create(
                        teacher=teacher.user,
                        message=(
                            f"New student {user.get_full_name() or user.username} "
                            f"requested to join class {profile.class_name}-{profile.section}."
                        )
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
                    message=(
                        f"New student {user.get_full_name() or user.username} "
                        f"registered (no assigned teacher yet)."
                    )
                )

            login(request, user)
            messages.success(
                request,
                f"Account created successfully! Your Student ID: {profile.student_code}"
            )
            # --- FIX 1 ---
            return redirect('health:student_dashboard')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = StudentSignUpForm()

    return render(request, 'accounts/student_register.html', {'form': form})

# 🧩 TEACHER REGISTRATION
def teacher_register(request):
    if request.method == "POST":
        form = TeacherSignUpForm(request.POST)
        if form.is_valid():
            verification_id = form.cleaned_data['verification_id']
            school = form.cleaned_data['school']

            if school.school_code != verification_id:
                form.add_error('verification_id', 'Verification ID does not match school records')
            else:
                user = form.save(commit=False)
                user.is_teacher = True
                user.school = school
                user.is_active = False
                user.save()

                profile = user.teacher_profile
                profile.contact = form.cleaned_data.get('contact')
                profile.address = form.cleaned_data.get('address')
                profile.verification_id = verification_id
                profile.save()

                otp = user.generate_otp()
                subject = "Teacher Account Verification OTP"
                message = f"Dear {user.username},\n\nYour OTP for verification is: {otp}\n\nPlease enter this to activate your account."
                send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email])

                request.session['pending_teacher_id'] = user.id
                messages.info(request, "OTP sent to your registered email. Please verify to activate your account.")
                return redirect('verify_teacher_signup_otp')
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
            # --- FIX 2 ---
            return redirect('health:teacher_dashboard')
        elif getattr(user, "is_student", False):
            # --- FIX 3 ---
            return redirect('health:student_dashboard')
    return render(request, 'home.html')


# 🔑 LOGIN
def login_view(request):
    if request.method == "POST":
        username_or_id = request.POST.get("username")
        password = request.POST.get("password")

        user = None
        user = authenticate(request, username=username_or_id, password=password)

        if user is None:
            from accounts.models import StudentProfile
            try:
                student = StudentProfile.objects.get(student_code=username_or_id)
                user = authenticate(request, username=student.user.username, password=password)
            except StudentProfile.DoesNotExist:
                user = None

        if user is not None:
            if getattr(user, "is_teacher", False):
                otp = str(random.randint(100000, 999999))
                user.otp = otp
                user.save()

                subject = "Login Verification OTP"
                message = f"Dear {user.username},\n\nYour OTP for login is: {otp}\n\nUse this to complete your login."
                send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email])

                request.session['pending_login_user_id'] = user.id
                messages.info(request, "OTP sent to your email. Please verify to complete login.")
                return redirect('verify_teacher_login_otp')

            elif getattr(user, "is_student", False):
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                # --- FIX 4 ---
                return redirect('health:student_dashboard')
            else:
                login(request, user)
                return redirect('home')

        else:
            messages.error(request, "Invalid username, student ID, or password.")

    return render(request, "accounts/login.html")

# 🚪 LOGOUT
def logout_view(request):
    django_logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('home')


# -----------------------------------------
# 🔐 VERIFY OTP (Teacher Signup)
# -----------------------------------------
def verify_teacher_signup_otp(request):
    teacher_id = request.session.get('pending_teacher_id')
    if not teacher_id:
        messages.error(request, "No registration in progress.")
        return redirect('teacher_register')

    user = get_object_or_404(User, id=teacher_id)

    if request.method == "POST":
        entered_otp = request.POST.get("otp")
        if entered_otp == user.otp:
            user.is_active = True
            user.is_verified = True
            user.otp = None
            user.save()
            del request.session['pending_teacher_id']
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your account is verified and active.")
            # --- FIX 5 ---
            return redirect('health:teacher_dashboard')
        else:
            messages.error(request, "Invalid OTP. Please try again.")

    return render(request, 'accounts/verify_teacher_otp.html', {'email': user.email})


# -----------------------------------------
# 🔐 VERIFY OTP (Teacher Login)
# -----------------------------------------
def verify_teacher_login_otp(request):
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
            login(request, user)
            del request.session['pending_login_user_id']
            messages.success(request, f"Welcome back, {user.username}!")
            # --- FIX 6 ---
            return redirect('health:teacher_dashboard')
        else:
            messages.error(request, "Invalid OTP. Please try again.")

    return render(request, 'accounts/verify_teacher_otp.html', {'email': user.email})

# 🌐 LANGUAGE SWITCHER VIEW
def set_language(request):
    if request.method == "POST":
        lang = request.POST.get("language", "en")
        if lang in ["en", "kn", "hi"]:
            request.session["django_language"] = lang
            translation.activate(lang)
            messages.success(request, f"Language changed to {lang.upper()}")
        else:
            messages.error(request, "Invalid language selected.")
    return redirect(request.META.get("HTTP_REFERER", "home"))


# -----------------------------------------
# 🔗 NEW PLACEHOLDER PAGES (Settings, Help, FAQ)
# -----------------------------------------

def settings_page(request):
    return render(request, 'accounts/settings.html')

def help_center_page(request):
    return render(request, 'accounts/help_center.html')

def faq_page(request):
    return render(request, 'accounts/faq.html')


# --- 4. NEW PROFILE VIEWS ---

@login_required
def student_profile(request):
    if not request.user.is_student:
        return redirect('home')
    
    profile = request.user.student_profile
    context = {
        'profile': profile
    }
    return render(request, 'accounts/student_profile.html', context)


@login_required
def edit_student_profile(request):
    if not request.user.is_student:
        return redirect('home')
        
    profile = request.user.student_profile
    
    if request.method == 'POST':
        form = StudentProfileEditForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('student_profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = StudentProfileEditForm(instance=profile)

    context = {
        'form': form
    }
    return render(request, 'accounts/edit_student_profile.html', context)


@login_required
def teacher_view_student_profile(request, student_code):
    if not request.user.is_teacher:
        return redirect('home')
    
    profile = get_object_or_404(StudentProfile, student_code=student_code, user__school=request.user.school)
    
    context = {
        'profile': profile
    }
    return render(request, 'accounts/teacher_view_student_profile.html', context)