from django.core.mail import send_mail
from django.conf import settings

def send_teacher_otp_email(user):
    otp = user.generate_otp()
    subject = "🔐 Rakshara Teacher Login OTP Verification"
    message = f"Hello {user.username},\n\nYour One-Time Password (OTP) is: {otp}\n\nThis code is valid for 5 minutes.\n\n- Rakshara Security Team"
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
