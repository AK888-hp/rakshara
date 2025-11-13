# accounts/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, StudentProfile, TeacherProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    This signal creates a new profile *only when a new user is created*.
    """
    if created: # <-- This check is critical
        if instance.is_student:
            StudentProfile.objects.create(user=instance)
        elif instance.is_teacher:
            TeacherProfile.objects.create(user=instance)

# The @receiver line that was accidentally pasted inside the function
# has been removed, fixing the TypeError.