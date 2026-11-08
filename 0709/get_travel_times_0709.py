import sys
import obspy
import numpy as np
import pandas as pd
from obspy.taup import TauPyModel
import os
from concurrent.futures import ProcessPoolExecutor, as_completed


# ============================================================
# 路径配置（无需手动修改）
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
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


_global_model = None


def _calc_single_taup(args):
    ev_dp, dis_deg, sta_el, phase = args
    global _global_model
    if _global_model is None:
        _global_model = TauPyModel(model='iasp91')
        
    try:
        arrivals = _global_model.get_travel_times(source_depth_in_km=ev_dp,
                                                  distance_in_degree=dis_deg, 
                                                  phase_list=[phase], 
                                                  receiver_depth_in_km=sta_el)
        return arrivals[0].time
    except Exception:
        return 0.0


def get_travel_times(meta_path:str, meta_name:str, new_meta_path:str, new_meta_name:str, phase_type:str)->None:
    print(f"\n--- 步骤 4: 正在获取 {phase_type} 震相走时 (多进程安全分块版) ---")
    
    with open(file=meta_path + '/' + meta_name, mode='r', encoding='utf-8') as f1:
        all_data = pd.read_csv(filepath_or_buffer=f1, low_memory=False, encoding='utf-8')

    evt_deps = all_data['event_dp_km'].tolist()
    sta_els = all_data['station_el_m'].tolist()
    dis_degs = all_data['dis_deg'].tolist()
    total_count = len(evt_deps)
    
    tasks = [(float(evt_deps[i]), float(dis_degs[i]), float(sta_els[i])/1000.0, phase_type) for i in range(total_count)]
    
    max_cores = 5  
    print(f"-> 启动了 {max_cores} 个进程计算，避免过热...")

    taup_list = []
    with ProcessPoolExecutor(max_workers=max_cores) as executor:
        results = executor.map(_calc_single_taup, tasks, chunksize=500)
        
        for i, res in enumerate(results):
            taup_list.append(res)
            if (i + 1) % 500 == 0 or (i + 1) == total_count:
                plot_progress_bar(present_count=i+1, sum_count=total_count)

    all_data[f'taup_{phase_type}'] = taup_list
    print("\n正在保存走时数据...")
    all_data.to_csv(path_or_buf=new_meta_path+'/'+new_meta_name, index=False, encoding='utf-8')
    return None


def clean_travel_time(meta_path:str, meta_name:str, new_meta_path:str, new_meta_name:str, phase_type:str)->None:
    """
    筛除震相走时异常(taup_pn/taup_sn=0)的数据
    """
    print(f"\n--- 步骤 5: 正在筛除 {phase_type} 走时异常数据 ---")
    
    with open(file=meta_path + '/' + meta_name, mode='r', encoding='utf-8') as f1:
        all_data = pd.read_csv(filepath_or_buffer=f1, low_memory=False, encoding='utf-8')

    filtered_data = all_data[all_data[f'taup_{phase_type}'] != 0.0]
    
    plot_progress_bar(present_count=1, sum_count=1)
    
    print("\n正在保存清洗后的走时数据...")
    filtered_data.to_csv(path_or_buf=new_meta_path+'/'+new_meta_name, index=False, encoding='utf-8')
    return None


def get_waveforms_time(meta_path:str, meta_name:str, new_meta_path:str, new_meta_name:str, phase_type:str)->None:
    """
    通过理论走时计算波形下载时的起止时间
    """
    print(f"\n--- 步骤 6: 正在计算 {phase_type} 波形下载起止时间 ---")
    
    with open(file=meta_path + '/' + meta_name, mode='r', encoding='utf-8') as f1:
        all_data = pd.read_csv(filepath_or_buffer=f1, low_memory=False, encoding='utf-8')

    evt_times = all_data['event_time'].tolist()
    taup_times = all_data[f'taup_{phase_type}'].tolist()
    total_count = len(evt_times)
    
    w_start_times = []
    w_end_times = []
    
    for row in range(total_count):
        try:
            event_time = obspy.UTCDateTime(str(evt_times[row]))
            waveforms_start_time = event_time + float(taup_times[row]) - 30.0
            waveforms_end_time = waveforms_start_time + 180.0
            
            w_start_times.append(str(waveforms_start_time))
            w_end_times.append(str(waveforms_end_time))
        except Exception:
            w_start_times.append("")
            w_end_times.append("")
    
        if row % 1000 == 0 or row == total_count - 1:
            plot_progress_bar(present_count=row, sum_count=total_count-1)
    
    all_data.insert(1, 'w_start_time', w_start_times)
    all_data.insert(2, 'w_end_time', w_end_times)
    
    print("\n正在保存包含波形起止时间的最终数据...")
    all_data.to_csv(path_or_buf=new_meta_path+'/'+new_meta_name, index=False, encoding='utf-8')
    return None


if __name__ == '__main__':

    # =========================================================================
    # 【只需修改这里的参数】
    # =========================================================================

    TARGET_YEAR = "2008"

    # 核心字典：距离后缀 对应 想要提取的震相
    distance_phase_map = {
        '0_2': 'Pg',
        '2_18': 'Pn',
        '18_30': 'P'
    }

    # =========================================================================
   

    BASE_PATH = os.path.join(PREDATA_DIR, TARGET_YEAR)
    os.makedirs(BASE_PATH, exist_ok=True)

    for i in [TARGET_YEAR]:  
        for dist_suffix, p_type in distance_phase_map.items():
            
            print(f"\n=======================================================")
            print(f" 开始处理年份: {i} | 距离范围: {dist_suffix.replace('_', '~')} | 目标震相: {p_type}")
            print(f"=======================================================")

            input_meta = f'1.3_{i}_events_{dist_suffix}.csv'
            
            full_input_path = os.path.join(BASE_PATH, input_meta)
            
            if not os.path.exists(full_input_path):
                print(f"未找到文件 {full_input_path}，自动跳过...")
                continue
            
            meta_1_4 = f'1.4_{p_type}_{i}_{dist_suffix}.csv'
            meta_1_5 = f'1.5_{p_type}_{i}_{dist_suffix}.csv'
            meta_1_6 = f'1.6_{p_type}_{i}_{dist_suffix}.csv'

            get_travel_times(meta_path=BASE_PATH, 
                             meta_name=input_meta,
                             new_meta_path=BASE_PATH, 
                             new_meta_name=meta_1_4,
                             phase_type=p_type)

            clean_travel_time(meta_path=BASE_PATH, 
                              meta_name=meta_1_4, 
                              new_meta_path=BASE_PATH, 
                              new_meta_name=meta_1_5,
                              phase_type=p_type)
            
            get_waveforms_time(meta_path=BASE_PATH,
                               meta_name=meta_1_5,
                               new_meta_path=BASE_PATH,
                               new_meta_name=meta_1_6,
                               phase_type=p_type)
