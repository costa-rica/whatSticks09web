from tokenize import cookie_re
from flask import Blueprint
from flask import render_template, url_for, redirect, flash, request, abort, session,\
    Response, current_app, send_from_directory
# import bcrypt
from ws09_models import sess, Users, login_manager, User_location_day, Oura_sleep_descriptions, \
    Apple_health_export
from flask_login import login_required, login_user, logout_user, current_user
from datetime import datetime
import numpy as np
import pandas as pd
from app_package.dashboard.utils import buttons_dict_util, buttons_dict_update_util, \
    make_chart_util, df_utils, create_raw_df
from app_package.main.utilsDf import create_df_files, browse_apple_data, create_df_files_apple
from app_package.main.utils import user_data_item_list_util
import json
import os
import time
import logging
from logging.handlers import RotatingFileHandler


#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

#initialize a logger
logger_dash = logging.getLogger(__name__)
logger_dash.setLevel(logging.DEBUG)
# logger_terminal = logging.getLogger('terminal logger')
# logger_terminal.setLevel(logging.DEBUG)

#where do we store logging information
file_handler = RotatingFileHandler(os.path.join(os.environ.get('WS_ROOT_WEB'),"logs",'dashboard_routes.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

#where the stream_handler will print
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

# logger_sched.handlers.clear() #<--- This was useful somewhere for duplicate logs
logger_dash.addHandler(file_handler)
logger_dash.addHandler(stream_handler)


dash = Blueprint('dash', __name__)


@dash.route('/dashboard/<dash_dependent_var>', methods=['GET', 'POST'])
@login_required
def dashboard(dash_dependent_var):

    logger_dash.info(f'- Entered dashboard: {dash_dependent_var.upper()} -')
    

    if dash_dependent_var == 'sleep':
        dash_dependent_var = 'oura_sleep_tonight'
    elif dash_dependent_var == 'steps':
        dash_dependent_var = 'apple_health_step_count'
    USER_ID = current_user.id if current_user.id !=2 else 1


    data_item_list = user_data_item_list_util(USER_ID)


    #make static/dashbuttons
    dash_btns_dir = os.path.join(current_app.static_folder,'dash_btns')
    # sleep_dash_btns_dir = os.path.join(dash_btns_dir, 'sleep')
    dash_dependent_var_dash_btns_dir = os.path.join(dash_btns_dir, dash_dependent_var)
    
    if not os.path.exists(dash_dependent_var_dash_btns_dir):
        os.makedirs(dash_dependent_var_dash_btns_dir)

    # Buttons for dashboard table to toggle on/off correlations
    buttons_dict = {}
    user_btn_json_name = f'user{USER_ID}_buttons_dict.json'

    ################################### Moving to bottom of route #################################
    # if request.method == 'POST':
    #     formDict = request.form.to_dict()
    #     logger_dash.info('formDict: ', formDict)
    #     if formDict.get('refresh_data'):
    #         logger_dash.info('- Refresh data button pressed -')
    #         #remove steps because unnecessary and potentially takes a long time
    #         data_item_sub_list = ['oura_sleep_tonight', 'oura_sleep_last_night', 'temp', 'cloudcover']
    #         create_df_files(USER_ID, data_item_sub_list)

    #         #####################################################################################
    #         #TODO: Need to seperate 'apple_health_' to include other parameters that are needed 
    #         #######################################################################################
    #         # try:
    #         create_df_files_apple(USER_ID,['apple_health_step_count'], 'Step Count', 'sum', 'HKQuantityTypeIdentifierStepCount')
    #         # except:
    #         #     logger_dash.info('-- user has no apple health data for HKQuantityTypeIdentifierStepCount --')
    #     else:
    #         buttons_dict = buttons_dict_util(formDict, dash_dependent_var_dash_btns_dir, buttons_dict, user_btn_json_name)
    #     return redirect(url_for('dash.dashboard', dash_dependent_var=dash_dependent_var))
    ################################################
    
    # Read dict of user's chart data prefrences
    if os.path.exists(os.path.join(dash_dependent_var_dash_btns_dir,user_btn_json_name)):
        buttons_dict = buttons_dict_update_util(dash_dependent_var_dash_btns_dir, user_btn_json_name)

    df_dict = df_utils(USER_ID, data_item_list)
    print('- see df_dict ---')
    for key, value in df_dict.items():
        print(f'* df key: {key}')
        print(value.head())
    
    ### Checking that the DF have data 
    list_of_user_data = [df_name  for df_name, df in df_dict.items() if not isinstance(df, bool)]

    if dash_dependent_var not in df_dict:
        message = f"There is no data {dash_dependent_var} attached to your user. Go to accounts to add data."
        return render_template('main/dashboard_empty.html', page_name='Empty Dashboard', message = message) 
    # if user has no data return empty dashboard page
    if len(list_of_user_data) == 0:
        message = "There is no data attached to your user. Go to accounts to add data."
        return render_template('main/dashboard_empty.html', page_name='Empty Dashboard', message = message)
    
    # If user has no data for dash_dependent_var return empty dashboard page
    if isinstance(df_dict.get(dash_dependent_var), bool):
        message = f"You have not added any {dash_dependent_var} data to your profile. Go to your accounts page to add {dash_dependent_var} data."
        return render_template('main/dashboard_empty.html', page_name='Empty Dashboard', message=message)

    # Create dataframe of combined data by looping over df_dict and merging df's
    tuple_count = 0
    for _, df in df_dict.items():
        if not isinstance(df, bool) and tuple_count==0:
            df_all = df
            tuple_count += 1

        elif not isinstance(df, bool):
            df_all = pd.merge(df_all, df, how='outer')
    
    df_all = df_all.dropna(axis=1, how='all')#remove columns with all missing values

    if len(df_all)==0:# No weather data will cause this
        message = "Missing weather data. Go to your accounts page and add your location to see this dashboard."
        return render_template('main/dashboard_empty.html', page_name=page_name, message=message)


    # make each column into a list series
    series_lists_dict = {}
    for col_name in df_all.columns:
        if col_name == 'date':
            series_lists_dict[col_name] =[datetime.strptime(i,'%Y-%m-%d') for i in df_all['date'].to_list() ]
        else:
            series_lists_dict[col_name] = [i for i in df_all[col_name]]
    
    logger_dash.info('---- buttons_dict ___')
    logger_dash.info(buttons_dict)

    # send to chart making
    script_b, div_b, cdn_js_b = make_chart_util(series_lists_dict, buttons_dict)
    
    # TODO: oura_sleep name change
    # Create names dict to show formatted names in Buttons
    formatted_names_dict = {'temp':'Temperature', 'cloudcover':'Cloud Cover',
        'oura_sleep_tonight': 'Oura Sleep', 'oura_sleep_last_night': 'Oura Sleep Night Before', 
        'apple_health_step_count': 'Apple Step Count'}
    user_apple_browse_file = f"user{USER_ID}_df_browse_apple.pkl"
    user_apple_browse_path = os.path.join(current_app.config.get('DF_FILES_DIR'), user_apple_browse_file)
    if os.path.exists(user_apple_browse_path):
        print(user_apple_browse_path)
        df_browse = pd.read_pickle(os.path.abspath(user_apple_browse_path))
        apple_browse_names_dict = {'apple_health_' + i.replace(" ", "_").lower():i for i in df_browse.type_formatted}
        formatted_names_dict = formatted_names_dict | apple_browse_names_dict

    dashboard_name_formatted = ''
    if dash_dependent_var in formatted_names_dict.keys():
        dashboard_name_formatted = formatted_names_dict[dash_dependent_var]

    page_name = f"{dashboard_name_formatted} Dashboard"
    # --- calcualute CORRELATIONS ---

    #Filter out rows where the dep vars are null
    print('- df_all -')
    print(df_all)
    df_interest = df_all[df_all[dash_dependent_var].notnull()]
    print('- df_interest columns -')
    print(df_interest.columns)

    # Create dictionaries for {data_item: correaltion} (and {data_item: Not enough data})
    print('- data_item_list -')
    print(data_item_list)
    print('- df_all.columns -')
    print(df_all.columns)
    data_items_of_interest_list = list(set(data_item_list) & set(df_all.columns)) #intersection of both lists
    print('- data_items_of_interest_list -')
    print(data_items_of_interest_list)
    corr_dict={}
    corr_dict_na={}
    for df_name in data_items_of_interest_list:
        corr_dict[df_name] = round(df_interest[df_name].corr(df_interest[dash_dependent_var]),2)


        if corr_dict[df_name] != corr_dict[df_name]:# Pythonic way for checking for nan
            corr_dict_na[df_name] = ["Not enough data",formatted_names_dict[df_name]]
            del corr_dict[df_name]
            
    # Remove depenedent variable for corrleations list
    del corr_dict[dash_dependent_var]
    

    
    # Sort correlations by most impactful by converting to DF
    if len(corr_dict) > 0:
        df_corr = pd.DataFrame.from_dict(corr_dict, orient='index')
        df_corr.rename(columns={list(df_corr)[0]:'correlation'}, inplace=True)
        print('--- df_corr ___ ')
        print(df_corr)
        df_corr['abs_corr'] = df_corr['correlation'].abs()
        df_corr = df_corr.sort_values('abs_corr', ascending=False)
        corr_dict = df_corr.to_dict().get('correlation')

        corr_dict = {key: ['{:,.0%}'.format(value), formatted_names_dict[key]] for key,value in corr_dict.items() }
    if len(corr_dict_na)>0:# Add back in any vars with "Not enough data" for correlation
        corr_dict = corr_dict | corr_dict_na

    print('--- corr_dict --')
    print(corr_dict)


    if request.method == 'POST':
        formDict = request.form.to_dict()
        logger_dash.info('formDict: ', formDict)
        if formDict.get('refresh_data'):
            logger_dash.info('- Refresh data button pressed -')
            #remove steps because unnecessary and potentially takes a long time
            data_item_sub_list = ['oura_sleep_tonight', 'oura_sleep_last_night', 'temp', 'cloudcover']
            create_df_files(USER_ID, data_item_sub_list)

            #####################################################################################
            #TODO: Need to seperate 'apple_health_' to include other parameters that are needed 
            #######################################################################################
            # try:
            create_df_files_apple(USER_ID,['apple_health_step_count'], 'Step Count', 'sum', 'HKQuantityTypeIdentifierStepCount')
            # except:
            #     logger_dash.info('-- user has no apple health data for HKQuantityTypeIdentifierStepCount --')
        else:
            buttons_dict = buttons_dict_util(formDict, dash_dependent_var_dash_btns_dir, buttons_dict, user_btn_json_name)
        return redirect(url_for('dash.dashboard', dash_dependent_var=dash_dependent_var, dashboard_name_formatted=dashboard_name_formatted))


    return render_template('main/dashboard.html', page_name=page_name,
        script_b = script_b, div_b = div_b, cdn_js_b = cdn_js_b, corr_dict=corr_dict, 
        buttons_dict=buttons_dict, dash_dependent_var = dash_dependent_var, dashboard_name_formatted=dashboard_name_formatted)

@dash.route('/refresh_data', methods=['GET', 'POST'])
@login_required
def refresh_data():
    print('--- in refresh_data ---')
    USER_ID = request.args.get('USER_ID')
    dash_dependent_var = request.args.get('dash_dependent_var')
    dashboard_name_formatted = request.args.get('dashboard_name_formatted')
    print('- dash_dependent_var -')
    print(dash_dependent_var)
    logger_dash.info('- Refresh data button pressed -')
    #remove steps because unnecessary and potentially takes a long time
    data_item_sub_list = ['oura_sleep_tonight', 'oura_sleep_last_night', 'temp', 'cloudcover']
    create_df_files(USER_ID, data_item_sub_list)

    #####################################################################################
    #TODO: Need to seperate 'apple_health_' to include other parameters that are needed 
    #######################################################################################
    # try:
    create_df_files_apple(USER_ID,['apple_health_step_count'], 'Step Count', 'sum', 'HKQuantityTypeIdentifierStepCount')
    print(' --- departing refresh_dash ---')
    # return redirect(url_for('dash.dashboard', dash_dependent_var=dash_dependent_var, dashboard_name_formatted=dashboard_name_formatted))
    return redirect(url_for('dash.dashboard', dash_dependent_var=dash_dependent_var))
