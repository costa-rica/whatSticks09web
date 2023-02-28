from flask import Blueprint
from flask import render_template, url_for, redirect, flash, request, \
    abort, session, Response, current_app, send_from_directory, make_response
import os
import logging
from logging.handlers import RotatingFileHandler

from flask_login import login_required, login_user, logout_user, current_user
from ws09_models import sess, Base,engine, Users, login_manager, Oura_token, Locations, \
    Weather_history, User_location_day, Oura_sleep_descriptions, communityposts, communitycomments, newsposts, newscomments, \
    Apple_health_export, User_notes


main = Blueprint('main', __name__)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

logger_main = logging.getLogger(__name__)
logger_main.setLevel(logging.DEBUG)

file_handler = RotatingFileHandler(os.path.join(os.environ.get('PROJ_ROOT_PATH'),'logs','main_routes.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

logger_main.addHandler(file_handler)
logger_main.addHandler(stream_handler)


@main.route("/", methods=["GET","POST"])
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dash.dashboard', dash_dependent_var='steps'))

    latest_post = sess.query(communityposts).all()
    print("--- latest communith posts ---")
    print(latest_post)
    # latest_post = ""
    if len(latest_post) > 0:
        latest_post = latest_post[-1]

        blog = {}
        keys = latest_post.__table__.columns.keys()
        blog = {key: getattr(latest_post, key) for key in keys}
        # blog['blog_name']='blog'+str(latest_post.id).zfill(4)
        blog['blog_name'] = latest_post.blog_id_name_string
        blog['date_published'] = blog['date_published'].strftime("%b %d %Y")
    else:
        blog =''

    return render_template('main/home.html', blog=blog)

@main.route('/login', methods = ['GET', 'POST'])
def login():
    print('* in login *')
    # if current_user.is_authenticated:
    #     return redirect(url_for('dash.dashboard', dash_dependent_var='steps'))
    page_name = 'Login'
    if request.method == 'POST':
        formDict = request.form.to_dict()

        email = formDict.get('email')

        user = sess.query(Users).filter_by(email=email).first()

        # verify password using hash
        password = formDict.get('password_text')

        if user:
            if password:
                if bcrypt.checkpw(password.encode(), user.password):
                    login_user(user)

                    return redirect(url_for('dash.dashboard', dash_dependent_var='steps'))
                else:
                    flash('Password or email incorrectly entered', 'warning')
            else:
                flash('Must enter password', 'warning')
        elif formDict.get('btn_login_as_guest'):
            user = sess.query(Users).filter_by(id=2).first()
            login_user(user)

            return redirect(url_for('dash.dashboard', dash_dependent_var='steps'))
        else:
            flash('No user by that name', 'warning')


    return render_template('main/login.html', page_name = page_name)


@main.route('/about_us')
def about_us():
    page_name = 'About us'
    return render_template('main/about_us.html', page_name = page_name)

@main.route('/privacy')
def privacy():
    page_name = 'Privacy'
    return render_template('main/privacy.html', page_name = page_name)