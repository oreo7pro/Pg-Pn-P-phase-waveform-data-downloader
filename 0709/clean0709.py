import os
import sys
import obspy
import numpy as np
import pandas as pd
import obspy.taup.taup_geo as geo


# ============================================================
# 路径配置（无需手动修改）
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
EVENT_DIR = os.path.join(DATA_DIR, "EVENT")
STATION_CSV_DIR = os.path.join(DATA_DIR, "STATIONCSV")
PREDATA_DIR = os.path.join(DATA_DIR, "predata")


def plot_progress_bar(present_count:int, sum_count:int, bar_length:int=30)->None:
     """
     绘制进度条
     """
     if sum_count <= 0:
         sum_count = 1
     percent = int(present_count)*100 / int(sum_count)
     arrow = '-' * int(percent/100 * bar_length - 1) + '>'
     spaces = ' ' * (bar_length - len(arrow))
     sys.stdout.write('\r处理进度: [{}{}] {:.2f}%'.format(arrow, spaces, percent))  
     sys.stdout.flush()
     return None


def cleaningbytime(cat_path:str, cat_name:str, sta_path:str, 
                   sta_name:str, cleantime_path:str, cleantime_name:str)->None:
    """
    清洗掉发震时间不在台站有效工作时间的数据
    """
    print(f"\n--- 步骤 1: 正在清洗时间不在工作范围内的数据 ({cat_name}) ---")
    
    with open(file=cat_path + '/' + cat_name, mode='r', encoding='gbk') as f1:
        evt_all_data = pd.read_csv(filepath_or_buffer=f1, low_memory=False, encoding='gbk')

    with open(file=sta_path + '/' + sta_name, mode='r', encoding='utf-8') as f2:
        sta_all_data = pd.read_csv(filepath_or_buffer=f2, low_memory=False, encoding='utf-8')

    tem_time_dict = {'event_time':[], 'event_lo':[], 'event_la':[], 'event_dp_km':[], 
                     'mag':[], 'magType':[], 'network':[], 'station':[], 
                     'station_lo':[], 'station_la':[], 'station_el_m':[], 
                     'start_time':[], 'end_time':[]}

    evt_times = evt_all_data['time'].tolist()
    evt_lons = evt_all_data['longitude'].tolist()
    evt_lats = evt_all_data['latitude'].tolist()
    evt_deps = evt_all_data['depth'].tolist()
    evt_mags = evt_all_data['mag'].tolist()
    evt_magts = evt_all_data['magType'].tolist()

    sta_nets = sta_all_data['Network'].tolist()
    sta_stas = sta_all_data['Station'].tolist()
    sta_lons = sta_all_data['Longitude'].tolist()
    sta_lats = sta_all_data['Latitude'].tolist()
    sta_els = sta_all_data['Elevation'].tolist()
    sta_starts = sta_all_data['StartTime'].tolist()
    sta_ends = sta_all_data['EndTime'].tolist()

    sta_parsed_times = []
    for i in range(len(sta_starts)):
        try:
            st = obspy.UTCDateTime(str(sta_starts[i]))
        except Exception:
            st = obspy.UTCDateTime('1900-01-01T00:00:00')
            
        try:
            et = obspy.UTCDateTime(str(sta_ends[i]))
        except Exception:
            et = obspy.UTCDateTime('2599-12-31T00:00:00')
            
        sta_parsed_times.append((st, et))

    evt_count = len(evt_times)
    sta_count = len(sta_stas)

    for evt_row in range(evt_count):
        try:
            event_time = obspy.UTCDateTime(str(evt_times[evt_row]))
        except Exception:
            continue
        
        for sta_row in range(sta_count):
            start_time, end_time = sta_parsed_times[sta_row]

            if start_time <= event_time <= end_time:
                tem_time_dict['event_time'].append(evt_times[evt_row])
                tem_time_dict['event_lo'].append(evt_lons[evt_row])
                tem_time_dict['event_la'].append(evt_lats[evt_row])
                tem_time_dict['event_dp_km'].append(evt_deps[evt_row])
                tem_time_dict['mag'].append(evt_mags[evt_row])
                tem_time_dict['magType'].append(evt_magts[evt_row])
                tem_time_dict['network'].append(sta_nets[sta_row])
                tem_time_dict['station'].append(sta_stas[sta_row])
                tem_time_dict['station_lo'].append(sta_lons[sta_row])
                tem_time_dict['station_la'].append(sta_lats[sta_row])
                tem_time_dict['station_el_m'].append(sta_els[sta_row])
                tem_time_dict['start_time'].append(sta_starts[sta_row])
                tem_time_dict['end_time'].append(sta_ends[sta_row])

        plot_progress_bar(present_count=evt_row, sum_count=evt_count-1)

    print("\n正在保存清洗后的时间数据...")
    cleaningtime_df = pd.DataFrame(data=tem_time_dict)
    cleaningtime_df.to_csv(path_or_buf=cleantime_path+'/'+cleantime_name, index=False, encoding='utf-8')
    print("步骤 1 完成。")
    return None


def getdis(cleantime_path:str, cleantime_name:str, cleandis_path:str, cleandis_name:str)->None:
    """
    计算震中距
    """
    print("\n--- 步骤 2: 正在计算震中距 ---")
    
    with open(file=cleantime_path + '/' + cleantime_name, mode='r', encoding='utf-8') as f1:
        all_data = pd.read_csv(filepath_or_buffer=f1, low_memory=False, encoding='utf-8')

    tem_dis_dict = {'event_time':[], 'event_lo':[], 'event_la':[], 'event_dp_km':[], 
                    'mag':[], 'magType':[], 'network':[], 'station':[], 
                    'station_lo':[], 'station_la':[], 'station_el_m':[], 
                    'start_time':[], 'end_time':[], 'dis_deg':[]}

    evt_times = all_data['event_time'].tolist()
    evt_lons = all_data['event_lo'].tolist()
    evt_lats = all_data['event_la'].tolist()
    evt_deps = all_data['event_dp_km'].tolist()
    evt_mags = all_data['mag'].tolist()
    evt_magts = all_data['magType'].tolist()
    sta_nets = all_data['network'].tolist()
    sta_stas = all_data['station'].tolist()
    sta_lons = all_data['station_lo'].tolist()
    sta_lats = all_data['station_la'].tolist()
    sta_els = all_data['station_el_m'].tolist()
    sta_starts = all_data['start_time'].tolist()
    sta_ends = all_data['end_time'].tolist()

    total_count = len(evt_times)

    for row in range(total_count):
        station_la = float(sta_lats[row])
        station_lo = float(sta_lons[row])
        event_la = float(evt_lats[row])
        event_lo = float(evt_lons[row])

        dis = geo.calc_dist(source_latitude_in_deg=event_la, 
                            source_longitude_in_deg=event_lo, 
                            receiver_latitude_in_deg=station_la, 
                            receiver_longitude_in_deg=station_lo, 
                            radius_of_planet_in_km=6378.1370, 
                            flattening_of_planet=0.0033528106647474805)
        
        tem_dis_dict['event_time'].append(evt_times[row])
        tem_dis_dict['event_lo'].append(evt_lons[row])
        tem_dis_dict['event_la'].append(evt_lats[row])
        tem_dis_dict['event_dp_km'].append(evt_deps[row])
        tem_dis_dict['mag'].append(evt_mags[row])
        tem_dis_dict['magType'].append(evt_magts[row])
        tem_dis_dict['network'].append(sta_nets[row])
        tem_dis_dict['station'].append(sta_stas[row])
        tem_dis_dict['station_lo'].append(sta_lons[row])
        tem_dis_dict['station_la'].append(sta_lats[row])
        tem_dis_dict['station_el_m'].append(sta_els[row])
        tem_dis_dict['start_time'].append(sta_starts[row])
        tem_dis_dict['end_time'].append(sta_ends[row])
        tem_dis_dict['dis_deg'].append(dis)

        if row % 1000 == 0 or row == total_count - 1:
            plot_progress_bar(present_count=row, sum_count=total_count-1)
    
    print("\n正在保存震中距数据...")
    cleaningdis_df = pd.DataFrame(data=tem_dis_dict)
    cleaningdis_df.to_csv(path_or_buf=cleandis_path+'/'+cleandis_name, index=False, encoding='utf-8')
    print("步骤 2 完成。")
    return None 


def cleaningbydis(cleandis_path:str, cleandis_name:str, meta_path:str, meta_name:str, mindis:float, maxdis:float)->None:
    """
    获得清洗完毕后的元数据 (根据震中距范围过滤)
    """
    print(f"\n--- 步骤 3: 正在提取震中距 {mindis} ~ {maxdis} 的数据 ---")
    
    with open(file=cleandis_path + '/' + cleandis_name, mode='r', encoding='utf-8') as f1:
        all_data = pd.read_csv(filepath_or_buffer=f1, low_memory=False, encoding='utf-8')

    filtered_data = all_data[(all_data['dis_deg'] >= mindis) & (all_data['dis_deg'] <= maxdis)]
    
    plot_progress_bar(present_count=1, sum_count=1)

    print(f"\n正在保存文件: {meta_name}")
    filtered_data.to_csv(path_or_buf=meta_path+'/'+meta_name, index=False, encoding='utf-8')
    print("提取完毕。")
    return None


if __name__ == '__main__':

    # =========================================================================
    # 【只需修改这里的参数】
    # =========================================================================

    TARGET_YEAR = "2008" 

    # =========================================================================


    OUT_PATH = os.path.join(PREDATA_DIR, TARGET_YEAR)
    os.makedirs(OUT_PATH, exist_ok=True)

    # step1：匹配时间
    cleaningbytime(cat_path=EVENT_DIR, 
                   cat_name=f'events_{TARGET_YEAR}.csv', 
                   sta_path=STATION_CSV_DIR, 
                   sta_name=f'gmap-stations_{TARGET_YEAR}.csv', 
                   cleantime_path=OUT_PATH, 
                   cleantime_name=f'1.1_{TARGET_YEAR}_events.csv')
    
    # step2：计算震中距
    getdis(cleantime_path=OUT_PATH, 
           cleantime_name=f'1.1_{TARGET_YEAR}_events.csv', 
           cleandis_path=OUT_PATH, 
           cleandis_name=f'1.2_{TARGET_YEAR}_events.csv')
    
    # step3：根据震中距范围切分数据
    print("\n--- 正在批量切分保存不同震中距范围的数据 ---")
    
    cleaningbydis(cleandis_path=OUT_PATH, 
                  cleandis_name=f'1.2_{TARGET_YEAR}_events.csv', 
                  meta_path=OUT_PATH, 
                  meta_name=f'1.3_{TARGET_YEAR}_events_0_2.csv',  
                  mindis=0.0, maxdis=2.0)
                  
    cleaningbydis(cleandis_path=OUT_PATH, 
                  cleandis_name=f'1.2_{TARGET_YEAR}_events.csv', 
                  meta_path=OUT_PATH, 
                  meta_name=f'1.3_{TARGET_YEAR}_events_2_18.csv', 
                  mindis=2.0, maxdis=18.0)
                  
    cleaningbydis(cleandis_path=OUT_PATH, 
                  cleandis_name=f'1.2_{TARGET_YEAR}_events.csv', 
                  meta_path=OUT_PATH, 
                  meta_name=f'1.3_{TARGET_YEAR}_events_18_30.csv', 
                  mindis=18.0, maxdis=30.0)

    print("\n所有数据分组提取完毕！保存在目录:", OUT_PATH)

    #nohup sh -c "python clean0709.py && python get_travel_times_0709.py" > Process_all.log 2>&1 &
