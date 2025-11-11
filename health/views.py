# health/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse

from classroom.models import VirtualClassroom
from .models import VitalRecord
from accounts.models import StudentProfile, TeacherProfile, Notification, JoinRequest
from ai_engine.utils import predict_health
from ai_engine.translate import get_translated_text

# --- UPDATED IMPORTS ---
from django.db.models import Avg, Prefetch
# --- END UPDATED IMPORTS ---


# 🩺 ADD VITAL RECORD
@login_required
def add_vital_record(request, student_code=None):
    # ... (this view is unchanged)
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

        return render(request, 'health/add_vital.html', {
            'student': student_profile,
            'prediction_label': label,
            'prediction_score': score,
        })

    return render(request, 'health/add_vital.html', {'student': student_profile})


# 📊 STUDENT DASHBOARD
@login_required
def student_dashboard(request):
    # ... (this view is unchanged)
    if not request.user.is_student:
        return redirect('teacher_dashboard')

    profile = request.user.student_profile
    vitals_qs = profile.vitals.all().order_by('-recorded_at')
    latest_vital = vitals_qs.first()
    vitals = list(vitals_qs[:30])

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


# 🧑‍🏫 TEACHER DASHBOARD (UPDATED TO FIX SQLITE ERROR)
@login_required
def teacher_dashboard(request):
    teacher = request.user
    school = getattr(teacher, 'school', None)

    if not getattr(teacher, "is_teacher", False):
        messages.error(request, "Access denied: only teachers can access this page.")
        return redirect('student_dashboard')
        
    if not school:
        messages.error(request, 'You are not assigned to any school. Please contact admin.')
        return render(request, 'health/teacher_dashboard.html', {'my_classes': []}) # Use my_classes

    # --- Handle new class creation ---
    if request.method == 'POST':
        class_name = request.POST.get('class_name')
        section = request.POST.get('section')

        if VirtualClassroom.objects.filter(school=school, class_name=class_name, section=section).exists():
            messages.warning(request, f"Class {class_name}-{section} already exists.")
        else:
            vc = VirtualClassroom.objects.create(
                school=school,
                teacher=teacher,
                class_name=class_name,
                section=section
            )
            messages.success(request, f"Class {vc.class_name}-{vc.section} created successfully!")
        return redirect('teacher_dashboard')

    # --- Get Teacher-Specific Data ---
    notifications = Notification.objects.filter(teacher=teacher).order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    Notification.objects.filter(teacher=teacher, is_read=False).update(is_read=True)

    my_classes = VirtualClassroom.objects.filter(teacher=teacher)
    for c in my_classes:
        c.student_count = c.students.count()

    pending_requests = JoinRequest.objects.filter(
        teacher=teacher, approved=False
    ).select_related('student__user')

    # --- NEW: Top 3 Classes (Podium) - SQLITE COMPATIBLE ---

    # 1. Prefetch the latest vital for ALL students in the school
    latest_vitals_prefetch = Prefetch(
        'vitals',
        queryset=VitalRecord.objects.order_by('-recorded_at'),
        to_attr='vitals_list' # Store in a temporary attribute
    )
    all_students_in_school = StudentProfile.objects.filter(
        user__school=school
    ).prefetch_related(latest_vitals_prefetch)

    # 2. Create a fast lookup map of {student_id: latest_score}
    student_scores_map = {}
    for student in all_students_in_school:
        if student.vitals_list: # Check if the student has any vitals
            student_scores_map[student.id] = student.vitals_list[0].prediction_score

    # 3. Get all classes and their associated students
    all_school_classes = VirtualClassroom.objects.filter(
        school=school
    ).prefetch_related('students') # prefetch_related is very fast

    # 4. Calculate average scores in Python (avoids complex DB query)
    class_rankings = []
    for vc in all_school_classes:
        class_scores = []
        # vc.students.all() is fast because of the prefetch_related
        for student in vc.students.all(): 
            if student.id in student_scores_map:
                class_scores.append(student_scores_map[student.id])
        
        if class_scores:
            # Only rank classes that have at least one student with a score
            avg_score = sum(class_scores) / len(class_scores)
            class_rankings.append({
                'vc': vc,
                'avg_risk_score': avg_score
            })

    # 5. Sort the classes by score (lowest is best)
    class_rankings.sort(key=lambda x: x['avg_risk_score'])

    # 6. Format for the podium (Top 3)
    top_classes = []
    for rank, item in enumerate(class_rankings[:3], 1):
        top_classes.append({
            'rank': rank,
            'name': f"{item['vc'].class_name}-{item['vc'].section}",
            'teacher': item['vc'].teacher.get_full_name() or item['vc'].teacher.username,
            'score': round(item['avg_risk_score'], 1)
        })
    
    # --- END OF NEW LOGIC ---

    context = {
        'my_classes': my_classes,
        'notifications': notifications,
        'unread_count': unread_count,
        'pending_requests': pending_requests,
        'top_classes': top_classes,
    }
    return render(request, 'health/teacher_dashboard.html', context)