# ============================================================
# 服务器后台运行：
#
# nohup python -u waveform_download_para.py > /dev/null 2>&1 &
#
# ============================================================


import sys
import warnings
warnings.filterwarnings("ignore")

import os
import time
import logging
import obspy
import pandas as pd

from obspy.clients.fdsn import Client
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import local


# ============================================================
# 路径配置（无需手动修改）
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
PREDATA_DIR = os.path.join(DATA_DIR, "predata")
WAVEFORM_DIR = os.path.join(DATA_DIR, "waveforms")


# ============================================================
# 全局参数
# ============================================================

MAX_WORKERS = 30

FDSN_TIMEOUT = 30

MAX_RETRIES = 1

BATCH_SIZE = MAX_WORKERS * 10

SAVE_EVERY_BATCHES = 8

LOG_EVERY_TASKS = 20
LOG_EVERY_SECONDS = 10


# ============================================================
# 线程局部 Client
# ============================================================

_thread_local = local()


def get_thread_clients():

    if not hasattr(_thread_local, "clients"):

        _thread_local.clients = [

            Client(
                "https://service.earthscope.org",
                timeout=FDSN_TIMEOUT
            ),

            Client(
                "GFZ",
                timeout=FDSN_TIMEOUT
            ),

            Client(
                "RESIF",
                timeout=FDSN_TIMEOUT
            ),

            Client(
                "SCEDC",
                timeout=FDSN_TIMEOUT
            ),

            Client(
                "GEOFON",
                timeout=FDSN_TIMEOUT
            ),

            Client(
                "USP",
                timeout=FDSN_TIMEOUT
            )
        ]

    return _thread_local.clients


# ============================================================
# Logger
# ============================================================

def setup_logger(
        filename,
        log_file_path,
        level=logging.INFO
    ):

    logger = logging.getLogger(filename)

    logger.setLevel(level)

    if logger.hasHandlers():

        logger.handlers.clear()

    file_handler = logging.FileHandler(
        log_file_path,
        mode="a",
        encoding="utf-8"
    )

    file_handler.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )

    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger


# ============================================================
# 单条波形下载
# ============================================================

def get_waveforms_single(
        network: str,
        station: str,
        w_start_time: str,
        w_end_time: str,
        waveforms_path: str = "",
        location: str = "*",
        channel: str = "*"
    ) -> tuple:

    """
    下载单条波形。

    返回：
        ("T", filename)  成功
        ("F", "nan")     失败
    """

    try:

        starttime = obspy.UTCDateTime(
            w_start_time
        )

        endtime = obspy.UTCDateTime(
            w_end_time
        )

    except Exception:

        return "F", "nan"

    try:

        time_name = obspy.UTCDateTime.strftime(
            starttime,
            "%Y.%m.%d.%H.%M.%S"
        )

        filename = (
            f"{time_name}.{network}.{station}.mseed"
        )

        filepath = os.path.join(
            waveforms_path,
            filename
        )

    except Exception:

        return "F", "nan"

    if os.path.exists(filepath):

        return "T", filename

    clients = get_thread_clients()

    for client in clients:

        for attempt in range(
            MAX_RETRIES + 1
        ):

            try:

                waveforms = client.get_waveforms(

                    network=network,

                    station=station,

                    location=location,

                    channel=channel,

                    starttime=starttime,

                    endtime=endtime,

                    attach_response=False

                )

                if (
                    waveforms is not None
                    and
                    len(waveforms) > 0
                ):

                    try:

                        waveforms.write(

                            filename=filepath,

                            format="MSEED"

                        )

                        return "T", filename

                    except Exception:

                        return "F", "nan"

            except Exception:

                if attempt < MAX_RETRIES:

                    time.sleep(0.5)

                continue

    return "F", "nan"


# ============================================================
# 并行下载
# ============================================================

def get_waveforms_parallel(
        tasks: list,
        parallel_results: dict,
        max_workers: int = MAX_WORKERS,
        download_log=None,
        progress_start: int = 0,
        total_rows: int = 0
    ) -> dict:

    future_to_index = {}

    batch_total = len(tasks)

    completed = 0

    success_count = 0

    failed_count = 0

    last_log_count = 0

    last_log_time = time.time()

    with ThreadPoolExecutor(
        max_workers=max_workers
    ) as executor:

        for index, task in enumerate(tasks):

            future = executor.submit(
                get_waveforms_single,
                **task
            )

            future_to_index[future] = index

        for future in as_completed(
            future_to_index
        ):

            index = future_to_index[future]

            try:

                good_or_bad, filename = (
                    future.result()
                )

                parallel_results[
                    "dwresult"
                ][index] = good_or_bad

                parallel_results[
                    "key"
                ][index] = filename

            except Exception:

                good_or_bad = "F"

                filename = "nan"

                parallel_results[
                    "dwresult"
                ][index] = "F"

                parallel_results[
                    "key"
                ][index] = "nan"

            completed += 1

            if good_or_bad == "T":

                success_count += 1

            else:

                failed_count += 1

            global_completed = (
                progress_start + completed
            )

            percent = (

                global_completed
                / total_rows
                * 100

                if total_rows > 0

                else 0

            )

            sys.stdout.write(

                f"\r>>> "
                f"{percent:6.2f}% | "
                f"当前批次: "
                f"{completed}/{batch_total} | "
                f"成功: "
                f"{success_count} | "
                f"失败: "
                f"{failed_count}"

            )

            sys.stdout.flush()

            now = time.time()

            if (

                completed - last_log_count
                >= LOG_EVERY_TASKS

                or

                now - last_log_time
                >= LOG_EVERY_SECONDS

                or

                completed == batch_total

            ):

                if download_log is not None:

                    download_log.info(

                        f"实时进度 | "
                        f"{global_completed}/{total_rows} | "
                        f"{percent:.2f}% | "
                        f"当前批次 "
                        f"{completed}/{batch_total} | "
                        f"成功 {success_count} | "
                        f"失败 {failed_count}"

                    )

                last_log_count = completed

                last_log_time = now

    return parallel_results


# ============================================================
# 主程序
# ============================================================

def main(
        input_csv: str,
        output_csv: str,
        waveforms_path: str,
        max_workers: int = MAX_WORKERS,
        log_get_results: bool = False,
        start_row: int = 0,
        log_path: str = ""
    ) -> None:

    download_log = setup_logger(

        filename="download_log",

        log_file_path=log_path

    )

    os.makedirs(

        waveforms_path,

        exist_ok=True

    )

    download_log.info(
        "--- 载入完整的 1.6 原始文件 ---"
    )

    all_data = pd.read_csv(

        filepath_or_buffer=input_csv,

        dtype=str

    )

    all_data = all_data.dropna(

        subset=[
            "w_start_time",
            "w_end_time"
        ]

    ).reset_index(drop=True)

    if "dwresult" not in all_data.columns:

        all_data["dwresult"] = ""

    if "key" not in all_data.columns:

        all_data["key"] = ""

    if (
        start_row > 0
        and
        os.path.exists(output_csv)
    ):

        download_log.info(
            "--- 检测到 1.7 进度表，正在恢复历史下载记录... ---"
        )

        old_data = pd.read_csv(

            filepath_or_buffer=output_csv,

            dtype=str

        )

        if (
            "dwresult" in old_data.columns
            and
            "key" in old_data.columns
        ):

            common_length = min(

                len(all_data),

                len(old_data)

            )

            all_data.loc[

                :common_length - 1,
                "dwresult"

            ] = old_data.loc[

                :common_length - 1,
                "dwresult"

            ].values

            all_data.loc[

                :common_length - 1,
                "key"

            ] = old_data.loc[

                :common_length - 1,
                "key"

            ].values

        download_log.info(

            f"--- 历史进度恢复完成！"
            f"将从第 {start_row} 行继续下载 ---"

        )

    total_rows = len(all_data)

    download_log.info(
        f"总数据量: {total_rows}"
    )

    download_log.info(
        f"并发线程数: {max_workers}"
    )

    download_log.info(
        f"Batch size: {BATCH_SIZE}"
    )

    download_log.info(
        f"每 {SAVE_EVERY_BATCHES} 个 batch 保存一次 CSV"
    )

    download_log.info(
        f"FDSN timeout: {FDSN_TIMEOUT}s"
    )

    total_success = 0

    total_failed = 0

    start_time_all = time.time()

    batch_number = 0

    for batch_start in range(

        start_row,

        total_rows,

        BATCH_SIZE

    ):

        batch_number += 1

        batch_end = min(

            batch_start + BATCH_SIZE,

            total_rows

        )

        sys.stdout.write(

            f"\n\n>>> 开始处理 "
            f"{batch_start}-{batch_end} / "
            f"{total_rows}\n"

        )

        sys.stdout.flush()

        download_log.info(

            f"========== 开始批次 "
            f"{batch_number} | "
            f"{batch_start}-{batch_end} "
            f"=========="

        )

        batch_df = all_data.iloc[

            batch_start:batch_end

        ].copy()

        batch_df["waveforms_path"] = (
            waveforms_path
        )

        get_waveforms_params = batch_df[

            [
                "network",
                "station",
                "w_start_time",
                "w_end_time",
                "waveforms_path"
            ]

        ].to_dict(

            orient="records"

        )

        batch_length = (
            batch_end - batch_start
        )

        batch_get_parallel_results = {

            "dwresult":
            [""] * batch_length,

            "key":
            [""] * batch_length

        }

        get_results = get_waveforms_parallel(

            tasks=get_waveforms_params,

            parallel_results=
            batch_get_parallel_results,

            max_workers=max_workers,

            download_log=download_log,

            progress_start=batch_start,

            total_rows=total_rows

        )

        all_data.loc[

            batch_start:
            batch_end - 1,

            "dwresult"

        ] = get_results["dwresult"]

        all_data.loc[

            batch_start:
            batch_end - 1,

            "key"

        ] = get_results["key"]

        success_count = (

            get_results[
                "dwresult"
            ].count("T")

        )

        failed_count = (

            get_results[
                "dwresult"
            ].count("F")

        )

        total_success += success_count

        total_failed += failed_count

        sys.stdout.write(
            "\n"
        )

        sys.stdout.flush()

        download_log.info(

            f"批次 {batch_number} 完成 | "
            f"范围 {batch_start}-{batch_end} | "
            f"成功 {success_count} | "
            f"失败 {failed_count} | "
            f"累计成功 {total_success} | "
            f"累计失败 {total_failed}"

        )

        should_save = (

            batch_number
            % SAVE_EVERY_BATCHES
            == 0

            or

            batch_end == total_rows

        )

        if should_save:

            all_data.to_csv(

                path_or_buf=output_csv,

                index=False,

                encoding="utf-8"

            )

            download_log.info(

                "========== [硬盘备份] "
                f"已保存至第 {batch_end} 条，"
                "当前所有进度已写入 1.7 表格 "
                "=========="

            )

            sys.stdout.write(

                f">>> [硬盘备份] "
                f"已保存至第 {batch_end} / "
                f"{total_rows} 条\n"

            )

            sys.stdout.flush()

    total_time = (
        time.time()
        - start_time_all
    )

    processed_rows = (
        total_rows - start_row
    )

    average_speed = (

        processed_rows / total_time

        if total_time > 0

        else 0

    )

    print()

    print(
        "========================================"
    )

    print(
        "全部批次下载完成！"
    )

    print(
        "========================================"
    )

    print(
        f"总数: {processed_rows}"
    )

    print(
        f"成功: {total_success}"
    )

    print(
        f"失败: {total_failed}"
    )

    print(
        f"平均速度: {average_speed:.2f} 条/s"
    )

    print(
        f"输出 CSV: {output_csv}"
    )

    print(
        f"波形目录: {waveforms_path}"
    )

    print(
        "========================================"
    )

    download_log.info(
        "========== 全部下载完成 =========="
    )

    download_log.info(
        f"总数: {processed_rows}"
    )

    download_log.info(
        f"成功: {total_success}"
    )

    download_log.info(
        f"失败: {total_failed}"
    )

    download_log.info(
        f"平均速度: {average_speed:.2f} 条/s"
    )

    return None


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":

    warnings.filterwarnings("ignore")

    print(
        "\n--- 1. 启动并行下载主程序 ---"
    )

    # ========================================================
    # 【只需修改这里的参数】
    # ========================================================

    TARGET_YEAR = 2009

    TARGET_PHASE = "Pg"

    TARGET_DIST = "0_2"

    START_ROW = 0

    # ========================================================

    YEAR_DIR = os.path.join(PREDATA_DIR, str(TARGET_YEAR))

    os.makedirs(YEAR_DIR, exist_ok=True)

    WAVE_PATH = os.path.join(
        WAVEFORM_DIR,
        TARGET_PHASE,
        str(TARGET_YEAR)
    )

    os.makedirs(WAVE_PATH, exist_ok=True)

    LOG_FILE = os.path.join(YEAR_DIR, "download_parallel.log")

    in_csv = os.path.join(
        YEAR_DIR,
        f"1.6_{TARGET_PHASE}_{TARGET_YEAR}_{TARGET_DIST}.csv"
    )

    out_csv = os.path.join(
        YEAR_DIR,
        f"1.7_{TARGET_PHASE}_{TARGET_YEAR}_{TARGET_DIST}.csv"
    )

    # ========================================================
    # 启动
    # ========================================================

    if os.path.exists(in_csv):

        print(f"--- 2. 找到输入文件: {in_csv} ---")
        print(f"--- 波形将保存至: {WAVE_PATH} ---")
        print(f"--- 日志文件: {LOG_FILE} ---")
        print(f"--- 并发线程数: {MAX_WORKERS} ---")
        print(f"--- Batch size: {BATCH_SIZE} ---")
        print(f"--- 每 {SAVE_EVERY_BATCHES} 个 batch 保存一次 CSV ---")

        main(
            input_csv=in_csv,
            output_csv=out_csv,
            waveforms_path=WAVE_PATH,
            max_workers=MAX_WORKERS,
            log_get_results=True,
            start_row=START_ROW,
            log_path=LOG_FILE
        )

    else:

        print(f"[错误] 找不到输入文件: {in_csv}")
        print(f"[提示] 请先运行 get_travel_times_0709.py 生成 1.6 文件")
