from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import User
from .forms import LoginForm, ProfileForm, RegistrationForm

bp = Blueprint("auth", __name__)


def _safe_next(target):
    """Only allow redirects to relative paths on this site (prevents open redirect)."""
    if target and target.startswith("/") and not target.startswith("//") \
            and not urlparse(target).netloc:
        return target
    return None


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = RegistrationForm()
    if form.validate_on_submit():
        role = form.role.data if form.role.data in ("student", "faculty") else "student"
        user = User(name=form.name.data.strip(), email=form.email.data.strip().lower(),
                    role=role, department=(form.department.data or "").strip() or None)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Account created. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user is None or not user.check_password(form.password.data):
            flash("Invalid email or password.", "danger")
        elif not user.is_active_account:
            flash("This account has been suspended. Contact the administrator.", "danger")
        else:
            login_user(user)
            nxt = _safe_next(request.args.get("next"))
            if nxt:
                return redirect(nxt)
            return redirect(url_for("admin.dashboard" if user.is_admin else "main.dashboard"))
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.name = form.name.data.strip()
        current_user.department = (form.department.data or "").strip() or None
        current_user.phone = (form.phone.data or "").strip() or None
        if form.new_password.data:
            current_user.set_password(form.new_password.data)
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html", form=form)
