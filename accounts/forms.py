from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, School, StudentProfile

class StudentSignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    dob = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    height_cm = forms.FloatField(required=False)
    weight_kg = forms.FloatField(required=False)
    personal_contact = forms.CharField(required=False)
    parent_contact = forms.CharField(required=False)
    address = forms.CharField(widget=forms.Textarea, required=False)
    school = forms.ModelChoiceField(queryset=School.objects.all(), required=True)
    roll_no = forms.CharField(required=True)
    class_name = forms.CharField(required=True)
    section = forms.CharField(required=True)
    
    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2",
                  "roll_no", "dob", "height_cm", "weight_kg", "personal_contact",
                  "parent_contact", "address", "school", "class_name", "section",
                  "image") # <-- And add 'image' here


class TeacherSignUpForm(UserCreationForm):
    # ... (This form is unchanged)
    email = forms.EmailField(required=True)
    contact = forms.CharField(required=False)
    address = forms.CharField(widget=forms.Textarea, required=False)
    school = forms.ModelChoiceField(queryset=School.objects.all(), required=True)
    verification_id = forms.CharField(required=True, help_text="Enter school verification id provided by admin")

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2", "school", "verification_id", "contact", "address")


# --- ADD THIS NEW FORM FOR EDITING PROFILES ---
class StudentProfileEditForm(forms.ModelForm):
    # These fields are on the User model
    username = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    
    # These fields are on the StudentProfile model
    class Meta:
        model = StudentProfile
        fields = [
            'roll_no', 'dob', 'height_cm', 'weight_kg', 
            'personal_contact', 'parent_contact', 'address', 'class_name', 'section'
        ]
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate the form with the user's current username and email
        if self.instance and self.instance.user:
            self.fields['username'].initial = self.instance.user.username
            self.fields['email'].initial = self.instance.user.email

    def save(self, *args, **kwargs):
        # Save the User model fields
        user = self.instance.user
        user.username = self.cleaned_data['username']
        user.email = self.cleaned_data['email']
        user.save()
        # Save the StudentProfile model fields
        return super().save(*args, **kwargs)