import numpy as np
import pandas as pd
import os


# ============================================================
# 路径配置（无需手动修改）
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
STATION_TXT_DIR = os.path.join(DATA_DIR, "STATIONTXT")
STATION_CSV_DIR = os.path.join(DATA_DIR, "STATIONCSV")


def stationtxt2csv(txt_path:str, txt_name:str, csv_path:str, csv_name:str)->0:

    """
    本函数用于将stationtxt文件转换并存储为csv格式
    : txt_path 类别: str: txt的存储路径
    : txt_name 类别: str: txt的存储名称
    : csv_path 类别: str: 生成csv文件的存储路径
    : csv_name 类别: str: 生成csv文件的存储名称
    return: 0
    """

    stationcsv_dict = {'Network':[], 'Station':[], 'Latitude':[], 'Longitude':[],
                       'Elevation':[], 'SiteName':[], 'StartTime':[], 'EndTime':[]}
    
    stationtxt_df = pd.read_csv(filepath_or_buffer=txt_path+'/'+txt_name, 
                             sep = '|', 
                             dtype = 'str')

    for row in np.arange(0, stationtxt_df.shape[0]):
        stationcsv_dict['Network'].append(stationtxt_df.loc[row][0])
        stationcsv_dict['Station'].append(stationtxt_df.loc[row][1])
        stationcsv_dict['Latitude'].append(stationtxt_df.loc[row][2])
        stationcsv_dict['Longitude'].append(stationtxt_df.loc[row][3])
        stationcsv_dict['Elevation'].append(stationtxt_df.loc[row][4])
        stationcsv_dict['SiteName'].append(stationtxt_df.loc[row][5])
        stationcsv_dict['StartTime'].append(stationtxt_df.loc[row][6])
        stationcsv_dict['EndTime'].append(stationtxt_df.loc[row][7])

        print('='*30, '第{}个台站处理完成'.format(row), '='*30, '\n')

    stationcsv_df = pd.DataFrame(data=stationcsv_dict)
    stationcsv_df.to_csv(path_or_buf=csv_path+'/'+csv_name, index=False, encoding='utf-8')

    print('='*30, '文件处理完成', '='*30)

    return 0 


if __name__ == '__main__':

    # =========================================================================
    # 【只需修改这里的参数】
    # =========================================================================

    TARGET_YEAR = "2008"

    # =========================================================================

    os.makedirs(STATION_CSV_DIR, exist_ok=True)

    stationtxt2csv(txt_path=STATION_TXT_DIR, 
                   txt_name=f'gmap-stations_{TARGET_YEAR}.txt', 
                   csv_path=STATION_CSV_DIR, 
                   csv_name=f'gmap-stations_{TARGET_YEAR}.csv')
