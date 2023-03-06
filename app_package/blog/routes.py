from flask import Blueprint
from flask import render_template, url_for, redirect, flash, request,current_app
import os
from datetime import datetime
import time
from sqlalchemy import func
import json
from flask_login import login_user, current_user, logout_user, login_required
# from app_package.blog.forms import BlogPostForm
from app_package.blog.utils import create_new_html_text, get_title, save_post_html, save_post_images
# last_first_list_util, wordToJson, \
#     word_docs_dir_util
from ws09_models import sess, Users, communityposts, communitycomments, newsposts, newscomments
# from app_package import db
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
logger_blog = logging.getLogger(__name__)
logger_blog.setLevel(logging.DEBUG)


#where do we store logging information
file_handler = RotatingFileHandler(os.path.join(os.environ.get('WS_ROOT_WEB'),"logs",'blog_routes.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

#where the stream_handler will print
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

# logger_sched.handlers.clear() #<--- This was useful somewhere for duplicate logs
logger_blog.addHandler(file_handler)
logger_blog.addHandler(stream_handler)

blog = Blueprint('blog', __name__)
    
@blog.route("/blog", methods=["GET"])
def blog_index():

    #make sure word doc folder exits with in static folder
    # word_docs_dir_util()

    #sorted list of published dates
    date_pub_list=[i.date_published for i in sess.query(communityposts).all()]
    # create new list of sorted datetimes into increasing order
    sorted_date_pub_list = sorted(date_pub_list)
    #reverse new list
    sorted_date_pub_list.sort(reverse=True)

    #make dict of title, date_published, description
    items=['title', 'description','date_published' ]
    posts_list = sess.query(communityposts).all()
    blog_dict_for_index_sorted={}
    for i in sorted_date_pub_list:
        for post in posts_list:
            if post.date_published == i:
                # temp_dict={key: (getattr(post,key) if key!='date_published' else getattr(post,key).strftime("%b %d %Y") ) for key in items}
                temp_dict = {key: getattr(post, key) for key in items}
                temp_dict['date_published'] = temp_dict['date_published'].strftime("%b %d %Y")
                # temp_dict={key: getattr(post,key)  for key in items}
                temp_dict['blog_name']=post.blog_id_name_string
                # temp_dict={key: (getattr(post,key) if key=='date_published' else getattr(post,key)[:9] ) for key in items}
                blog_dict_for_index_sorted[post.id]=temp_dict
                posts_list.remove(post)

    return render_template('blog/index.html', blog_dicts_for_index=blog_dict_for_index_sorted)


@blog.route("/blog/<blog_name>", methods=["GET"])
def blog_template(blog_name):

    post_html = "blog/posts/" + blog_name + ".html"

    post=sess.query(communityposts).filter_by(blog_id_name_string=blog_name).first()
    date = post.date_published.strftime("%m/%d/%Y")

    return render_template('blog/template.html', post_html=post_html, date=date)


@blog.route("/post", methods=["GET","POST"])
@login_required
def blog_post():
    if not current_user.post_blog_permission:
        return redirect(url_for('blog.blog_index'))

    logger_blog.info(f"- user has blog post permission -")

    if request.method == 'POST' and 'post_html_file' in request.files:
        print("** are we posting an article? **")
        formDict = request.form.to_dict()
        post_html_file = request.files.get('post_html_file')
        post_images_zip = request.files.get('post_images_zip')
        post_html_filename = post_html_file.filename

        logger_blog.info(f"- filename is {post_html_filename} -")

        file_path_str_to_templates_blog_posts = os.path.join(current_app.config.root_path,"templates","blog","posts")
                
        #check if templates/blog/posts exists
        if not os.path.exists(file_path_str_to_templates_blog_posts):
            logger_dash.info(f"- making templates/blog/posts dir -")
            os.mkdir(file_path_str_to_templates_blog_posts)


        # check if file name already uploaded:
        existing_file_names_list = [i.name for i in os.scandir(file_path_str_to_templates_blog_posts)]
        if post_html_filename in existing_file_names_list:
            flash('A file with the same name has already been saved. Change file name and try again.', 'warning')
            return redirect(request.url)

        # Save blog_post_html to templates/blog/posts/
        blog_id_name_string, blog_post_new_name = save_post_html(formDict, post_html_file, 
                                file_path_str_to_templates_blog_posts, post_html_filename)

        # Save images to static/images/blog/000id/ <-- if there is a filename
        if post_images_zip.filename != "":
            logger_blog.info(f"- post_images_zip is not None -")

            save_post_images(post_images_zip, blog_id_name_string, blog_post_new_name)


        flash(f'Post added successfully!', 'success')

    return render_template('blog/post.html')


@blog.route("/blog_user_home", methods=["GET","POST"])
@login_required
def blog_user_home():
    print('--- In blog_user home ----')
    logger_blog.info(f"- In blog_user_home -")

    if not current_user.post_blog_permission:
        return redirect(url_for('blog.blog_index'))


    #check, create directories between db/ and static/
    # word_docs_dir_util()

    all_my_posts=sess.query(communityposts).filter_by(user_id=current_user.id).all()
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

            return redirect(url_for('blog.blog_delete', post_id=post_id))
    #     elif formDict.get('edit_post_button')!='':
    #         print('post to delte:::', formDict.get('edit_post_button')[9:],'length:::', len(formDict.get('edit_post_button')[9:]))
    #         post_id=int(formDict.get('edit_post_button')[10:])
    #         return redirect(url_for('blog.blog_edit', post_id=post_id))
    return render_template('blog/user_home.html', posts_details_list=posts_details_list, len=len,
        column_names=column_names)


@blog.route("/delete/<post_id>", methods=['GET','POST'])
@login_required
def blog_delete(post_id):
    post_to_delete = sess.query(communityposts).get(int(post_id))

    if current_user.id != post_to_delete.user_id:
        return redirect(url_for('blog.blog_index'))
    logger_blog.info('-- In delete route --')
    logger_blog.info(f'post_id:: {post_id}')


    # delete word document in templates/blog/posts

    # delete images in static/images/communityposts

    # delete from database



    post_to_delete = sess.query(communityposts).get(int(post_id))
    logger_blog.info(f"--- name of blog file: {post_to_delete.blog_id_name_string }")
    # blog_name = 'blog'+post_id.zfill(4)
    # print(post_to_delete)
    
    # #delete word document
    # word_doc_path_database = current_app.config.get('WORD_DOC_DIR')

    try:# word doc from database folder
        file_path_str_to_templates_blog_posts = os.path.join(current_app.config.root_path,"templates","blog","posts")
        os.remove(os.path.join(file_path_str_to_templates_blog_posts, post_to_delete.blog_id_name_string + ".html"))
        # os.remove(os.path.join(word_doc_path_static, post_to_delete.word_doc))
    except:
        # logger_blog.info(f'no word document file exists')
        logger_blog.info('no word doucment file exists')
    
    #delete images folder
    try:# static folder
        shutil.rmtree(os.path.join(current_app.static_folder, 'images','communityposts', post_to_delete.blog_id_name_string))
    except:
        logger_blog.info(f'No {post_to_delete.blog_id_name_string} in static folder')

    # try:# database folder
    #     shutil.rmtree(os.path.join(current_app.config.get('WORD_DOC_DIR'),'blog_images', blog_name))
    # except:
    #     print(f'{blog_name} directory in database direcgtory does not exist')

    sess.query(communityposts).filter(communityposts.id==post_id).delete()
    # sess.query(Postshtml).filter(Postshtml.post_id==post_id).delete()
    # sess.query(Postshtmltagchars).filter(Postshtmltagchars.post_id==post_id).delete()
    sess.commit()
    flash(f'Post removed successfully!', 'success')
    return redirect(url_for('blog.blog_user_home'))


@blog.route("/edit", methods=['GET','POST'])
@login_required
def blog_edit():
    if current_user.id != 1:
        return redirect(url_for('blog.blog_index'))
    print('** Start blog edit **')
    post_id = int(request.args.get('post_id'))
    post = sess.query(Posts).filter_by(id = post_id).first()
    postHtml_list = sess.query(Postshtml).filter_by(post_id = post_id).all()[1:]
    published_date = post.date_published.strftime("%Y-%m-%d")

    # get list of word_row_id for post_id
    # put last object in first object's place
    merge_row_id_list = last_first_list_util(post_id)[1:]

    column_names = ['word_row_id', 'row_tag', 'row_going_into_html','merge_with_bottom']
    row_format_options = ['new lines','h1','h3', 'html', 'ul', 'ul and indent', 'indent',
        'image_title','image', 'codeblock','date_published']
    if request.method == 'POST':
        formDict=request.form.to_dict()
        # print('formDict::')
        # print(formDict)
        
        post.title = formDict.get('blog_title')
        post.description = formDict.get('blog_description')
        post.date_published = datetime.strptime(formDict.get('blog_pub_date'), '%Y-%m-%d')
        sess.commit()

        #update row_tag and row_going_into_html in Postshtml
        postHtml_update = sess.query(Postshtml).filter_by(post_id = post_id)
        
        #if title changed update first row psotHtml
        postHtml_title = postHtml_update.filter_by(word_row_id = 1).first()
        if post.title != postHtml_title.row_going_into_html:
            postHtml_title.row_going_into_html = post.title
            sess.commit()

        for i,j in formDict.items():
            
            if i.find('row_tag:'+str(post_id))>-1:
                word_row_id_temp = int(i[len('row_tag:'+str(post_id))+1:])
                update_row_temp=postHtml_update.filter_by(word_row_id = word_row_id_temp).first()
                update_row_temp.row_tag = j
                sess.commit()
            if i.find('row_html:'+str(post_id))>-1:
                word_row_id_temp = int(i[len('row_html:'+str(post_id))+1:])
                update_row_temp=postHtml_update.filter_by(word_row_id = word_row_id_temp).first()
                update_row_temp.row_going_into_html = j
                sess.commit()
        
        if formDict.get('delete_word_row'):
            row_to_delete = int(formDict.get('delete_word_row'))
            sess.query(Postshtml).filter_by(post_id = post_id,word_row_id = row_to_delete).delete()
            sess.query(Postshtmltagchars).filter_by(post_id = post_id,word_row_id = row_to_delete).delete()
            sess.commit()
        
        if formDict.get('start_cons_line') and formDict.get('end_cons_line'):
            #This will merge multiple rows if the start and end inputs are filled
            row_to_keep = int(formDict.get('start_cons_line'))
            row_to_move = row_to_keep + 1

            while row_to_move <= int(formDict.get('end_cons_line')):
                row_to_keep_obj=sess.query(Postshtml).filter_by(post_id=post_id, word_row_id=row_to_keep).first()
                row_to_move_obj=sess.query(Postshtml).filter_by(post_id=post_id, word_row_id=row_to_move).first()
                row_to_keep_obj.row_going_into_html=row_to_keep_obj.row_going_into_html+'<br>'+row_to_move_obj.row_going_into_html
                
                sess.query(Postshtml).filter_by(post_id=post_id, word_row_id=row_to_move).delete()
                sess.query(Postshtmltagchars).filter_by(post_id=post_id, word_row_id=row_to_move).delete()
                sess.commit()
                row_to_move += 1

            return redirect(url_for('blog.blog_edit',post_id=post_id ))

        if formDict.get('update_lines'):
            return redirect(url_for('blog.blog_edit',post_id=post_id ))

        else:
            #Merge one button pressed
            #This will merge the selected tbutton tothe row above
            for i in formDict.keys():# i is the merge button value
                if i[:1]=='_':
                    print('i that will become formDict_key: ', i, len(i))
                    formDict_key = i
                    print('int(i[6:]) that will become formDict_key: ', int(i[6:]))
                    row_to_move = int(i[6:])
            
            row_to_keep=int(formDict.get(formDict_key)[8:])
            row_to_keep_obj=sess.query(Postshtml).filter_by(post_id=post_id, word_row_id=row_to_keep).first()
            row_to_move_obj=sess.query(Postshtml).filter_by(post_id=post_id, word_row_id=row_to_move).first()
            row_to_keep_obj.row_going_into_html=row_to_keep_obj.row_going_into_html+'<br>'+row_to_move_obj.row_going_into_html
            
            sess.query(Postshtml).filter_by(post_id=post_id, word_row_id=row_to_move).delete()
            sess.query(Postshtmltagchars).filter_by(post_id=post_id, word_row_id=row_to_move).delete()
            sess.commit()

        return redirect(url_for('blog.blog_edit',post_id=post_id ))

    return render_template('blog/edit_template.html',post_id=post_id, post=post,
        postHtml_list=zip(postHtml_list,merge_row_id_list) , column_names=column_names, published_date=published_date,
        row_format_options=row_format_options )

