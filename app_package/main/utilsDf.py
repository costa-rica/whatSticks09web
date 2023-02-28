
from flask import current_app
from datetime import datetime, timedelta
import os
# from flask import current_app
from ws09_models import sess, Oura_sleep_descriptions, Weather_history, User_location_day, \
    Apple_health_export
import pandas as pd
# from flask_login import current_user
import json
import numpy as np
import logging
from logging.handlers import RotatingFileHandler
import re


#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

#initialize a logger
logger_main = logging.getLogger(__name__)
logger_main.setLevel(logging.DEBUG)
# logger_terminal = logging.getLogger('terminal logger')
# logger_terminal.setLevel(logging.DEBUG)

#where do we store logging information
file_handler = RotatingFileHandler(os.path.join(os.environ.get('WS_ROOT_WEB'),"logs",'users_routes.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

#where the stream_handler will print
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

# logger_sched.handlers.clear() #<--- This was useful somewhere for duplicate logs
logger_main.addHandler(file_handler)
logger_main.addHandler(stream_handler)



def remove_df_pkl(USER_ID, data_item):
    temp_file_name = f'user{USER_ID}_df_{data_item}.pkl'
    file_to_remove= os.path.join(current_app.config.get('DF_FILES_DIR'), temp_file_name)
    if os.path.exists(file_to_remove):
        os.remove(file_to_remove)


#This function is the same as in dashboard/utilsChart
def create_raw_df(USER_ID, table, table_name):

    if table_name != "weather_history_":
        base_query = sess.query(table).filter_by(user_id = 1)
        df = pd.read_sql(str(base_query)[:-1] + str(USER_ID), sess.bind)
    else:
        base_query = sess.query(table)
        df = pd.read_sql(str(base_query), sess.bind)
    if len(df) == 0:
        return False
    
    cols = list(df.columns)
    for col in cols:
        if col[:len(table_name)] == table_name:
            df = df.rename(columns=({col: col[len(table_name):]}))
    
    return df


def apple_hist_util(USER_ID, data_item_list, data_item_name_show, method, data_item_apple_type_name):
    print('--  IN apple_hist_util ---')
    df = create_raw_df(USER_ID, Apple_health_export, 'apple_health_export_')
    if isinstance(df,bool):
        return df
    df=df[df['type']==data_item_apple_type_name]
    df['date']=df['creationDate'].str[:10]
    df=df[['date', 'value']].copy()
    df['value']=df['value'].astype(float)

    df = df.rename(columns=({'value': data_item_list[0]}))
    if method == 'sum':
        df = df.groupby('date').sum()
    elif method == 'average':
        df = df.groupby('date').mean()
    df[data_item_list[0] + '-ln'] = np.log(df[data_item_list[0]])
    df.reset_index(inplace = True)
    print(df.head())
    return df


# def apple_hist_steps(USER_ID):
#     df = create_raw_df(USER_ID, Apple_health_export, 'apple_health_export_')
#     if isinstance(df,bool):
#         return df

#     df=df[df['type']=='HKQuantityTypeIdentifierStepCount']
#     df['date']=df['creationDate'].str[:10]
#     df=df[['date', 'value']].copy()
#     df['value']=df['value'].astype(int)
    
#     df = df.rename(columns=({'value': 'apple_health_step_count'}))
#     df = df.groupby('date').sum()
#     df['apple_health_step_count-ln'] = np.log(df.apple_health_step_count)
#     df.reset_index(inplace = True)
    
#     return df


def browse_apple_data(USER_ID):
    table_name = 'apple_health_export_'
    file_name = f'user{USER_ID}_df_browse_apple.pkl'
    file_path = os.path.join(current_app.config.get('DF_FILES_DIR'), file_name)

    if os.path.exists(file_path):
        os.remove(file_path)

    df = create_raw_df(USER_ID, Apple_health_export, table_name)
    if not isinstance(df, bool):
        series_type = df[['type']].copy()
        series_type = series_type.groupby(['type'])['type'].count()

        df_type = series_type.to_frame()
        df_type.rename(columns = {list(df_type)[0]:'record_count'}, inplace=True)
        count_of_apple_records = "{:,}".format(df_type.record_count.sum())

        # Try add new columns 
        df_type['index'] = range(1,len(df_type)+1)
        df_type.reset_index(inplace=True)
        df_type.set_index('index', inplace=True)
        df_type['type_formatted'] = df_type['type'].map(lambda cell_value: format_item_name(cell_value) )

        df_type['df_file_created']=''
        df_type.to_pickle(file_path)
        
        return count_of_apple_records
    return False


def format_item_name(data_item_name):
    #Accetps funky apple health name and returns something with spaces and capital letters
    # list_of_strings = ['HKCategoryTypeIdentifier','HKDataType','HKQuantityTypeIdentifier']

    # Get list of generic apple health cateogry names for removal in formatted names
    # with open(os.path.join(current_app.config.get('APPLE_HEALTH_DIR'), 'appleHealthCatNames.txt')) as f:
    #     lines = f.readlines()
    # list_of_strings = [i.strip() for i in lines]
    list_of_strings = current_app.config.get('APPLE_HEALTH_CAT_NAMES')

    if any(i in data_item_name for i in list_of_strings):
        for i in list_of_strings:
            if i in data_item_name:
                length_of_string = len(i)
                new_name = data_item_name[length_of_string:]
        return re.sub(r"(\w)([A-Z])", r"\1 \2", new_name)
    else:
        return data_item_name


def oura_hist_util(USER_ID, data_item):

    df = create_raw_df(USER_ID, Oura_sleep_descriptions, 'oura_sleep_descriptions_')
    if isinstance(df,bool):
        return df

    logger_main.info(f'--  making {data_item} --')
    df = df[['summary_date', 'score']].copy()
    # Remove duplicates keeping the last entryget latest date
    df = df.drop_duplicates(subset='summary_date', keep='last')

    if data_item == 'oura_sleep_tonight':
        df.rename(columns=({'summary_date':'date', 'score':'oura_sleep_tonight'}), inplace= True)
        df['oura_sleep_tonight-ln'] = np.log(df.oura_sleep_tonight)

    elif data_item == 'oura_sleep_last_night':
        df.rename(columns=({'summary_date':'date', 'score':'oura_sleep_last_night'}), inplace= True)
        df['date']=pd.to_datetime(df['date'],format='%Y-%m-%d')
        df['date'] = df['date'].apply(lambda d: d-timedelta(1))
        df['date'] = df['date'].astype(str)
        df['oura_sleep_last_night-ln'] = np.log(df.oura_sleep_last_night)

    return df


def user_loc_day_util(USER_ID):
    df = create_raw_df(USER_ID, User_location_day, 'user_location_day_')

    if isinstance(df,bool):
        return False, False
    # 1) get make df of user_day_location
    df = df[['date', 'location_id']]
    df= df.drop_duplicates(subset='date', keep='last')

    #2) make df of all weather [location_id, date, avg temp, cloudcover]
    df_weath_hist = create_raw_df(USER_ID, Weather_history, 'weather_history_')

    if isinstance(df_weath_hist,bool):
        return False, False

    df_weath_hist = df_weath_hist[['date_time','temp','location_id', 'cloudcover']].copy()
    df_weath_hist = df_weath_hist.rename(columns=({'date_time': 'date'}))
    
    # 3) merge on location_id and date
    df_user_date_temp = pd.merge(df, df_weath_hist, 
        how='left', left_on=['date', 'location_id'], right_on=['date', 'location_id'])
    df_user_date_temp = df_user_date_temp[df_user_date_temp['temp'].notna()]
    df_user_date_temp= df_user_date_temp[['date', 'temp', 'cloudcover']].copy()
    df_user_date_temp['cloudcover'] = df_user_date_temp['cloudcover'].astype(float)
    df_user_date_temp['temp-ln']=df_user_date_temp['temp'].apply(
                                        lambda x: np.log(.01) if x==0 else np.log(x))
    df_user_date_temp['cloudcover-ln']=df_user_date_temp['cloudcover'].apply(
                                        lambda x: np.log(.01) if x==0 else np.log(x))

    df_temp = df_user_date_temp[['date', 'temp', 'temp-ln']].copy()
    df_cloud = df_user_date_temp[['date', 'cloudcover', 'cloudcover-ln']].copy()

    return df_temp, df_cloud


def create_df_files(USER_ID, data_item_list):
    logger_main.info('-- In users/create_df_files --')

    #if data_item_list contains 'apple_health_' check to that browse apple exits
    if any('apple_health' in i for i in data_item_list):
        logger_main.info('**** data_item from apple health discovered: WRONG PLACE FOR APPLE DATA ****')
    #     if not os.path.exists(os.path.join(current_app.config.get('DF_FILES_DIR, f'user{USER_ID}_df_browse_apple.pkl')):
    #         browse_apple_data(USER_ID)


    # create file dictionary {data_item_name: path_to_df (but no df yet)}
    file_dict = {}
    for data_item in data_item_list:
        # temp_file_name = f'user{USER_ID}_df_{data_item}.json'
        temp_file_name = f'user{USER_ID}_df_{data_item}.pkl'
        file_dict[data_item] = os.path.join(current_app.config.get('DF_FILES_DIR'), temp_file_name)

    # Remove any existing df for user
    for _, f in file_dict.items():
        if os.path.exists(f):
            os.remove(f)

    df_dict = {}
    # Make DF for each in database/df_files/
    for data_item, file_path in file_dict.items():
        print(f'data_item: {data_item}')
        if not os.path.exists(file_path):
            # print('data_item: ', data_item)
            # if data_item == 'apple_health_step_count':
            #     df_dict[data_item] = apple_hist_steps(USER_ID)
            #     # if not isinstance(df_dict['steps'], bool): df_dict['steps'].to_pickle(file_path)
            #     if not isinstance(df_dict[data_item], bool): df_dict[data_item].to_pickle(file_path)
            #     #create brows_data_df
            #     browse_apple_data(USER_ID)
            # if data_item[:12] == 'apple_health':
            #     print('- Making  Apple health data item df_.pkl file -')
            #     print(' ***** ')

            #     df_dict[data_item_list[0]] = apple_hist_util(USER_ID, data_item_list, data_item_name_show, method, data_item_apple_type_name)
            #     if not isinstance(df_dict[data_item_list[0]], bool): df_dict[data_item_list[0]].to_pickle(file_path)
            #     # if not isinstance(df_dict['steps'], bool): df_dict['steps'].to_pickle(file_path)
            #     # if not isinstance(df_dict[data_item], bool): df_dict[data_item].to_pickle(file_path)

            #NOTE:Apple_health not processed here. AH processed in create_df_files_apple
            # elif data_item == 'oura_sleep_tonight':
            if data_item[:5] == 'oura_':
                logger_main.info(f'-- data_item: {data_item} fired --')
                df_dict[data_item] = oura_hist_util(USER_ID, data_item)
                if not isinstance(df_dict[data_item], bool):df_dict[data_item].to_pickle(file_path)
            elif data_item =='temp':
                df_dict['temp'], _ = user_loc_day_util(USER_ID)
                # if not isinstance(df_dict['temp'] , bool): df_dict['temp'] .to_pickle(file_path)
                if not isinstance(df_dict[data_item] , bool): df_dict[data_item] .to_pickle(file_path)
            elif data_item == 'cloudcover':
                _, df_dict['cloudcover'] = user_loc_day_util(USER_ID)
                # if not isinstance(df_dict['cloudcover'] , bool): df_dict['cloudcover'] .to_pickle(file_path)
                if not isinstance(df_dict[data_item] , bool): df_dict[data_item] .to_pickle(file_path)
            # else:
            #     print('-- else apple_hist_util --')
            #     df_dict[data_item_list[0]] = apple_hist_util(USER_ID, data_item_list, data_item_name_show, method, data_item_apple_type_name)
            #     if not isinstance(df_dict[data_item_list[0]], bool): df_dict[data_item_list[0]].to_pickle(file_path)
        # else:
        #     df_dict[data_item] = pd.read_pickle(file_path)
        #     logger_main.info(f'- catchall for future data_item(s) -')

    return df_dict


def create_df_files_apple(USER_ID,data_item_list, data_item_name_show, method, data_item_apple_type_name):
    logger_main.info('-- In users/create_df_files_apple --')

    # check if browse apple exits
    if any('apple_health' in i for i in data_item_list):
        logger_main.info('- data_item from apple health discovered -')
        if not os.path.exists(os.path.join(current_app.config.get('DF_FILES_DIR'), f'user{USER_ID}_df_browse_apple.pkl')):
            browse_apple_data(USER_ID)

    file_dict = {}
    # make file name and path for data_item
    for data_item in data_item_list:
        temp_file_name = f'user{USER_ID}_df_{data_item}.pkl'
        file_dict[data_item] = os.path.join(current_app.config.get('DF_FILES_DIR'), temp_file_name)

    logger_main.info(f'-- df .pkl files to be made: --')
    logger_main.info(f'{file_dict}')

    # Remove any existing df for user
    for _, f in file_dict.items():
        if os.path.exists(f):
            os.remove(f)

    df_dict = {}
    # Make DF for each in database/df_files/
    for data_item, file_path in file_dict.items():
        if not os.path.exists(file_path):
            if data_item[:12] == 'apple_health':
                logger_main.info(f'-- making pkl file for {data_item} --')

                df_dict[data_item_list[0]] = apple_hist_util(USER_ID, data_item_list, data_item_name_show, method, data_item_apple_type_name)
                if not isinstance(df_dict[data_item_list[0]], bool): df_dict[data_item_list[0]].to_pickle(file_path)
                logger_main.info(f'-- successfully made pkl file for {data_item} --')


    logger_main.info('-- Completed making apple_health pkl dfs users/create_df_files_apple --')
    return df_dict