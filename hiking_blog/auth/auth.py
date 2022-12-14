"""This file handles all user signup/login/logout activities of the application."""

from flask import Blueprint, render_template, redirect, flash, request, url_for, abort, current_app
from flask_login import login_required, logout_user, current_user, login_user
from functools import wraps
from hiking_blog.forms import SignUpForm, LoginForm, ChangePasswordForm, PasswordRecoveryForm, ChangeUsernameForm
from hiking_blog.login_manager import login_manager
from hiking_blog.db import db
from itsdangerous import URLSafeTimedSerializer
from hiking_blog.models import User
from hiking_blog.contact import send_password_reset_email
from better_profanity import profanity
from datetime import timedelta


DAYS_BEFORE_LOGOUT = timedelta(days=30)


auth_bp = Blueprint(
    "auth_bp", __name__,
    template_folder="templates",
    static_folder="static"
)


@auth_bp.route("/auth/login", methods=["GET", "POST"])
def login():
    """
    Allows the user to enter their username and password to login.

    Checks if the user is already logged in (if so, user is redirected to homepage). Then, runs a function to check the
    login info provided on the form is valid (redirecting if it's not). Finally, logs the user in and sends them to
    whatever page they were on when prompted for their login info.
    """

    if current_user.is_authenticated:
        flash("You are already logged in.")
        return redirect(url_for('home_bp.home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        message, reroute = check_login(form, user)
        if message is not None:
            flash(message)
            return reroute
        login_user(user, remember=True, duration=DAYS_BEFORE_LOGOUT)
        next_page = request.args.get("next")
        return redirect(next_page or url_for("home_bp.home"))
    return render_template("form_page.html",
                           form=form,
                           logged_in=current_user.is_authenticated,
                           form_header="Sign in.",
                           form_sub_header="Input your username and password to log in to your profile.",
                           above_button_text="Not yet a member?",
                           button_text="Sign Up!",
                           url_link="auth_bp.sign_up",
                           above_button_text_two="Forgot your username or password?",
                           button_text_two="Click here.",
                           url_link_two="auth_bp.password_recovery"
                           )


@auth_bp.route("/auth/sign_up", methods=["GET", "POST"])
def sign_up():
    """
    Allows a user without membership to the site to become a member.

    Get request sends user to the form page to sign up. A post request runs a function to confirm the user is not
    already a member and that their passwords match, then runs a separate function that creates a new user entry
    in the database before redirecting them to the homepage.
    """
    form = SignUpForm()
    if form.validate_on_submit():
        admin, message, reroute = check_signup(form)
        if message is not None:
            flash(message)
            return reroute
        create_new_user(form, admin)
        return redirect(url_for("home_bp.home"))
    return render_template("form_page.html",
                           form=form,
                           logged_in=current_user.is_authenticated,
                           form_header="Sign up today!",
                           form_sub_header="Fill out this form to join!")


@auth_bp.route("/auth/password_recovery", methods=["GET", "POST"])
def password_recovery():
    """Allows user to submit their username to be used in resetting a forgotten password."""
    form = PasswordRecoveryForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        send_password_reset_email(user.email)
        return render_template("check_email.html")
    return render_template("form_page.html",
                           form=form,
                           form_header="Forgot Password?",
                           form_sub_header="Enter your username to reset your password.",
                           above_button_text="If you've forgotten your username",
                           button_text="click here.",
                           url_link="contact_bp.username_recovery"
                           )


@auth_bp.route("/auth/reset/<token>", methods=["GET", "POST"])
def reset_with_token(token):
    """
    # -----------------------------------------Needs Docstring------------------------------------------------

    :param token:
    :return:
    """
    # ------------------------------------Needs to be broken up-------------------------------------------
    try:
        password_reset_serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        email = password_reset_serializer.loads(token, salt='pw-reset-salt', max_age=3000)
    except:
        message = "The password reset link is invalid or expired"
        flash(message, 'danger')
        return redirect(url_for('auth_bp.login'))
    try:
        user = User.query.filter_by(email=email).first()
    except:
        message = "Invalid email address!"
        flash(message, 'danger')
        return redirect(url_for('auth_bp.login'))
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if form.new_password.data != form.verify_password.data:
            flash("Passwords do not match!")
            return redirect(url_for("auth_bp.reset_with_token", token=token))
        user.set_password(form.new_password.data)
        db.session.commit()
        message = "Your password has been updated!"
        flash(message, 'Success! You may now log in with your new password.')
        return redirect(url_for('auth_bp.login'))
    return render_template("form_page.html",
                           form=form,
                           h_two="Reset your password.",
                           p_tag="Enter your new password below:")


def change_password(email):
    """Allows user to change their password."""
#     ----------------------------------------------Reserved for above breakdown------------------------------------
    pass


@auth_bp.route("/auth/reset_username/<user_id>", methods=["GET", "POST"])
def reset_username(user_id):
    """Allows the user to reset their username."""
    user = User.query.get(user_id)
    form = ChangeUsernameForm()
    if form.validate_on_submit():
        user.username = form.username.data
        user.username_needs_verification = True
        db.session.commit()
        message = "Your username has been updated!"
        flash(message, "Success! You may now log in with your new username.")
        return redirect(url_for('auth_bp.login'))
    return render_template("form_page.html",
                           form=form,
                           h_two="Reset your username.",
                           p_tag="Enter your new username below:")


@auth_bp.route("/auth/logout")
@login_required
def logout():
    """Logs the user out and redirects them to the home page."""
    logout_user()
    return redirect(url_for("home_bp.home"))


@login_manager.user_loader
def load_user(user_id):
    """
    Tells flask-login how to load users given an id.

    Parameters
    ----------
    user_id : int
        The primary key from the users table in the database that corresponds to the current user.
    """

    if user_id is not None:
        return User.query.get(user_id)
    return None


@login_manager.unauthorized_handler
def unauthorized():
    """Flashes a message to a logged-out user attempting to access a page only viewable by logged-in users."""
    flash("You must be logged in to view that page")
    return redirect(url_for("auth_bp.login"))


def create_new_user(form, admin):
    """Creates a new user entry in the database."""
    new_user = User(
        username=form.username.data,
        email=form.email.data,
        is_admin=admin,
        email_confirmed=False,
        username_approved=False,
        username_needs_verification=True
    )
    new_user.set_password(form.password.data)
    db.session.add(new_user)
    db.session.commit()
    login_user(new_user)


def check_signup(form):
    """
    Confirms that the user provided sign up info is valid.

    Assigns the admin value for the would-be new user to False UNLESS it is the first user. Then, checks for validity
    of user-entered-info, returning a flash message and redirect if invalid or if username includes profanity.
    """

    message = None
    reroute = None
    admin = False
    all_users = User.query.all()
    if not all_users:
        admin = True
    if User.query.filter_by(username=form.username.data).first():
        message = "You've already signed up!"
        reroute = redirect(url_for("auth_bp.login"))
    if form.password.data != form.verify_password.data:
        message = "Passwords Must Match"
        reroute = redirect(url_for("auth_bp.sign_up"))
    if profanity.contains_profanity(form.username.data):
        print(profanity.censor(form.username.data))
        message = "Username may not contain profanity."
        reroute = redirect(url_for("auth_bp.sign_up"))
    return admin, message, reroute


def check_login(form, user):
    """Checks user-entered-login info for validity."""
    message = None
    reroute = None
    if not user:
        message = "That username does not exist. Please try again."
        reroute = redirect(url_for("auth_bp.login"))
        return message, reroute
    if not user.check_password(password=form.password.data):
        message = "Password incorrect. Please Try again."
        form.username.data = user.username
        reroute = redirect(url_for("auth_bp.login"))
    return message, reroute


def admin_only(f):
    """
    A wrapper for functions throughout this application that require a user be logged in before they run.

    Parameters
    ----------
    f : function()
        The function being wrapped by admin_only.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function
