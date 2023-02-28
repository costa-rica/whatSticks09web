from flask import current_app, url_for
from flask_login import current_user
from datetime import datetime, timedelta
from ws09_models import sess, engine, Apple_health_export
import time
from app_package import mail
import os
from werkzeug.utils import secure_filename
import zipfile
import shutil
import pandas as pd
import logging
from logging.handlers import RotatingFileHandler
import re


#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

#initialize a logger
logger_main = logging.getLogger(__name__)
logger_main.setLevel(logging.DEBUG)


#where do we store logging information
file_handler = RotatingFileHandler(os.path.join(os.environ.get('WS_ROOT_WEB'),"logs",'users_routes.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

#where the stream_handler will print
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

# logger_sched.handlers.clear() #<--- This was useful somewhere for duplicate logs
logger_main.addHandler(file_handler)
logger_main.addHandler(stream_handler)


def report_process_time(start_post_time):
        
    end_post_time = time.time()
    run_seconds = round(end_post_time - start_post_time)
    if run_seconds <60:
        return f"---run_time: {str(run_seconds)} seconds"
    elif run_seconds > 60:
        run_minutes =  round(run_seconds / 60)
        return f"--- run_time: {str(run_minutes)} mins and {str(run_seconds % 60)} seconds"

def make_dir_util(dir):
    if not os.path.exists(dir):
        os.makedirs(dir)
        logger_main.info(f'- Created {dir}')


def decompress_and_save_apple_health(apple_health_dir, apple_health_data):
    ###################################################################
    # Anytime user adds apple health .zip, this method fires
    ##################################################################
    logger_main.info(f'-- START users_routes/utilsApple def decompress_and_save_apple_health')
    # logger_main.info(f'-- ***************************************')
    make_dir_util(os.path.join(apple_health_dir, 'apple_health_export'))
    # path_to_zip_file = os.path.join(apple_health_dir, secure_filename(apple_health_data.filename))
    path_to_zip_file = os.path.join(apple_health_dir, 'apple_health_export',secure_filename(apple_health_data.filename))
    apple_health_data.save(path_to_zip_file)


    logger_main.info(f'- path_to_zip_file: {path_to_zip_file}')


    ##################################################################
    # /apple_health_export/ OK
    # 
    #######################################################################

    #unzip
    with zipfile.ZipFile(path_to_zip_file, 'r') as zip_ref:
        xml_filename = zip_ref.namelist()[0]
        
        if xml_filename == 'apple_health_export/':# <--- means it comes straight from Apple Health download
            logger_main.info(f'- User submitted export.zip straight from Apple Health')
            zip_ref.extractall(apple_health_dir)
            

            new_file_path_files_list = os.listdir(os.path.join(apple_health_dir,'apple_health_export'))
            for file in new_file_path_files_list:
                if file[-4:]=='.xml':
                    new_file_path = os.path.join(apple_health_dir,'apple_health_export', file)
                    logger_main.info(f'---> new_file_path: {new_file_path}')

        else:# <---- some other file maybe something i zipped
            logger_main.info(f'- User submitted a zipped version of the xml file')
            zip_ref.extractall(os.path.join(apple_health_dir, 'apple_health_export'))
            
            new_file_path = os.path.join(apple_health_dir,'apple_health_export',xml_filename )
        # This extracts a folder called 'apple_health_export'
        # inside this folder is are two files export.zpi and export.xml



    # logger_main.info(f'2: apple_health_dir: {apple_health_dir}')
    # logger_main.info(f'-- apple_health filename: {apple_health_data.filename}')
    # logger_main.info(f'-- apple_health filename type: {type(apple_health_data.filename)}')
    # logger_main.info(f'-- apple_health filename type: {apple_health_data.filename[:-4]}')

    ##################################################################
    # BY HERE it already made too many /apple_health_export/
    # on  second addition of apple_health_export to a user
    #######################################################################


    #copy file to apple_health_dir and rename
    # if xml_filename == 'apple_health_export/':# <--- means it comes straight from Apple Health download
    #     # new_file_path = os.path.join(apple_health_dir,'apple_health_export','export.xml' )
    #     logger_main.info(f'---> searching for new_file in apple_health_export dir')
    #     new_file_path_files_list = os.listdir(os.path.join(apple_health_dir,'apple_health_export'))
    #     for file in new_file_path_files_list:
    #         if file[-4:]=='.xml':
    #             new_file_path = os.path.join(apple_health_dir,'apple_health_export', file)
    #             logger_main.info(f'---> new_file_path: {new_file_path}')
    #     logger_main.info(f'---> from Apple Health download')
    # else:# <---- some other file maybe something i zipped
    #     new_file_path = os.path.join(apple_health_dir,'apple_health_export',xml_filename )
    #     logger_main.info(f'---> from Nick edited or other source')
    # # new_file_path = os.path.join(apple_health_dir,'export.xml' )
    # # new_file_path = os.path.join(apple_health_dir,xml_filename )
    #     logger_main.info(f'---> new_file_path (user zipped): {new_file_path}')

    # logger_main.info(f'3: apple_health_dir: {apple_health_dir}')


    today_str = datetime.today().strftime("%Y%m%d")
    new_file_name = 'user' +str(current_user.id).zfill(4) + "_" + today_str + ".xml"
    new_file_path_dest = os.path.join(apple_health_dir, new_file_name)



    shutil.copy(new_file_path, new_file_path_dest)

    # delete .zip and apple_health_export
    os.remove(path_to_zip_file)
    shutil.rmtree(os.path.join(apple_health_dir,'apple_health_export'))

    logger_main.info(f'-- END users_routes/utilsApple def decompress_and_save_apple_health')

    return new_file_path_dest


def add_apple_to_db(xml_dict):
    #Add new users apple data to database
    logger_main.info(f'-- in users/utilsApple.py def add_apple_to_db --')
    #######################################
    # XML already converted to dictionary #
    #######################################

    records_list = xml_dict['HealthData']['Record']
    df = pd.DataFrame(records_list)
    df['user_id'] = current_user.id
    df['time_stamp_utc']=datetime.utcnow()
    for name in list(df.columns):
        if name.find('@')!=-1:
            df.rename(columns={name:name[1:]}, inplace=True)

# Columns with dictionary structures i di'tn kwon what to do with
    df.MetadataEntry=''
    df.HeartRateVariabilityMetadataList=''

    #get all user's existing apple_health data into df
    base_query = sess.query(Apple_health_export).filter_by(user_id = 1)
    df_existing = pd.read_sql(str(base_query)[:-1] + str(current_user.id), sess.bind)

    logger_main.info(f'current user has {len(df_existing)} rows')
    
    #rename columns
    table_name = 'apple_health_export_'
    cols = list(df_existing.columns)
    for col in cols:
        if col[:len(table_name)] == table_name:
            df_existing = df_existing.rename(columns=({col: col[len(table_name):]}))


    ##############################################################################
    ### NOTE: This is where a problem with apple health dates occurs.
    #### The createDate has slight differences depending on when the file is downloaded due to daylight savings
    #### pd.to_datetime(date_string).asm8 will normalize the data so that different daylight savings times can be compared on same level
    #### Other issues include:
    #### - uniqueness requires ['user_id','type','sourceName','sourceVersion','unit','creationDate','startDate','endDate','value','device']
    #### - 'id' is set to object because there is no int, so need to remove from new data
    ##############################################################################
    # New converting column to datatime value


    if len(df_existing) > 0:
        
        
        #convert df_existing to normalized date string
        df['creationDate'] = pd.to_datetime(df['creationDate'])
        df['creationDate'] = df['creationDate'].map(lambda x: x.asm8)
        df['creationDate'] = df['creationDate'].astype(str)

        df['startDate'] = pd.to_datetime(df['startDate'])
        df['startDate'] = df['startDate'].map(lambda x: x.asm8)
        df['startDate'] = df['startDate'].astype(str)

        df['endDate'] = pd.to_datetime(df['endDate'])
        df['endDate'] = df['endDate'].map(lambda x: x.asm8)
        df['endDate'] = df['endDate'].astype(str)

        for col in df_existing.columns:
            if col not in list(df.columns):
                df[col]=''


        df = df[list(df_existing.columns)]

        logger_main.info(f'-- length of EXISTING apple health data: {len(df_existing)}')
        logger_main.info(f'-- length of NEW apple health data: {len(df)}')

        # columns_to_compare_newness_list = ['user_id','type','sourceName','sourceVersion','unit','creationDate','startDate','endDate','value','device']
        columns_to_compare_newness_list = ['user_id','type','sourceName','sourceVersion','unit','creationDate','startDate','endDate','value']
       
        df_existing.set_index(columns_to_compare_newness_list, inplace=True)

        df.set_index(columns_to_compare_newness_list, inplace=True)
        
        df_existing.head(2)
        df.head(2)


        df = df[~df.index.isin(df_existing.index)]
        df.reset_index(inplace=True)
        df.drop(columns=['id'], inplace=True)
        logger_main.info(f'-- length of NEW apple health data: {len(df)}')

    else:
        #convert df_existing to normalized date string
        df['creationDate'] = pd.to_datetime(df['creationDate'])
        df['creationDate'] = df['creationDate'].map(lambda x: x.asm8)
        df['creationDate'] = df['creationDate'].astype(str)

        df['startDate'] = pd.to_datetime(df['startDate'])
        df['startDate'] = df['startDate'].map(lambda x: x.asm8)
        df['startDate'] = df['startDate'].astype(str)

        df['endDate'] = pd.to_datetime(df['endDate'])
        df['endDate'] = df['endDate'].map(lambda x: x.asm8)
        df['endDate'] = df['endDate'].astype(str)



        logger_main.info(f'-- length of NEW apple health data: {len(df)}')


 
    #Adding apple health to DATABASE
    logger_main.info('-- Adding new data to db via df.to_sql')
    
    df.to_sql('apple_health_export', con=engine, if_exists='append', index=False)

    logger_main.info('* Successfully added xml to database!')
    return len(df)


def clear_df_files(USER_ID):
    logger_main.info('-- in users/utilsApple.py def clear_df_files --')
    list_of_df_files = os.listdir(current_app.config.get('DF_FILES_DIR'))
    search_for_string = f"user{USER_ID}_df_apple_health"
    for file in list_of_df_files:
        if file.find(search_for_string) > -1:
            os.remove(os.path.join(current_app.config.get('DF_FILES_DIR'), file))


    # open user_browse_apple health
    apple_browse_user_filename = f"user{USER_ID}_df_browse_apple.pkl"
    if os.path.exists(os.path.join(current_app.config.get('DF_FILES_DIR'), apple_browse_user_filename)):

        df_browse = pd.read_pickle(os.path.join(current_app.config.get('DF_FILES_DIR'), apple_browse_user_filename))

        #find items that have been created
        # type_formatted_series = df_browse[df_browse['df_file_existing']=='true'].type_formatted
        type_formatted_series = df_browse[df_browse['df_file_created']=='true'].type_formatted

        #delete those
        for apple_type in type_formatted_series:
            file_name = f'user{USER_ID}_df_{apple_type.replace(" ", "_").lower()}.pkl'
            os.remove(os.path.join(current_app.config.get('DF_FILES_DIR'), file_name))

        #then delete user_df_browse_apple
        os.remove(os.path.join(current_app.config.get('DF_FILES_DIR'), apple_browse_user_filename))

