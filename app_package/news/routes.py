from flask import Blueprint
from flask import render_template, url_for, redirect, flash, request,current_app
import os
from datetime import datetime
import time
from sqlalchemy import func
import json
from flask_login import login_user, current_user, logout_user, login_required

from app_package.news.utils import create_new_html_text, get_title, save_post_html, save_post_images, \
    build_comment_dict

from ws09_models import sess, Users, communityposts, communitycomments, newsposts, newscomments

from sqlalchemy import func 
import shutil
import logging
from logging.handlers import RotatingFileHandler
import zipfile
from werkzeug.utils import secure_filename



#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

#initialize a logger
logger_news = logging.getLogger(__name__)
logger_news.setLevel(logging.DEBUG)


#where do we store logging information
file_handler = RotatingFileHandler(os.path.join(os.environ.get('WEB_ROOT'),"logs",'news_routes.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

#where the stream_handler will print
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

# logger_sched.handlers.clear() #<--- This was useful somewhere for duplicate logs
logger_news.addHandler(file_handler)
logger_news.addHandler(stream_handler)

news = Blueprint('news', __name__)
    
@news.route("/news", methods=["GET"])
def posts_index():

    #make sure word doc folder exits with in static folder
    # word_docs_dir_util()

    #sorted list of published dates
    date_pub_list=[i.date_published for i in sess.query(newsposts).all()]
    # create new list of sorted datetimes into increasing order
    sorted_date_pub_list = sorted(date_pub_list)
    #reverse new list
    sorted_date_pub_list.sort(reverse=True)

    #make dict of title, date_published, description
    items=['title', 'description','date_published' ]
    posts_list = sess.query(newsposts).all()
    post_dict_for_index_sorted={}
    for i in sorted_date_pub_list:
        for post in posts_list:
            if post.date_published == i:
                # temp_dict={key: (getattr(post,key) if key!='date_published' else getattr(post,key).strftime("%b %d %Y") ) for key in items}
                temp_dict = {key: getattr(post, key) for key in items}
                temp_dict['date_published'] = temp_dict['date_published'].strftime("%-d %b %Y")
                # temp_dict={key: getattr(post,key)  for key in items}
                temp_dict['post_name']=post.post_id_name_string
                temp_dict['username'] = sess.query(Users).filter_by(id = post.user_id).first().username
                # temp_dict={key: (getattr(post,key) if key=='date_published' else getattr(post,key)[:9] ) for key in items}
                post_dict_for_index_sorted[post.id]=temp_dict
                posts_list.remove(post)

    return render_template('news/index.html', post_dicts_for_index=post_dict_for_index_sorted)


@news.route("/news/<post_name>", methods=["GET","POST"])
def view_post(post_name):

    post_html = "news/posts/" + post_name + ".html"

    post=sess.query(newsposts).filter_by(post_id_name_string=post_name).first()
    post_date = post.date_published.strftime("%-d %B %Y")
    post_username = sess.query(Users).filter_by(id = post.user_id).first().username

    # get comments
    comments_query_list = sess.query(newscomments).filter_by(post_id=post.id).all()

    comments_list = build_comment_dict(comments_query_list)



    if request.method == 'POST':
        formDict = request.form.to_dict()
        print("formDict: ", formDict)
        if current_user.guest_account == True:
            flash('Guest cannot edit data.', 'info')
            return redirect(url_for(request.url,post_name=post_name))
        
        elif formDict.get('submit_comment_add'):
            new_comment = newscomments(user_id=current_user.id, post_id=post.id, comment=formDict.get('comment'))
            sess.add(new_comment)
            sess.commit()
            flash("Comment successfully added!", "success")
            return redirect(url_for(request.url,post_name=post_name))
        
        elif formDict.get('delete_comment'):
            comment_id_to_delete = formDict.get('delete_comment')
            sess.query(newscomments).filter_by(id=int(comment_id_to_delete)).delete()
            sess.commit()
            flash(f"Deleted comment id: {comment_id_to_delete}", "warning")
            return redirect(url_for(request.url,post_name=post_name))


    return render_template('news/view_post.html', post_html=post_html, post_date=post_date, post_username=post_username,
        comments_list = comments_list)


@news.route("/create_post", methods=["GET","POST"])
@login_required
def create_post():
    if not current_user.post_blog_permission:
        return redirect(url_for('news.post_index'))

    logger_news.info(f"- user has news post permission -")

    if request.method == 'POST' and 'post_html_file' in request.files:
        print("** are we posting an article? **")
        formDict = request.form.to_dict()
        post_html_file = request.files.get('post_html_file')
        post_images_zip = request.files.get('post_images_zip')
        post_html_filename = post_html_file.filename

        logger_news.info(f"- filename is {post_html_filename} -")

        file_path_str_to_templates_news_posts = os.path.join(current_app.config.root_path,"templates","news","posts")
                
        #check if templates/blog/posts exists
        if not os.path.exists(file_path_str_to_templates_news_posts):
            logger_news.info(f"- making templates/news/posts dir -")
            os.mkdir(file_path_str_to_templates_news_posts)


        # check if file name already uploaded:
        existing_file_names_list = [i.name for i in os.scandir(file_path_str_to_templates_news_posts)]
        if post_html_filename in existing_file_names_list:
            flash('A file with the same name has already been saved. Change file name and try again.', 'warning')
            return redirect(request.url)

        # Save blog_post_html to templates/blog/posts/
        post_id_name_string, blog_post_new_name = save_post_html(formDict, post_html_file, 
                                file_path_str_to_templates_news_posts, post_html_filename)

        # Save images to static/images/blog/000id/ <-- if there is a filename
        if post_images_zip.filename != "":
            logger_news.info(f"- post_images_zip is not None -")

            save_post_images(post_images_zip, post_id_name_string, blog_post_new_name)


        flash(f'Post added successfully!', 'success')

    return render_template('news/create_post.html')


@news.route("/news_user_home", methods=["GET","POST"])
@login_required
def news_user_home():
    print('--- In blog_user home ----')
    logger_news.info(f"- In blog_user_home -")

    if not current_user.post_news_permission:
        return redirect(url_for('blog.post_index'))


    #check, create directories between db/ and static/
    # word_docs_dir_util()

    all_my_posts=sess.query(newsposts).filter_by(user_id=current_user.id).all()
    # print(all_posts)
    posts_details_list=[]
    for i in all_my_posts:
        posts_details_list.append([i.id, i.title, i.date_published.strftime("%m/%d/%Y"),
            i.description, i.post_html_filename])
    
    column_names=['id', 'blog_title', 'delete','date_published',
         'blog_description','word_doc']

    if request.method == 'POST':
        formDict=request.form.to_dict()
        print('formDict::', formDict)
        if formDict.get('delete_record_id')!='':
            post_id=formDict.get('delete_record_id')
            print(post_id)

            return redirect(url_for('news.news_delete', post_id=post_id))

    return render_template('news/user_home.html', posts_details_list=posts_details_list, len=len,
        column_names=column_names)

