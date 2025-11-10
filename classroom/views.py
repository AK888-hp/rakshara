from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import VirtualClassroom, StudentProfile
from accounts.models import StudentProfile, Notification, JoinRequest
from health.models import VitalRecord
from health.utils import predict_health
from django.core.mail import send_mail
from django.conf import settings

# 🧩 Teacher Dashboard
@login_required
def teacher_dashboard(request):
    """Display teacher dashboard with classes, notifications, and pending join requests."""
    teacher = request.user
    school = getattr(teacher, 'school', None)

    # ✅ Restrict to teachers only
    if not getattr(teacher, "is_teacher", False):
        messages.error(request, "Access denied: only teachers can access this page.")
        return redirect('student_dashboard')

    # ✅ Notifications
    notifications = Notification.objects.filter(teacher=teacher).order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    Notification.objects.filter(teacher=teacher, is_read=False).update(is_read=True)

    # ✅ Virtual classes
    classes = VirtualClassroom.objects.filter(teacher=teacher)

    # ✅ Pending join requests (students waiting for approval)
    pending_requests = JoinRequest.objects.filter(
        teacher=teacher, approved=False
    ).select_related('student__user')

    # ✅ Handle new class creation
    if request.method == 'POST':
        class_name = request.POST.get('class_name')
        section = request.POST.get('section')

        if not school:
            messages.error(request, 'You are not assigned to any school.')
            return redirect('teacher_dashboard')

        if VirtualClassroom.objects.filter(school=school, class_name=class_name, section=section).exists():
            messages.warning(request, f"⚠️ Class {class_name}-{section} already exists.")
        else:
            vc = VirtualClassroom.objects.create(
                school=school,
                teacher=teacher,
                class_name=class_name,
                section=section
            )
            messages.success(request, f"🏫 Class {vc.class_name}-{vc.section} created successfully!")

        return redirect('teacher_dashboard')

    # ✅ Add student counts
    for c in classes:
        c.student_count = c.students.count()

    return render(
        request,
        'classroom/teacher_dashboard.html',
        {
            'classes': classes,
            'notifications': notifications,
            'unread_count': unread_count,
            'pending_requests': pending_requests,
        }
    )


# 🧩 Approve Join Request
@login_required
def approve_request(request, pk):
    """Approve student’s join request and add them to the class."""
    join_req = get_object_or_404(JoinRequest, pk=pk, teacher=request.user)
    vc = VirtualClassroom.objects.filter(
        teacher=request.user,
        class_name=join_req.class_name,
        section=join_req.section
    ).first()

    if vc:
        vc.students.add(join_req.student)
        join_req.approved = True
        join_req.save()
        Notification.objects.create(
            teacher=request.user,
            message=f"✅ {join_req.student.user.username} has been approved and added to {vc.class_name}-{vc.section}."
        )
        messages.success(request, f"✅ {join_req.student.user.username} added to {vc.class_name}-{vc.section}.")
    else:
        messages.error(request, "⚠️ No matching class found to add this student.")
    return redirect('teacher_dashboard')


# 🧩 Reject Join Request
@login_required
def reject_request(request, pk):
    """Reject and delete student join request."""
    join_req = get_object_or_404(JoinRequest, pk=pk, teacher=request.user)
    join_req.delete()
    messages.info(request, f"🚫 Join request from {join_req.student.user.username} rejected.")
    return redirect('teacher_dashboard')


# 🧩 Class Detail Page
@login_required
def classroom_detail(request, pk):
    """Display all students of a specific virtual classroom."""
    vc = get_object_or_404(VirtualClassroom, pk=pk)
    if not getattr(request.user, "is_teacher", False):
        return redirect('student_dashboard')

    students = vc.students.all().order_by('roll_no')
    return render(request, 'classroom/classroom_detail.html', {'vc': vc, 'students': students})





@login_required
def quick_checkup(request, pk):
    """
    Teachers can perform quick sequential health checkups for each student.
    Handles parent email alerts safely and shows popups for invalid addresses.
    """
    vc = get_object_or_404(VirtualClassroom, id=pk)
    students = list(vc.students.all().order_by("roll_no"))
    idx = int(request.GET.get("idx", 0))

    # ✅ End of student list
    if idx >= len(students):
        messages.success(request, "✅ Quick checkup completed for all students!")
        return redirect("classroom_detail", vc.id)

    student = students[idx]

    # ✅ Handle SEND ALERT button
    if request.method == "POST" and "alert" in request.POST:
        parent_email = getattr(student, "parent_contact", "").strip()
        if not parent_email or "@" not in parent_email:
            # Show popup alert on page for invalid email
            return render(
                request,
                "classroom/quick_check.html",
                {
                    "vc": vc,
                    "student": student,
                    "idx": idx,
                    "total": len(students),
                    "invalid_email": True,
                    "prediction_label": "Mild",
                },
            )

        try:
            subject = f"⚠️ Health Alert for {student.user.get_full_name()}"
            message = (
                f"Dear Parent,\n\n"
                f"During today's school health checkup, your child {student.user.get_full_name()} "
                f"was found to have a mild or critical health condition.\n\n"
                f"Please take necessary care and consult a doctor if needed.\n\n"
                f"Regards,\nRakshara Health Monitoring Team"
            )
            send_mail(subject, message, settings.EMAIL_HOST_USER, [parent_email])
            messages.success(
                request, f"📧 Alert sent successfully to {student.user.get_full_name()}'s parent."
            )
            return redirect(f"{request.path}?idx={idx + 1}")

        except (SMTPRecipientsRefused, BadHeaderError):
            return render(
                request,
                "classroom/quick_check.html",
                {
                    "vc": vc,
                    "student": student,
                    "idx": idx,
                    "total": len(students),
                    "invalid_email": True,
                    "prediction_label": "Mild",
                },
            )
        except Exception as e:
            messages.error(request, f"❌ Email sending failed: {e}")
            return redirect(f"{request.path}?idx={idx + 1}")

    # ✅ Handle normal checkup submission
    if request.method == "POST":
        try:
            hr = int(request.POST.get("heart_rate"))
            spo2 = float(request.POST.get("spo2"))
            br = float(request.POST.get("breathing_rate"))
            temp = float(request.POST.get("temperature"))
            weight = float(request.POST.get("weight_kg") or student.weight_kg or 0)
            height = float(request.POST.get("height_cm") or student.height_cm or 0)

            score, label = predict_health(hr, spo2, br, temp, weight, height)

            VitalRecord.objects.create(
                student=student,
                heart_rate=hr,
                spo2=spo2,
                breathing_rate=br,
                temperature_c=temp,
                weight_kg=weight,
                height_cm=height,
                prediction_score=score,
                prediction_label=label,
            )

            return render(
                request,
                "classroom/quick_check.html",
                {
                    "vc": vc,
                    "student": student,
                    "idx": idx,
                    "total": len(students),
                    "prediction_score": score,
                    "prediction_label": label,
                },
            )

        except (TypeError, ValueError):
            messages.error(request, "⚠️ Invalid or missing vital data entered.")
        except Exception as e:
            messages.error(request, f"❌ Error saving record: {e}")

    # ✅ Page load
    return render(
        request,
        "classroom/quick_check.html",
        {"vc": vc, "student": student, "idx": idx, "total": len(students)},
    )
