# 地震波形数据下载程序使用说明

## 程序概述

本程序用于从全球地震台网下载指定震相的波形数据，完整流程包括：
1. 台站数据格式转换（TXT → CSV）
2. 地震事件与台站时间匹配、震中距计算、数据分组
3. 理论走时计算、波形截取时间窗口生成
4. 并行下载波形数据

---

## 目录结构

```
seis-download/
├── 0709/                          # Python 脚本目录
│   ├── stationtxt2csv.py          # 步骤 0：台站 TXT 转 CSV
│   ├── clean0709.py               # 步骤 1-3：数据清洗与分组
│   ├── get_travel_times_0709.py   # 步骤 4-6：走时计算与 1.6 文件生成
│   └── waveform_download_para.py  # 步骤 7：波形下载
├── data/
│   ├── EVENT/                     # 地震事件 CSV（按年份命名）
│   ├── STATIONTXT/                # 台站 TXT 原始文件
│   ├── STATIONCSV/                # 台站 CSV（自动生成）
│   ├── predata/                   # 中间数据与最终结果
│   │   └── {年份}/               # 按年份自动创建
│   │       ├── 1.1_ ~ 1.3_       # 清洗与分组结果
│   │       ├── 1.4_ ~ 1.6_       # 走时计算结果（1.6 为下载输入）
│   │       ├── 1.7_              # 下载进度表（自动生成）
│   │       └── download_parallel.log
│   └── waveforms/                 # 下载的波形文件
│       └── {震相}/{年份}/
```

---

## 快速开始

### 第一步：准备数据文件

下载并将以下文件放入 `data/` 对应目录：

| 文件 | 存放目录 | 命名格式 |
|------|----------|----------|
| 地震事件数据 | `data/EVENT/` | `events_{年份}.csv` |
| 台站数据（TXT） | `data/STATIONTXT/` | `gmap-stations_{年份}.txt` |


1. 地震事件目录下载网址：https://earthquake.usgs.gov/earthquakes/search/

    设置筛选条件，⼀次下载⼀年的数据，xxxx-1-1 00:00:00 ~ xxxx-12-31 23:59:59，
在输出选项⾥把下载格式改为CSV。

2. 台站目录下载网址：ds.iris.edu/gmap/

    如果打不开这个⽹站，可以打开VPN之后再试试。
同样⼀次下载⼀年的数据，只设置开始时间与结束时间，范围与1中设置的相同，设置
好之后点⼀下最上⾯的Update Map，然后最下⾯的下载格式改为TEXT就可以下载
了。

### 第二步：修改参数

打开每个脚本，只需修改 **配置区参数**：

```python
TARGET_YEAR = "2008"       # 目标年份
TARGET_PHASE = "Pg"        # 目标震相（仅下载脚本需要修改此项）
TARGET_DIST = "0_2"        # 距离范围（仅下载脚本需要修改此项）
```

> **文件路径无需修改**

### 第三步：按顺序运行

```bash
# 进入脚本目录
cd 0709

# 步骤 0：台站数据转换（每个年份运行一次）
python stationtxt2csv.py

# 步骤 1-3：数据清洗与分组
python clean0709.py

# 步骤 4-6：走时计算，生成 1.6 文件
python get_travel_times_0709.py

# 步骤 7：下载波形
python waveform_download_para.py
```

**因为预处理时间和下载时间会持续很久，推荐使用以下命令后台运行下载程序：**

```bash
# 一键运行全部清洗与走时计算
nohup sh -c "python clean0709.py && python get_travel_times_0709.py" > Process_all.log 2>&1 &

# 后台运行下载
nohup python -u waveform_download_para.py > /dev/null 2>&1 &
```

---

## 文件编号说明

| 编号 | 内容 | 生成脚本 |
|------|------|----------|
| 1.1 | 时间匹配后的事件-台站对 | `clean0709.py` |
| 1.2 | 添加震中距列 | `clean0709.py` |
| 1.3 | 按距离范围分组（0\_2 / 2\_18 / 18\_30） | `clean0709.py` |
| 1.4 | 添加理论走时列 | `get_travel_times_0709.py` |
| 1.5 | 筛除走时异常数据 | `get_travel_times_0709.py` |
| 1.6 | 添加波形截取时间窗口（**下载输入文件**） | `get_travel_times_0709.py` |
| 1.7 | 下载结果与进度（**断点续传依据**） | `waveform_download_para.py` |

---

## 断点续传

下载中断后，修改 `waveform_download_para.py` 中的 `START_ROW` 为上次中断的行号，重新运行即可从断点继续：

```python
START_ROW = 960   # 从第 960 行继续
```

> 1.7 文件会自动保存在年份文件夹中，与 1.6 文件同目录。

---

## 参数配置说明

### waveform_download_para.py 全局参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_WORKERS` | 30 | 并发下载线程数 |
| `FDSN_TIMEOUT` | 30 | 单次 FDSN 请求超时（秒） |
| `MAX_RETRIES` | 1 | 失败后重试次数 |
| `BATCH_SIZE` | 300 | 每批提交的任务数 |
| `SAVE_EVERY_BATCHES` | 8 | 每 N 个 batch 保存一次进度 |

### 距离-震相对应关系（在 get_travel_times_0709.py 中配置）

| 距离范围 | 默认震相 |
|----------|----------|
| 0° ~ 2° | Pg |
| 2° ~ 18° | Pn |
| 18° ~ 30° | P |

---

## 常见问题

**Q: 切换年份/项目时需要改路径吗？**
A: 不需要。只需修改脚本顶部的 `TARGET_YEAR` 等参数，文件路径会自动推导。

**Q: 1.6 文件在哪里生成？**
A: 在 `data/predata/{年份}/` 目录下，由 `get_travel_times_0709.py` 自动生成。

**Q: 下载脚本找不到 1.6 文件？**
A: 确认 `TARGET_YEAR`、`TARGET_PHASE`、`TARGET_DIST` 三个参数与 1.6 文件名完全匹配。

**Q: 如何更换波形存储位置？**
A: 修改 `waveform_download_para.py` 顶部的 `WAVEFORM_DIR` 变量即可。

**Q: 需要的环境与运行依赖库是什么？**
A: 我在python3.9运行的该程序，不确定其他条件下会不会报错之类的，如果报错，可以依照以下流程配置一个新环境：

安装 Miniconda 并配置环境：
```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda
source ~/miniconda/bin/activate
conda init
```
创建一个 seis 环境并安装老版本库：
```bash
conda create -n seis python=3.9 -y
conda activate seis
pip install pandas==1.4.1 obspy==1.4.0 scipy==1.10.1
```