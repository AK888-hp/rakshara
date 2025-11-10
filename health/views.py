from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import VitalRecord
from accounts.models import StudentProfile, TeacherProfile
from .utils import predict_health


# 🩺 ADD VITAL RECORD
@login_required
def add_vital_record(request, student_code=None):
    user = request.user
    if user.is_student:
        student_profile = user.student_profile
    else:
        if student_code:
            student_profile = get_object_or_404(StudentProfile, student_code=student_code)
        else:
            messages.error(request, "No student selected.")
            return redirect('teacher_dashboard')

    if request.method == 'POST':
        hr = int(request.POST.get('heart_rate'))
        spo2 = float(request.POST.get('spo2'))
        br = float(request.POST.get('breathing_rate'))
        temp = float(request.POST.get('temperature'))
        weight = request.POST.get('weight_kg') or student_profile.weight_kg
        height = request.POST.get('height_cm') or student_profile.height_cm

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

        # ✅ Return template with popup instead of redirect
        return render(request, 'health/add_vital.html', {
            'student': student_profile,
            'prediction_label': label,
            'prediction_score': score,
        })

    return render(request, 'health/add_vital.html', {'student': student_profile})

# 📊 STUDENT DASHBOARD
@login_required
def student_dashboard(request):
    """Displays student's health summary, charts, and recent records."""
    if not request.user.is_student:
        return redirect('teacher_dashboard')

    profile = request.user.student_profile

    # ✅ Query ordered vitals properly
    vitals_qs = profile.vitals.all().order_by('-recorded_at')
    latest_vital = vitals_qs.first()  # Safe latest record
    vitals = list(vitals_qs[:30])     # Recent 30 records

    # Prepare data for chart (reverse for chronological order)
    labels = [v.recorded_at.strftime("%d %b %H:%M") for v in reversed(vitals)]
    hr_data = [v.heart_rate for v in reversed(vitals)]
    spo2_data = [v.spo2 for v in reversed(vitals)]
    temp_data = [v.temperature_c for v in reversed(vitals)]

    return render(request, 'health/student_dashboard.html', {
        'profile': profile,
        'vitals': vitals,
        'latest_vital': latest_vital,
        'labels': labels,
        'hr_data': hr_data,
        'spo2_data': spo2_data,
        'temp_data': temp_data
    })


# 🧑‍🏫 TEACHER DASHBOARD
@login_required
def teacher_dashboard(request):
    """Teacher view of all students and quick vital submissions."""
    teacher = get_object_or_404(TeacherProfile, user=request.user)
    school = teacher.user.school

    # All students in teacher's school
    students = StudentProfile.objects.filter(user__school=school).order_by('class_name', 'section', 'roll_no')

    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        try:
            student = StudentProfile.objects.get(id=student_id)
            hr = float(request.POST.get('heart_rate'))
            spo2 = float(request.POST.get('spo2'))
            br = float(request.POST.get('breathing_rate'))
            temp = float(request.POST.get('temperature'))

            score, label = predict_health(hr, spo2, br, temp, student.weight_kg, student.height_cm)

            VitalRecord.objects.create(
                student=student,
                heart_rate=hr,
                spo2=spo2,
                breathing_rate=br,
                temperature_c=temp,
                prediction_score=score,
                prediction_label=label
            )
            messages.success(request, f"✅ Vitals added for {student.user.username}")
        except StudentProfile.DoesNotExist:
            messages.error(request, "❌ Student not found.")
        except ValueError:
            messages.error(request, "Invalid input values.")

        return redirect('teacher_dashboard')

    context = {
        'teacher': teacher,
        'students': students,
    }
    return render(request, 'health/teacher_dashboard.html', context)
