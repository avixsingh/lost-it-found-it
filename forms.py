from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import (DataRequired, Email, EqualTo, Length, Optional,
                                Regexp, ValidationError)

from ..models import User

PHONE_RULE = Regexp(r"^[0-9+\-\s]{7,20}$", message="Enter a valid phone number.")


class RegistrationForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(2, 100)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    # Only student and faculty may be chosen publicly. Admin is never offered.
    role = SelectField("I am a", choices=[("student", "Student"), ("faculty", "Faculty")])
    department = StringField("Department / Course", validators=[Optional(), Length(max=100)])
    password = PasswordField("Password", validators=[DataRequired(), Length(8, 64)])
    confirm = PasswordField("Confirm password",
                            validators=[DataRequired(), EqualTo("password", "Passwords must match.")])
    submit = SubmitField("Create account")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("This email is already registered.")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")


class ProfileForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(2, 100)])
    department = StringField("Department / Course", validators=[Optional(), Length(max=100)])
    phone = StringField("Phone", validators=[Optional(), PHONE_RULE])
    new_password = PasswordField("New password (optional)", validators=[Optional(), Length(8, 64)])
    confirm = PasswordField("Confirm new password",
                            validators=[EqualTo("new_password", "Passwords must match.")])
    submit = SubmitField("Save changes")
