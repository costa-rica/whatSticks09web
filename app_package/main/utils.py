from flask import current_app, url_for
from flask_login import current_user
import json
import requests
from datetime import datetime, timedelta
from ws09_models import sess, Users, Locations, Weather_history, \
    Oura_token, Oura_sleep_descriptions, User_location_day
import time
from flask_mail import Message
from app_package import mail
import os
from werkzeug.utils import secure_filename
import zipfile
import shutil
import logging
from logging.handlers import RotatingFileHandler
import re
import pandas as pd


# if os.environ.get('CONFIG_TYPE')=='local':
#     config_context = ConfigLocal()
# elif os.environ.get('CONFIG_TYPE')=='dev':
#     config_context = ConfigDev()
# elif os.environ.get('CONFIG_TYPE')=='prod':
#     config_context = ConfigProd()


#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

#initialize a logger
logger_main = logging.getLogger(__name__)
logger_main.setLevel(logging.DEBUG)


#where do we store logging information
file_handler = RotatingFileHandler(os.path.join(os.environ.get('WEB_ROOT'),"logs",'users_routes.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

#where the stream_handler will print
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

# logger_sched.handlers.clear() #<--- This was useful somewhere for duplicate logs
logger_main.addHandler(file_handler)
logger_main.addHandler(stream_handler)



def user_data_item_list_util(USER_ID):
    list_of_data = os.listdir(current_app.config.get('DF_FILES_DIR'))

    file_name_start = f'user{USER_ID}_df_'
    start_length = len(file_name_start)
    list_of_data = [i for i in list_of_data if i[:start_length] == file_name_start]

    logger_main.info('-- list_of_data --')
    logger_main.info(list_of_data)


    data_item_list = [i[start_length:i.find('.')] for i in list_of_data]
    try:
        data_item_list.remove('browse_apple')
    except:
        print('no browse_apple')
    return data_item_list



def make_dir_util(dir):
    try:
        os.makedirs(dir)
    except:
        logger_main.info(f'{dir} already exists')


def send_reset_email(user):
    token = user.get_reset_token()
    logger_main.info(f"current_app.config.get(MAIL_USERNAME): {current_app.config.get('MAIL_USERNAME')}")
    msg = Message('Password Reset Request',
                  sender=current_app.config.get('MAIL_USERNAME'),
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('users.reset_token', token=token, _external=True)}

If you did not make this request, ignore email and there will be no change
'''

    mail.send(msg)


def send_confirm_email(email):
    logger_main.info(f"-- sending email to {email} --")
    msg = Message('Welcome to What Sticks!',
        sender=current_app.config.get('MAIL_USERNAME'),
        recipients=[email])
    msg.body = 'You have succesfully been registered to What-Sticks.'
    mail.send(msg)
    logger_main.info(f"-- email sent --")


def call_location_api(user):
#2-1b-1) call weather API
    api_token = current_app.config['LOCATION_API_KEY']
    # base_url = 'http://api.weatherapi.com/v1'#TODO: put this address in config
    base_url = current_app.config['LOCATION_API_URL_BASE']
    history = '/history.json'#TODO: put this address in config
    payload = {}
    payload['q'] = f"{user.lat}, {user.lon}"
    payload['key'] = api_token
    yesterday = datetime.today() - timedelta(days=1)
    payload['dt'] = yesterday.strftime('%Y-%m-%d')
    payload['hour'] = 0

#2-1b) if new location is new add location to Locations
    logger_main.info('* --> start location data process')
    # new_location = Locations()
    try:
        r_history = requests.get(base_url + history, params = payload)
        
        if r_history.status_code == 200:
            logger_main.info('Location API response code: ', r_history.status_code)
            #2) for each id call weather api
            return r_history.json()
        else:
            return f'Problem connecting with Weather API. Response code: {r_history.status_code}'
    except:
        return 'Error making call to Weather API. No response.'


def gen_weather_url(location_id, date):
    api_token = current_app.config['VISUAL_CROSSING_TOKEN']
    date_time = datetime.strptime(date + " 13:00:00", "%Y-%m-%d %H:%M:%S").isoformat()
    loc = sess.query(Locations).get(location_id)
    lat = loc.lat
    lon = loc.lon
    weather_call_url =f"{current_app.config['VISUAL_CROSSING_BASE_URL']}{str(lat)},{str(lon)}/{str(date_time)}?key={api_token}&include=current"
    logger_main.info('Weather_call:::')
    logger_main.info(weather_call_url)
    return weather_call_url


def add_new_location(location_api_response):
    new_location = Locations(
        city = location_api_response.get('location').get('name'),
        region = location_api_response.get('location').get('region'),
        country = location_api_response.get('location').get('country'),
        lat = location_api_response.get('location').get('lat'),
        lon = location_api_response.get('location').get('lon'),
        tz_id = location_api_response.get('location').get('tz_id')
        )
    sess.add(new_location)
    sess.commit()
    location_id = new_location.id
    logger_main.info(f'--- New location added, id: {location_id} ---')
    return location_id


def add_weather_history(weather_api_response, location_id):

    
    upload_dict ={ key: value for key, value in weather_api_response.json().get('days')[0].items()}
    upload_dict['location_id'] = location_id
    upload_dict['date_time'] = upload_dict['datetime']

    
    upload_dict_keys = list(upload_dict.keys())
    for key in upload_dict_keys:
        if isinstance(upload_dict[key], list):# <--- There have been some values that have return lists but most are text or float
            upload_dict[key] = upload_dict[key][0]
        if key not in Weather_history.__table__.columns.keys():# <--- keys are strange names, this removes any unexpected
            del upload_dict[key]

    try:
        new_data = Weather_history(**upload_dict)
        sess.add(new_data)
        sess.commit()
        return "successfully added to weather histrory"
    except:
        return "failed to add weather history"


def add_weather_history_more(weather_api_response, location_id):
    upload_success_count = 0
    upload_fail_count = 0
    for day_forecast in weather_api_response.json().get('days'):
        upload_dict ={ key: value for key, value in day_forecast.items()}
        upload_dict['location_id'] = location_id
        upload_dict['date_time'] = upload_dict['datetime']

        upload_dict_keys = list(upload_dict.keys())
        for key in upload_dict_keys:
            if isinstance(upload_dict[key], list):# <--- There have been some values that have return lists but most are text or float
                upload_dict[key] = upload_dict[key][0]
            if key not in Weather_history.__table__.columns.keys():# <--- keys are strange names, this removes any unexpected
                del upload_dict[key]

        try:
            new_data = Weather_history(**upload_dict)
            sess.add(new_data)
            sess.commit()
            upload_success_count += 1
        except:
            upload_fail_count += 1
    return upload_success_count

def oura_sleep_call(new_token):
    logger_main.info(f"--- making Oura API call ---")
    # url_sleep='https://api.ouraring.com/v1/sleep?start=2020-03-11&end=2020-03-21?'
    url_sleep = current_app.config['OURA_API_URL_BASE']
    response_sleep = requests.get(url_sleep, headers={"Authorization": "Bearer " + new_token})
    sleep_dict = response_sleep.json()
    logger_main.info('response_code: ',response_sleep.status_code)
    if response_sleep.status_code !=200:
        logger_main.info('*** Error With Token ****')
        return f'Error {str(response_sleep.status_code)}'
    else:
        return sleep_dict

def oura_sleep_db_add(sleep_dict, oura_token_id):
    logger_main.info(f"--- Adding Oura Ring data to database for user ---")
    # Add oura dictionary response to database
    startTime_db_oura_add = time.time()
    deleted_elements = 0
    sessions_added = 0
    
    for sleep_session in sleep_dict['sleep']:
        sleep_session_exists = sess.query(Oura_sleep_descriptions).filter_by(
            bedtime_end = sleep_session.get('bedtime_end'),
            user_id = current_user.id).first()
        if not sleep_session_exists:

            # delete any dict element whose key is not in column list
            for element in list(sleep_session.keys()):
                if element not in Oura_sleep_descriptions.__table__.columns.keys():
                    # print('element to delete: ', element)
                    
                    del sleep_session[element]
                    deleted_elements += 1

            sleep_session['user_id'] = current_user.id
            sleep_session['token_id'] = oura_token_id
            #check if existing sleep bedtime_end exists if yes skip
            existing_sleep_bedtime_end = sess.query(Oura_sleep_descriptions).filter_by(
                user_id = current_user.id,
                bedtime_end = sleep_session['bedtime_end']
            ).first()
            if not existing_sleep_bedtime_end:
                try:
                    new_sleep = Oura_sleep_descriptions(**sleep_session)
                    sess.add(new_sleep)
                    sess.commit()
                    sessions_added +=1
                except:
                    logger_main.info(f"Failed to add oura data row for sleepend: {sleep_session.get('bedtime_end')}")
    
    executionTime = (time.time() - startTime_db_oura_add)
    logger_main.info('Add Oura Data Execution time in seconds: ' + str(executionTime))
    deleted_elements_formatted = "{:,}".format(deleted_elements)
    logger_main.info(f'Number of eleements deleted {deleted_elements_formatted}')
    logger_main.info("Elements are data items in sleep sessions. Each sleep sesssion has score, summary_date, etc.")
    
    return sessions_added


def location_exists(user):
    
    min_loc_distance_difference = 1000

    locations_unique_list = sess.query(Locations).all()
    for loc in locations_unique_list:
        lat_diff = abs(user.lat - loc.lat)
        lon_diff = abs(user.lon - loc.lon)
        loc_dist_diff = lat_diff + lon_diff
        # print('** Differences **')
        # print('lat_difference:', lat_diff)
        # print('lon_diff:', lon_diff)

        if loc_dist_diff < min_loc_distance_difference:
            min_loc_distance_difference = loc_dist_diff
            location_id = loc.id

    if min_loc_distance_difference > .1:
        print('-----> loc_dist_diff is less than min required')
        location_id = 0
    
    # returns location_id = 0 if there is no location less than sum of .1 degrees
    return location_id


def make_user_item_list(data_item_key,list_of_notes) :
    data_item_list = []
    for note in list_of_notes:

        if isinstance(note,str):
            if note.find(data_item_key)>-1:
                data_item_start = note[note.find(data_item_key):]
                data_item_str = data_item_start[len(data_item_key):data_item_start.find(';')]
            else:
                data_item_str = ''
        else:
            data_item_str = ''
        data_item_list.append(data_item_str)
    
    return data_item_list


def edit_user_items_dict_util(user_notes):
    items_end_pos_list  = [m.start() for m in re.finditer(';', user_notes)]           
    counter = 0
    user_items_list = []
    for item_end_pos in items_end_pos_list:
        if counter==0:
            user_items_list.append(user_notes[:item_end_pos])
        else:
            user_items_list.append(user_notes[items_end_pos_list[counter-1]+1:item_end_pos])
        counter+=1

    items_dict = {}
    for item in user_items_list:
        items_dict[item[:item.find(':')]] = item[item.find(':')+1:]
    return items_dict

def get_apple_health_count(USER_ID):
    # table_name = 'apple_health_export_'
    # USER_ID = current_user.id if current_user.id !=2 else 1
    file_name = f'user{USER_ID}_df_browse_apple.pkl'
    file_path = os.path.join(current_app.config.get('DF_FILES_DIR'), file_name)
    if os.path.exists(file_path):
        df = pd.read_pickle(file_path)
        count = "{:,}".format(df.record_count.sum())
    else:
        count = 0
    return count
    # df_records_dict = df.to_dict('records')

def get_user_df_count(USER_ID, data_item):
    # table_name = 'apple_health_export_'
    # USER_ID = current_user.id if current_user.id !=2 else 1
    file_name = f'user{USER_ID}_df_{data_item}.pkl'
    file_path = os.path.join(current_app.config.get('DF_FILES_DIR'), file_name)
    print('file_path:::')
    print(file_path)
    if os.path.exists(file_path):
        df = pd.read_pickle(file_path)
        count = "{:,}".format(len(df))
    else:
        count = 0
    return count
    # df_records_dict = df.to_dict('records')