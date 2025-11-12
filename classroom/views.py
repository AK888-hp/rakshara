from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail, BadHeaderError
from smtplib import SMTPRecipientsRefused

from .models import VirtualClassroom
from health.models import VitalRecord
from accounts.models import StudentProfile, Notification, User, JoinRequest
from ai_engine.utils import predict_health

from django.db.models import Avg, Count, Case, When, Prefetch
from django.db.models.functions import TruncDay
import json


# --- THIS FUNCTION IS DELETED to prevent the infinite loop ---
# def teacher_dashboard(request):
#     return redirect('teacher_dashboard')


@login_required
def approve_request(request, req_id):
    req = get_object_or_404(JoinRequest, id=req_id, teacher=request.user)
    
    vc = get_object_or_404(
        VirtualClassroom, 
        teacher=request.user, 
        class_name=req.class_name, 
        section=req.section
    )
    
    vc.students.add(req.student)
    req.approved = True
    req.save()
    messages.success(request, f"{req.student.user.username} approved.")
    
    # --- FIXED REDIRECT ---
    return redirect('health:teacher_dashboard')


@login_required
def reject_request(request, req_id):
    req = get_object_or_404(JoinRequest, id=req_id, teacher=request.user)
    req.delete()
    messages.warning(request, f"{req.student.user.username} request rejected.")
    
    # --- FIXED REDIRECT ---
    return redirect('health:teacher_dashboard')


@login_required
def delete_student_from_class(request, student_id, class_id):
    if not request.user.is_teacher:
        return redirect('home')

    vc = get_object_or_404(VirtualClassroom, id=class_id, teacher=request.user)
    student = get_object_or_404(StudentProfile, id=student_id)

    if 'confirm' in request.GET:
        vc.students.remove(student)
        messages.success(request, f"{student.user.username} has been removed from the class.")
    else:
        messages.info(request, "Please confirm deletion.")
    
    return redirect('classroom_detail', pk=class_id)


@login_required
def classroom_detail(request, pk):
    if not request.user.is_teacher:
        return redirect('home')
    
    vc = get_object_or_404(VirtualClassroom, id=pk, teacher=request.user)
    
    latest_vitals_prefetch = Prefetch(
        'vitals',
        queryset=VitalRecord.objects.order_by('-recorded_at'),
        to_attr='latest_vitals_list'
    )
    students = vc.students.all().select_related('user').prefetch_related(latest_vitals_prefetch)

    status_counts = {
        "Healthy": 0,
        "Watch": 0,
        "Risk": 0,
        "Not Yet Checked": 0
    }

    for student in students:
        if student.latest_vitals_list:
            latest_vital = student.latest_vitals_list[0]
            label = latest_vital.prediction_label.lower()
            
            if "healthy" in label or "normal" in label:
                status_counts["Healthy"] += 1
            elif "watch" in label or "mild" in label or "moderate" in label:
                status_counts["Watch"] += 1
            elif "high risk" in label or "critical" in label:
                status_counts["Risk"] += 1
            else:
                status_counts["Risk"] += 1 
        else:
            status_counts["Not Yet Checked"] += 1
            
    pie_chart_data = {
        "labels": ["Healthy/Normal", "Watch/Mild", "High Risk/Critical", "Not Yet Checked"],
        "data": [
            status_counts["Healthy"],
            status_counts["Watch"],
            status_counts["Risk"],
            status_counts["Not Yet Checked"]
        ],
    }

    all_vitals = VitalRecord.objects.filter(student__in=students)

    avg_health_over_time = all_vitals.annotate(
        day=TruncDay('recorded_at')
    ).values('day').annotate(
        avg_score=Avg('prediction_score')
    ).order_by('day')

    line_chart_data = {
        "labels": [entry['day'].strftime('%b %d, %Y') for entry in avg_health_over_time],
        "data": [round(entry['avg_score'], 1) for entry in avg_health_over_time],
    }

    context = {
        'vc': vc,
        'students': students,
        'pie_chart_data_json': json.dumps(pie_chart_data),
        'line_chart_data_json': json.dumps(line_chart_data),
    }
    return render(request, 'classroom/classroom_detail.html', context)


@login_required
def quick_checkup(request, pk):
    if not request.user.is_teacher:
        return redirect('home')

    vc = get_object_or_404(VirtualClassroom, id=pk, teacher=request.user)
    students = list(vc.students.all())
    total_students = len(students)

    try:
        idx = int(request.GET.get('idx', 0))
        student_profile = students[idx]
    except (IndexError, ValueError):
        messages.success(request, "Quick checkup completed for all students.")
        return redirect('classroom_detail', pk=pk)

    if request.method == 'POST':
        if 'alert' in request.POST:
            parent_email = student_profile.parent_contact
            if parent_email:
                try:
                    subject = f"Health Alert for {student_profile.user.get_full_name()}"
                    message = (
                        f"Dear Parent/Guardian,\n\n"
                        f"This is an alert from {vc.school.name}. "
                        f"A recent health check for {student_profile.user.get_full_name()} (Class: {vc.class_name}-{vc.section}) showed a potential health concern. "
                        f"Please contact the school for more details.\n\n"
                        f"- Rakshara System"
                    )
                    send_mail(subject, message, settings.EMAIL_HOST_USER, [parent_email])
                    messages.success(request, f"Alert sent to {parent_email} for {student_profile.user.get_full_name()}.")
                
                except (SMTPRecipientsRefused, BadHeaderError):
                    return render(request, 'classroom/quick_check.html', {
                        'vc': vc, 'student': student_profile, 'idx': idx, 'total': total_students, 'invalid_email': True
                    })
                except Exception as e:
                    messages.error(request, f"Could not send email. Error: {e}")
            else:
                return render(request, 'classroom/quick_check.html', {
                    'vc': vc, 'student': student_profile, 'idx': idx, 'total': total_students, 'invalid_email': True
                })
            
            return redirect(f"{request.path_info}?idx={idx + 1}")

        else:
            hr = int(request.POST.get('heart_rate'))
            spo2 = float(request.POST.get('spo2'))
            br = float(request.POST.get('breathing_rate'))
            temp = float(request.POST.get('temperature'))
            
            weight = request.POST.get('weight_kg') or student_profile.weight_kg or None
            height = request.POST.get('height_cm') or student_profile.height_cm or None
            
            if weight and (not student_profile.weight_kg or float(weight) != student_profile.weight_kg):
                student_profile.weight_kg = weight
            if height and (not student_profile.height_cm or float(height) != student_profile.height_cm):
                student_profile.height_cm = height
            student_profile.save()

            score, label = predict_health(hr, spo2, br, temp, weight, height)

            VitalRecord.objects.create(
                student=student_profile,
                heart_rate=hr,
                spo2=spo2,
                breathing_rate=br,
                temperature_c=temp,
                weight_kg=weight,
                height_cm=height,
                prediction_score=score,
                prediction_label=label
            )

            return render(request, 'classroom/quick_check.html', {
                'vc': vc,
                'student': student_profile,
                'idx': idx,
                'total': total_students,
                'prediction_label': label,
                'prediction_score': score,
            })

    return render(request, 'classroom/quick_check.html', {
        'vc': vc,
        'student': student_profile,
        'idx': idx,
        'total': total_students
    })


@login_required
def view_student_history(request, student_id):
    if not request.user.is_teacher:
        return redirect('home')

    student = get_object_or_404(StudentProfile, id=student_id, user__school=request.user.school)
    
    vitals_qs = student.vitals.all().order_by('recorded_at')
    
    line_chart_data = {
        "labels": [v.recorded_at.strftime("%d %b %H:%M") for v in vitals_qs],
        "hr_data": [v.heart_rate for v in vitals_qs],
        "spo2_data": [v.spo2 for v in vitals_qs],
        "temp_data": [v.temperature_c for v in vitals_qs],
    }
    
    context = {
        'profile': student,
        'vitals': vitals_qs.reverse(),
        'line_chart_data_json': json.dumps(line_chart_data)
    }
    return render(request, 'classroom/student_history.html', context)


@login_required
def delete_classroom(request, pk):
    if not request.user.is_teacher:
        return redirect('home')
    
    vc = get_object_or_404(VirtualClassroom, id=pk, teacher=request.user)
    
    if request.method == 'POST':
        class_name = vc.class_name
        section = vc.section
        vc.delete()
        messages.success(request, f"Class {class_name}-{section} has been permanently deleted.")
        # --- FIXED REDIRECT ---
        return redirect('health:teacher_dashboard')
    
    messages.error(request, "Invalid request.")
    # --- FIXED REDIRECT ---
    return redirect('health:teacher_dashboard')