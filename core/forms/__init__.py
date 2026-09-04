from core.forms.auth import (
    RegisterForm,
    LoginForm,
    PasswordChangeForm,
    PasswordResetRequestForm,
    PasswordResetForm,
    OTPForm,
)
from core.forms.profile import ProfileForm, WithdrawalInfoForm, ProfilePictureForm
from core.forms.setting import SettingForm

__all__ = [
    'RegisterForm',
    'LoginForm',
    'PasswordChangeForm',
    'PasswordResetRequestForm',
    'PasswordResetForm',
    'OTPForm',
    'ProfileForm',
    'WithdrawalInfoForm',
    'ProfilePictureForm',
    'SettingForm',
]
