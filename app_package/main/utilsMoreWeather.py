from app_package.main.utils import gen_weather_url, add_new_location, add_weather_history
# from app_package.dashboard.utils import df_utils
from app_package.main.utils import location_exists, user_data_item_list_util
import requests;import json
from ws09_models import sess, Oura_sleep_descriptions, Users, Oura_token, Weather_history, Locations, User_location_day, \
    Apple_health_export
import os
from datetime import datetime, timedelta
import time
import pandas as pd
import os
import logging
from logging.handlers import RotatingFileHandler


# logs_dir = os.path.abspath(os.path.join(os.getcwd(), 'logs'))

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



def get_df_for_dash(USER_ID, data_item, file_path):
    file_name = f'user{USER_ID}_df_{data_item}.pkl'
    file_path_and_name = os.path.join(file_path, file_name)
    if not os.path.exists(file_path_and_name):
        return False
    df = pd.read_pickle(file_path_and_name)
    return df

# def user_oldest_day_util(USER_ID):
#     data_item_list = ['steps', 'sleep', 'temp', 'cloudcover']
#     df_dict = {key:get_df_for_dash(USER_ID,key) for key in data_item_list}
#     logger_main.info(f"- df_dict steps: {df_dict.get('steps').head()}")
#     logger_main.info(f"- df_dict temp: {df_dict.get('temp').head()}")
#     oldest_date_list = []
#     for i in data_item_list:
#         if not isinstance(df_dict.get(i), bool):
#             if isinstance(df_dict.get(i).iloc[0].date, str):
#                 oldest_date_list.append(datetime.strptime(df_dict.get(i).iloc[0].date,'%Y-%m-%d'))
#     logger_main.info(f'- oldest_date_list: {oldest_date_list}')
#     oldest_date_str = min(oldest_date_list).strftime("%Y-%m-%d")
#     return oldest_date_str

def user_oldest_day_util(USER_ID, file_path):
    # data_item_list = ['steps', 'sleep', 'temp', 'cloudcover']
    data_item_list = user_data_item_list_util(USER_ID)

    df_dict = {key:get_df_for_dash(USER_ID, key, file_path) for key in data_item_list}
    logger_main.info(f'- searched for oldest_day in : {df_dict.keys()}')
    oldest_date_list = []
    for i in data_item_list:
        if not isinstance(df_dict.get(i), bool):
            if isinstance(df_dict.get(i).iloc[0].date, str):
                oldest_date_list.append(datetime.strptime(df_dict.get(i).iloc[0].date,'%Y-%m-%d'))
    logger_main.info(f'- oldest_date_list: {oldest_date_list}')
    oldest_date_str = min(oldest_date_list).strftime("%Y-%m-%d")
    return oldest_date_str


def search_weather_dict_util(oldest_date_str, loc_id):
    ##############################################################
    # This function searches weather history and returns first 
    # missing gap of historical weather data
    ################################################################
    # date_dict = {}
    flag_looking_for_end = False
    
    current_date = datetime.strptime(oldest_date_str,'%Y-%m-%d')
    today_date_str = datetime.now().strftime('%Y-%m-%d')
    today_date = datetime.strptime(today_date_str,'%Y-%m-%d')
    
    while current_date <= today_date:

        search_weather = sess.query(Weather_history).filter_by(location_id = loc_id, date_time = current_date.strftime("%Y-%m-%d")).first()
        
        if current_date == datetime.strptime(oldest_date_str,'%Y-%m-%d'):
        # First search loop
            if not search_weather:

                start_date = current_date
                flag_looking_for_end = True
                if current_date == today_date:
#                     print('--- This should fire also _ search_weather_dict_util___')
                    return {"start":start_date.strftime('%Y-%m-%d'), "end": current_date.strftime('%Y-%m-%d')}
            #last date
            elif search_weather and current_date == today_date:
            #first search is also last day (today)
                return {}
        else:
        # every loop after first
            if not search_weather and not flag_looking_for_end:
            # Found first missing date: found start date --> start looking for end_date
                start_date = current_date
                flag_looking_for_end = True
                if current_date == today_date:
                # Only in case where the only missing weatehr history is actual current day
                    return {"start":start_date.strftime('%Y-%m-%d'), "end": current_date.strftime('%Y-%m-%d')}
#             elif search_weather and (flag_looking_for_end or current_date == today_date):
            elif search_weather and flag_looking_for_end:
            # STOP: found weather history after finding it in last current_date
                end_date = current_date - timedelta(1)
                return {"start":start_date.strftime('%Y-%m-%d'), "end": end_date.strftime('%Y-%m-%d')}
            elif search_weather and current_date == today_date:
            # STOP: found weather history and reached the last day of search --> no need for any data
                return {}
            elif not search_weather and current_date == today_date:
            # ONLY case where we reach last day (actual current date) and still not found weather_hist
                return {"start":start_date.strftime('%Y-%m-%d'), "end": current_date.strftime('%Y-%m-%d')}
            # -- Other cases not needed --
            #             elif search_weather and not flag_looking_for_end:
                        # No Change: continue searching: found weather history after finding it in previous current_date
            #             elif not search_weather and flag_looking_for_end:
                        # Already found start date - no change to start date; Not found end date

        current_date += timedelta(1)
    return {}


def search_weather_dict_list_util(oldest_date_str, loc_id):
    ############################################################################
    # This function returns list of dicts containing {"start":date,"end":date} #
    # starts with oldest_date_str send by whatever means then calls
    # search_weather_dict_util (above) if returns empty dict it stops, else it
    # uses the returned dict to find end date, adds one date and submits that as
    # the new oldest_date_str until oldest_date_str is actual current day (today)
    #############################################################################
    search_weather_dict_list = []
    today_date_str = datetime.now().strftime('%Y-%m-%d')
    today_date = datetime.strptime(today_date_str,'%Y-%m-%d')
    next_start_date = datetime.strptime(oldest_date_str,'%Y-%m-%d')
    # get oldest _date_str
    while search_weather_dict_list == [] or next_start_date <= today_date:       
        
        if search_weather_dict_list == []:
        #search for first
            temp_dict = search_weather_dict_util(oldest_date_str, loc_id)

        else:
        # Every tiem after use the next day to search from
            temp_dict = search_weather_dict_util(next_start_date.strftime('%Y-%m-%d'), loc_id)
            
        if temp_dict == {}:
            return search_weather_dict_list
        elif temp_dict.get('end') == today_date_str:
            search_weather_dict_list.append(temp_dict)
            return search_weather_dict_list
            
        search_weather_dict_list.append(temp_dict)
        next_start_date = datetime.strptime(temp_dict.get('end'),'%Y-%m-%d') + timedelta(1)




def add_user_loc_days(oldest_date_str, USER_ID, loc_id):
    # dates_call_dict = {}
    # call_period = 1
    end_date_str = datetime.now().strftime("%Y-%m-%d")
    end_date = datetime.strptime(end_date_str,"%Y-%m-%d")
    oldest_day = datetime.strptime(oldest_date_str,"%Y-%m-%d")
    end_date_flag = True# indicates loop is searching for end_date of a period. False means searching for start_date
    # previous_day = end_date

    while end_date >= oldest_day:
        end_date_str = end_date.strftime("%Y-%m-%d")
        search_day = sess.query(User_location_day).filter_by(user_id=USER_ID, date=end_date_str).first()

        if not search_day and end_date == oldest_day:

            new_user_loc = User_location_day(user_id = USER_ID, location_id=loc_id, date=end_date_str, row_type="user input")
            sess.add(new_user_loc)
            sess.commit()
        elif not search_day and end_date_flag:
            
            new_user_loc = User_location_day(user_id = USER_ID, location_id=loc_id, date=end_date_str, row_type="user input")
            sess.add(new_user_loc)
            sess.commit()
            # temp_end = end_date.strftime("%Y-%m-%d")

            end_date_flag = False
        elif not search_day and not end_date_flag:
            
            new_user_loc = User_location_day(user_id = USER_ID, location_id=loc_id, date=end_date_str, row_type="user input")
            sess.add(new_user_loc)
            sess.commit()

        elif search_day:

            end_date_flag =True


        end_date = end_date - timedelta(1)
    # TODO: Do not need these date_call_dict but need to make this for a similar function that users weather_hist
    # return dates_call_dict
        

# def get_missing_weather_dates_from_hist(oldest_date_str, loc_id):
#     logger_main.info(f'- In get_dates_call_dict_from_hist -')
#     dates_call_dict = {}
#     call_period = 1
#     end_date_str = datetime.now().strftime("%Y-%m-%d")
#     end_date = datetime.strptime(end_date_str,"%Y-%m-%d")
#     oldest_day = datetime.strptime(oldest_date_str,"%Y-%m-%d")
#     end_date_flag = True
#     # previous_day = end_date
#     logger_main.info(f'oldest_date_str: {oldest_date_str}')
#     temp_start_str=oldest_date_str
#     temp_end_str = end_date.strftime("%Y-%m-%d")

#     while end_date >= oldest_day:
#         end_date_str = end_date.strftime("%Y-%m-%d")
#         search_day = sess.query(Weather_history).filter_by(location_id=loc_id, date_time=end_date_str).first()
#         # logger_main.info(f'end_date_str: {end_date_str}')
#         if not search_day and end_date == oldest_day:# ONLY gets called at very end if search_day not found
#             logger_main.info('--- in if end_date == oldest_day ---')
            
            
            
#             if temp_end_str != dates_call_dict[call_period-1].get('end'):
#                 dates_call_dict[call_period] = {"start": temp_start_str, "end":temp_end_str}
#                 call_period += 1
#                 logger_main.info('- fire last -')
#         elif not search_day and end_date_flag:#Only on days with no weath_hist just before a day w/ weath_hist
#             temp_end_str = end_date.strftime("%Y-%m-%d")
#             temp_start_str = temp_end_str
#             end_date_flag = False
#         elif not search_day and not end_date_flag:#Any day w/out weath_hist NOT before a day w/ weath_hist
#             temp_start_str = end_date.strftime("%Y-%m-%d")

#         elif search_day and temp_start_str != oldest_date_str:#Any day w/ weath_hist (but not first day of checking hence temp_start_str!='')
#                                 # Trust temp_start_str !='' is needed here

#             if len(dates_call_dict) ==0:
#                 dates_call_dict[call_period] = {"start": temp_start_str, "end":temp_end_str}
#                 logger_main.info('- First dates_call_dict entry: len(dates_call_dict) ==0 - ')
#                 logger_main.info(dates_call_dict[call_period])

#                 call_period += 1

#             elif len(dates_call_dict) >0:
#                 if temp_end_str != dates_call_dict[call_period-1].get('end'):
#                     dates_call_dict[call_period] = {"start": temp_start_str, "end":temp_end_str}                  
#                     logger_main.info('- After first dates_call_dict - ')
#                     logger_main.info(dates_call_dict[call_period])

#                     call_period += 1
#             end_date_flag =True
#             # previous_day = end_date

#         end_date = end_date - timedelta(1)
#     return dates_call_dict



