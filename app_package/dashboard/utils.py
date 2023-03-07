from bokeh.plotting import figure, output_file, show
from bokeh.embed import components
from bokeh.resources import CDN
from bokeh.io import curdoc
from bokeh.themes import built_in_themes, Theme
from bokeh.models import ColumnDataSource, Grid, LinearAxis, Plot, Text, Span
from datetime import datetime, timedelta
import os
from flask import current_app
from ws09_models import sess, Oura_sleep_descriptions, Weather_history, User_location_day
import pandas as pd
from flask_login import current_user
import json
import logging
from logging.handlers import RotatingFileHandler
from app_package.main.utilsDf import create_raw_df


#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

#initialize a logger
logger_dash = logging.getLogger(__name__)
logger_dash.setLevel(logging.DEBUG)

#where do we store logging information
file_handler = RotatingFileHandler(os.path.join(os.environ.get('WEB_ROOT'),"logs",'dashboard_routes.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

#where the stream_handler will print
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

# logger_sched.handlers.clear() #<--- This was useful somewhere for duplicate logs
logger_dash.addHandler(file_handler)
logger_dash.addHandler(stream_handler)



def buttons_dict_util(formDict, dashboard_routes_dir, buttons_dict, user_btn_json_name):
    if formDict.get('same_page'):
        del formDict['same_page']
    # if len(formDict)>0:
    #1 read json dict with switches

    if os.path.exists(os.path.join(dashboard_routes_dir,user_btn_json_name)):
        with open(os.path.join(dashboard_routes_dir,user_btn_json_name)) as json_file:
            buttons_dict = json.load(json_file)

    if buttons_dict.get(list(formDict.keys())[0]) != None:
        buttons_dict[list(formDict.keys())[0]] = (buttons_dict.get(list(formDict.keys())[0]) + int(formDict[list(formDict.keys())[0]])) % 2
    else:
        buttons_dict[list(formDict.keys())[0]] = int(formDict[list(formDict.keys())[0]])

    with open(os.path.join(dashboard_routes_dir,user_btn_json_name), 'w') as convert_file:
        convert_file.write(json.dumps(buttons_dict))
    logger_dash.info('Wrote buttons_dict.json')
    return buttons_dict


def buttons_dict_update_util(dashboard_routes_dir, user_btn_json_name):
    with open(os.path.join(dashboard_routes_dir,user_btn_json_name)) as json_file:
        buttons_dict = json.load(json_file)
    return buttons_dict


# #This function is same as in users/utilsDf
# def create_raw_df(USER_ID, table, table_name):
#     # print('*** In create_raw_df **')
#     if table_name != "weather_history_":
#         base_query = sess.query(table).filter_by(user_id = 1)
#         df = pd.read_sql(str(base_query)[:-1] + str(USER_ID), sess.bind)
#     else:
#         # print('*** step 5 **')
#         base_query = sess.query(table)
#         df = pd.read_sql(str(base_query), sess.bind)
#     if len(df) == 0:
#         return False
    
#     cols = list(df.columns)
#     for col in cols:
#         if col[:len(table_name)] == table_name:
#             df = df.rename(columns=({col: col[len(table_name):]}))
    
#     return df


def get_df_for_dash(USER_ID, data_item):
    file_name = f'user{USER_ID}_df_{data_item}.pkl'
    file_path = os.path.join(current_app.config.get('DF_FILES_DIR'), file_name)
    if not os.path.exists(file_path):
        print(' ********** ')
        print(file_path)
        return False

    df = pd.read_pickle(file_path)

    return df


def make_chart_util(series_lists_dict, buttons_dict):
    logger_dash.info('-- make_chart_util --')
    logger_dash.info(f'-- {series_lists_dict.keys()} --')

    list_of_items = [i for i in series_lists_dict.keys() if i.find('-ln') == -1 ]
    list_of_items.remove('date')
    logger_dash.info(list_of_items)

    plot_font_size = "1rem"
    dates_list = series_lists_dict.get('date')
    date_start = max(dates_list) - timedelta(days=2.5)
    date_end = max(dates_list) + timedelta(days=1)

    fig1=figure(toolbar_location=None,tools='xwheel_zoom,xpan',active_scroll='xwheel_zoom',
            x_range=(date_start,date_end),
            y_range=(-5,12),sizing_mode='stretch_width', height=400)

    color_list = ['#f1c40f', '#f39c12', "#e67e22", "#d35400", '#ecf0f1','#bdc3c7', '#95a5a6']

    source_dict = {}
    glyph_dict = {}
    counter = 0

    # Loop tover list o0f items
    for item in list_of_items:
        flag = True
        print(f'-- working on {item} ---')
        item_list = series_lists_dict.get(item)
        
        item_ln_list = series_lists_dict.get(item + '-ln')
        # if item == 'active_energy_burned':
        #     with open('active_energy_burned.json', 'w') as file_path:
        #         json.dump(item_list, file_path)

        item_list_formatted = []
        #TODO: Remove nan obs -> possible solution: item_ln_list_formatted =[]# remove nan
        # Format item_list
        # --> if number is less than 10 "{:.2f}".format(element)
        # --> if number is greater than 10 "{:,}".format(element)
        # --> if number is none nan return nan
        for i in item_list:
            if i != i:
                item_list_formatted.append(i)

            if float(i) <10:
                item_list_formatted.append("{:.1f}".format(i))

            elif float(i) >= 10:
                item_list_formatted.append("{:,}".format(int(i)))
                    # item_list_formatted.append('Numbrer')

            # else:
            #     print('* Found and else *')
            #     print(type(i))
            #     print(i)
                

        item_list = item_list_formatted

        if buttons_dict.get(item) !=1:
            fig1.circle(dates_list,item_ln_list, 
                legend_label=item, 
                fill_color=color_list[counter % len(color_list)], 
                line_color=None,
                size=30)

            source_dict[item] = ColumnDataSource(dict(x=dates_list, y=item_ln_list, text=item_list)) # data
            glyph_dict[item] = Text(text="text",text_font_size={'value': plot_font_size},x_offset=-10, y_offset=10) # Image
            fig1.add_glyph(source_dict[item], glyph_dict[item])
        
        counter += 1



    # #steps rectangle label
    # if series_lists_dict.get('steps'):
    #     steps_list = series_lists_dict.get('steps')
    #     steps_ln_list = series_lists_dict.get('steps-ln')
    #     if buttons_dict.get('steps') !=1:
    #         fig1.square(dates_list, steps_ln_list, legend_label = 'Daily Steps', size=30, color="gray", alpha=0.5)
            
    #         source4 = ColumnDataSource(dict(x=dates_list, y=steps_ln_list,
    #             text=steps_list))
    #         glyph4 = Text(text="text",text_font_size={'value': plot_font_size},x_offset=-10, y_offset=10)
    #         fig1.add_glyph(source4, glyph4)


    fig1.ygrid.grid_line_color = None
    fig1.yaxis.major_label_text_color = None
    fig1.yaxis.major_tick_line_color = None
    fig1.yaxis.minor_tick_line_color = None

    fig1.legend.background_fill_color = "#578582"
    fig1.legend.background_fill_alpha = 0.2
    fig1.legend.border_line_color = None
    fig1.legend.label_text_font_size ='1.3rem'
    fig1.xaxis.major_label_text_font_size = '1.3rem'
    # fig1.xaxis.axis_label = 'whatever'
    theme_1=curdoc().theme = Theme(filename=os.path.join(current_app.static_folder, 'chart_theme_2.yml'))

    script1, div1 = components(fig1, theme=theme_1)

    cdn_js=CDN.js_files

    return script1, div1, cdn_js


def df_utils(USER_ID, data_item_list):
    # Make DF for each data_item
    print('- In df_utils -')
    file_dict ={}
    for data_item in data_item_list:
        print(f'data_item: {data_item}')
        file_name = f'user{USER_ID}_df_{data_item}.pkl'
        file_path = os.path.join(current_app.config.get('DF_FILES_DIR'), file_name)
        file_dict[data_item] = file_path
    
    df_dict = {}

    for data_item, file_path in file_dict.items():
        df_dict[data_item] = get_df_for_dash(USER_ID, data_item)

    return df_dict
