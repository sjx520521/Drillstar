import os
import logging
import random
import numpy as np
import pandas as pd
import pyqtgraph as pg
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QWidget, QMessageBox, QHBoxLayout, QLabel, QAbstractItemView,
    QCheckBox, QVBoxLayout, QScrollArea, QFrame, QSizePolicy, QComboBox
)
from PyQt5.QtCore import Qt, QAbstractTableModel, QTimer
from PyQt5.QtGui import QFont, QColor, QPen, QGuiApplication

from dataanalysis.ui.ProcessTime_ui import Ui_time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# 设置PyQtGraph全局配置
pg.setConfigOptions(
    antialias=True,
    useOpenGL=False,
    enableExperimental=False
)


class Win_ProcessTime(QWidget):
    def __init__(self, node: object):
        super().__init__()
        # 高DPI适配（需在UI初始化前设置）
        self._init_high_dpi()

        # UI初始化（使用设计器生成的UI，包含时间标签）
        self.ui = Ui_time()
        self.ui.setupUi(self)
        self.setWindowTitle("DataAnalysis [Time]")
        self.node = node

        # 数据存储
        self.df = pd.DataFrame()
        self.df_Features = pd.DataFrame()
        self.df_OutputFeatures = pd.DataFrame()
        self._df = pd.DataFrame()

        # UI相关
        self.select_para = []
        self.checked_para = []
        self.linear_Selection_dict = {}
        self.layout_dict = {}
        self.region = [0, 0]
        self.color_map = {}
        self.checkbox_dict = {}
        self.current_time_range = [None, None]
        self.draw_group_size = 1

        # PyQtGraph配置
        self.pg_config = {
            'antialias': True,
            'background': 'w',
            'grid': True,
            'line_width': 1.2,
            'major_grid_color': QColor(200, 200, 200),
            'minor_grid_color': QColor(240, 240, 240),
            'axis_font_size': 10,
            'label_font_size': 12,
            'plot_max_height': 400,
            'plot_min_height': 150,
            # 新增：时间选择框颜色（和频率、时频率一致）
            'region_pen_color': QColor(0, 122, 204),    # 蓝色边框（可根据实际颜色调整）
            'region_brush_color': QColor(0, 122, 204, 30)  # 蓝色半透明背景
        }

        # 时间轴相关
        self.time_series = {}
        self.date_series = {}
        self.time_unit = 's'
        self.display_mode = 'time'
        self.time_column = None
        self.raw_time_series = None
        self.time_array = None
        self.time_tick_interval = 1

        # 时间单位配置
        self.unit_factors = {
            's': 1,
            'min': 60,
            'h': 3600,
            'day': 86400,
            'month': 2592000,
            'year': 31536000
        }
        self.unit_thresholds = {
            's': 600,
            'min': 600,
            'h': 240,
            'day': 300,
            'month': 120
        }
        self.unit_order = ['s', 'min', 'h', 'day', 'month', 'year']

        # 直接使用UI中的时间标签（避免动态创建）
        self.label_time_range = self.ui.label_time_range

        # 初始化滚动绘图区域
        self._init_scrollable_plot_area()

        # 初始化UI和信号绑定
        self._init_ui()
        self._bind_signals()

    def _set_transfer_data(self, df: pd.DataFrame):
        self.df_OutputFeatures = df.copy() if df is not None else pd.DataFrame()
        self.ui.btn_Transfer.setEnabled(not self.df_OutputFeatures.empty)

    def _init_high_dpi(self):
        """初始化Qt高DPI适配"""
        try:
            QGuiApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
            QGuiApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
            logger.info("高DPI适配已启用")
        except Exception as e:
            logger.warning(f"高DPI适配初始化失败：{str(e)}")

    def _init_scrollable_plot_area(self):
        """初始化带滚动条的绘图区域（保留时间标签）"""
        # 1. 创建滚动区域
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # 2. 创建滚动内容窗口
        self.scroll_widget = QFrame()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setSpacing(10)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)

        # 3. 将滚动区域添加到绘图布局（时间标签已在UI中）
        self._clear_layout(self.ui.verticalLayout_draw)
        self.ui.verticalLayout_draw.addWidget(self.scroll_area)
        self.scroll_area.setWidget(self.scroll_widget)

        logger.info("滚动绘图区域初始化完成")

    def _init_ui(self):
        """初始化UI控件"""
        # 填充特征下拉框
        self.ui.btn_Load.setText("Load")
        self.ui.btn_Calculate.setText("计算选区特征")
        self.ui.btn_Transfer.setText("Transfer")
        try:
            from dataanalysis.share_DataAnalysis import ShareInfo
            for item in ShareInfo.features:
                if item != "参数":
                    self.ui.cB_Features.addItem(item)
        except ImportError:
            logger.warning("ShareInfo模块导入失败，特征下拉框未填充")

        # 默认配置
        self.ui.lE_Sample.setText("1000")
        self.ui.btn_Transfer.setEnabled(False)
        self.ui.tV_TimeFeatures.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cB_DrawMode = QComboBox(self)
        self.cB_DrawMode.addItems(["1参数/图", "2参数/图", "3参数/图"])
        self.cB_DrawMode.setCurrentIndex(0)
        self.ui.verticalLayout_2.insertWidget(1, self.cB_DrawMode)

    def _bind_signals(self):
        """绑定信号槽"""
        self.ui.btn_Load.clicked.connect(self.on_Load)
        self.ui.btn_Calculate.clicked.connect(self.on_Calculate)
        self.ui.btn_AllFeaturesCalculate.clicked.connect(self.on_All_Calculate_time_Features)
        self.ui.btn_Transfer.clicked.connect(self.on_Transfer)
        self.ui.btn_Show_Time.clicked.connect(self.on_show_time)
        self.ui.btn_Show_Date.clicked.connect(self.on_show_date)
        self.cB_DrawMode.currentIndexChanged.connect(self.on_draw_mode_changed)

    def _clear_layout(self, layout):
        """安全清空布局（不删除布局本身）"""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)  # 改为解除父控件，避免立即销毁
            elif item.layout():
                self._clear_layout(item.layout())

    def on_Load(self):
        """加载上游节点数据"""
        try:
            if self.node.getInput(0) is None:
                self.node.markDirty()
                self.node.markInvalid()
                QMessageBox.warning(self, "警告", "上游节点无输入数据！")
                return

            res = self.node.getInput(0).serialize()
            self.df = res['value'].copy()  # 复制数据避免修改上游
            if self.df.empty:
                QMessageBox.warning(self, "警告", "加载的数据为空！")
                return

            # 修正采样数
            max_sample = len(self.df)
            current_sample = int(self.ui.lE_Sample.text())
            if current_sample > max_sample or current_sample <= 0:
                self.ui.lE_Sample.setText(str(max_sample // 2 if max_sample // 2 > 0 else 1))

            # 识别时间列
            self._parse_time_column()

            self.node.eval()
            self.on_initUI()
            QMessageBox.information(self, "成功", f"加载数据成功：{self.df.shape}")
            logger.info(f"加载数据成功：{self.df.shape}")

        except Exception as e:
            self.node.markInvalid()
            QMessageBox.critical(self, "错误", f"数据加载失败：{str(e)}")
            logger.error(f"数据加载失败：{str(e)}")

    def _parse_time_column(self):
        """识别并解析时间列"""
        self.time_column = None
        self.raw_time_series = None
        self.time_array = None

        # 自动检测时间列
        time_keywords = ['time', 'date', 'timestamp', 'datetime', '时间', '日期', '时间戳']
        for col in self.df.columns:
            if any(keyword in col.lower() for keyword in time_keywords):
                try:
                    self.raw_time_series = pd.to_datetime(self.df[col], errors='raise')
                    self.time_column = col
                    self.time_array = (self.raw_time_series - self.raw_time_series.iloc[0]).dt.total_seconds().values
                    logger.info(f"识别时间列：{col}，起始时间：{self.raw_time_series.iloc[0]}")
                    return
                except Exception:
                    continue

        # 未识别到时间列时使用默认时间
        logger.warning("未识别时间列，使用默认时间序列")
        total_points = len(self.df)
        default_start = datetime.now()
        self.raw_time_series = pd.Series([default_start + timedelta(seconds=i) for i in range(total_points)])
        self.time_array = np.arange(total_points)

    def on_initUI(self):
        """初始化参数选择UI"""
        # 清空布局
        self._clear_layout(self.ui.verticalLayout_data)
        self.select_para.clear()
        self.checked_para.clear()
        self.color_map.clear()
        self.checkbox_dict.clear()

        header = self.df.columns.tolist()
        total_points = len(self.df)

        # 生成时间序列
        relative_seconds = self.time_array if self.time_array is not None else np.arange(total_points)
        self.time_unit = self._get_auto_time_unit(relative_seconds[-1])
        factor = self.unit_factors[self.time_unit]
        time_seq = relative_seconds / factor
        self.time_tick_interval = self._get_time_tick_interval(time_seq[-1])

        # 创建复选框
        for item in header:
            if item == self.time_column or not pd.api.types.is_numeric_dtype(self.df[item]):
                continue

            # 复选框布局
            h_layout = QHBoxLayout()
            checkbox = QCheckBox(item)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(lambda state, col=item: self.on_checkbox_state_changed(col, state))
            h_layout.addWidget(checkbox)
            self.ui.verticalLayout_data.addLayout(h_layout)

            # 随机颜色
            color = QColor(random.randint(30, 220), random.randint(30, 220), random.randint(30, 220))
            while color.lightness() < 50 or color.lightness() > 200:
                color = QColor(random.randint(30, 220), random.randint(30, 220), random.randint(30, 220))

            # 保存参数
            self.select_para.append(item)
            self.checked_para.append(item)
            self.checkbox_dict[item] = checkbox
            self.color_map[item] = color
            self.time_series[item] = time_seq
            self.date_series[item] = self.raw_time_series.values

        if not self.select_para:
            QMessageBox.warning(self, "警告", "无有效数值列可绘图！")

    def on_checkbox_state_changed(self, col, state):
        """复选框状态变化处理"""
        if state == Qt.Checked:
            if col not in self.checked_para:
                self.checked_para.append(col)
        else:
            if col in self.checked_para:
                self.checked_para.remove(col)

    def on_draw_mode_changed(self, index):
        self.draw_group_size = index + 1

    def _get_auto_time_unit(self, total_seconds):
        """自动转换时间单位"""
        current_unit = 's'
        while True:
            threshold = self.unit_thresholds.get(current_unit, float('inf'))
            factor = self.unit_factors[current_unit]
            total_in_unit = total_seconds / factor
            if total_in_unit >= threshold and current_unit != self.unit_order[-1]:
                current_unit = self.unit_order[self.unit_order.index(current_unit) + 1]
            else:
                break
        return current_unit

    def _get_time_tick_interval(self, total_in_unit):
        """计算时间刻度间隔"""
        intervals = [1, 2, 5, 10, 15, 20, 30, 50, 100]
        for interval in intervals:
            if 5 <= total_in_unit / interval <= 20:
                return interval
        return max(1, int(total_in_unit / 10))

    def _init_plot_layout(self, item):
        """创建绘图控件"""
        # 坐标轴配置
        font = QFont()
        font.setPixelSize(self.pg_config['axis_font_size'])
        label_font = QFont()
        label_font.setPixelSize(self.pg_config['label_font_size'])
        label_font.setBold(True)

        # X轴配置
        if self.display_mode == 'time':
            x_axis = pg.AxisItem(orientation='bottom')
            x_axis.setLabel(f'Time ({self.time_unit})', font=label_font)
            x_axis.setTickFont(font)
            x_axis.setTickSpacing(self.time_tick_interval, self.time_tick_interval / 5)
            x_axis.setRange(self.time_series[item][0], self.time_series[item][-1])
        else:
            class CustomDateAxis(pg.DateAxisItem):
                def tickStrings(self, values, scale, spacing):
                    strings = []
                    for v in values:
                        dt = datetime.fromtimestamp(v)
                        if spacing >= 86400 * 30:
                            strings.append(dt.strftime('%Y-%m'))
                        elif spacing >= 86400:
                            strings.append(dt.strftime('%Y-%m-%d'))
                        else:
                            strings.append(dt.strftime('%m-%d %H:%M'))
                    return strings

            x_axis = CustomDateAxis(orientation='bottom')
            x_axis.setLabel('Date', font=label_font)
            x_axis.setTickFont(font)
            total_seconds = (self.raw_time_series.iloc[-1] - self.raw_time_series.iloc[0]).total_seconds()
            date_tick_interval = self._get_date_tick_interval(total_seconds)
            x_axis.setTickSpacing(date_tick_interval, date_tick_interval / 5)

        # Y轴配置
        y_axis = pg.AxisItem(orientation='left')
        y_axis.setLabel(item, font=label_font)
        y_axis.setTickFont(font)
        y_axis.enableAutoSIPrefix(False)

        # 绘图控件
        plot_widget = pg.PlotWidget(axisItems={"bottom": x_axis, "left": y_axis})
        plot_widget.setBackground('w')
        plot_widget.showGrid(x=True, y=True, alpha=0.5)
        plot_widget.setClipToView(True)
        plot_widget.setDownsampling(mode='peak')
        plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        plot_widget.setMinimumHeight(self.pg_config['plot_min_height'])
        plot_widget.setMaximumHeight(self.pg_config['plot_max_height'])

        self.layout_dict[item] = plot_widget
        self.scroll_layout.addWidget(plot_widget)

    def _get_date_tick_interval(self, total_seconds):
        """计算日期刻度间隔"""
        intervals = [300, 600, 900, 1800, 3600, 10800, 21600, 43200, 86400]
        for interval in intervals:
            if 8 <= total_seconds / interval <= 25:
                return interval
        return 86400

    def _sample_data(self, x_data, y_data):
        """数据采样"""
        max_points = 5000
        if len(x_data) > max_points:
            step = len(x_data) // max_points
            return x_data[::step], y_data[::step]
        return x_data, y_data

    def _draw_plot(self, item, group_columns=None):
        """绘制单个参数曲线或分组曲线"""
        plot_widget = self.layout_dict[item]
        plot_widget.clear()
        plot_item = plot_widget.getPlotItem()
        legend = plot_item.addLegend(offset=(10, 10))

        # 数据准备
        if self.display_mode == 'time':
            x_data = self.time_series[item]
            init_start = 0
            init_end = max(1, int(len(self.df) * 0.1))
            init_region = [x_data[init_start], x_data[init_end]]
        else:
            x_data = self.raw_time_series.astype('int64') // 10 ** 9
            init_start = 0
            init_end = max(1, int(len(self.df) * 0.1))
            init_region = [x_data.iloc[init_start], x_data.iloc[init_end]]

        columns_to_draw = group_columns if group_columns else [item]
        plot_item.getAxis('left').setLabel(" / ".join(columns_to_draw))

        for column in columns_to_draw:
            y_data = self.df[column].values
            x_sampled, y_sampled = self._sample_data(x_data, y_data)

            line_width = 1 if len(x_sampled) > 8000 else self.pg_config['line_width']
            curve_pen = pg.mkPen(color=self.color_map[column], width=line_width, cosmetic=True)
            plot_item.plot(x_sampled, y_sampled, pen=curve_pen, name=column)

        # 区域选择器（修改颜色为和频率、时频率一致的蓝色）
        linear_region = pg.LinearRegionItem(
            values=init_region,
            pen=self.pg_config['region_pen_color'],    # 蓝色边框
            brush=self.pg_config['region_brush_color'],# 蓝色半透明背景
            movable=True
        )
        import functools
        linear_region.sigRegionChanged.connect(functools.partial(self.on_region_changed, item))
        plot_widget.addItem(linear_region)
        self.linear_Selection_dict[item] = linear_region

        # 初始化时间范围
        if self.current_time_range[0] is None:
            self.current_time_range = init_region
            self._update_time_range_label()

    def on_region_changed(self, item):
        """区域变化处理（修复信号绑定问题）"""
        try:
            min_x, max_x = self.linear_Selection_dict[item].getRegion()
            self.current_time_range = [min_x, max_x]

            for para, lr in self.linear_Selection_dict.items():
                if para == item:
                    continue
                lr.blockSignals(True)
                lr.setRegion([min_x, max_x])
                lr.blockSignals(False)

            # 延迟更新标签（避免频繁刷新）
            QTimer.singleShot(50, self._update_time_range_label)

        except Exception as e:
            logger.error(f"区域同步失败：{str(e)}")

    def _update_time_range_label(self):
        """更新时间范围标签"""
        if not self.time_column or self.current_time_range[0] is None:
            self.label_time_range.setText("当前选中时间：无")
            return

        # 查找时间索引
        if self.display_mode == 'time':
            # 修复：按时间显示时，先通过相对时间找到原始时间索引
            relative_time = self.current_time_range[0] * self.unit_factors[self.time_unit]
            start_idx = np.argmin(np.abs(self.time_array - relative_time))
            relative_time_end = self.current_time_range[1] * self.unit_factors[self.time_unit]
            end_idx = np.argmin(np.abs(self.time_array - relative_time_end))
        else:
            time_seq = self.raw_time_series.astype('int64') // 10 ** 9
            start_idx = np.argmin(np.abs(time_seq - self.current_time_range[0]))
            end_idx = np.argmin(np.abs(time_seq - self.current_time_range[1]))

        # 格式化时间
        start_time = self.raw_time_series.iloc[start_idx]
        end_time = self.raw_time_series.iloc[end_idx]
        start_str = start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        end_str = end_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.label_time_range.setText(f"当前选中时间：\n{start_str}\n至\n{end_str}")

    def _draw_plots(self):
        """绘制所有勾选参数的曲线"""
        try:
            if not self.checked_para:
                QMessageBox.warning(self, "警告", "未勾选任何参数！")
                return

            # 清空旧绘图
            self._clear_old_plots()

            group_size = max(1, self.draw_group_size)
            checked_groups = [
                self.checked_para[i:i + group_size]
                for i in range(0, len(self.checked_para), group_size)
            ]

            for group in checked_groups:
                primary_item = group[0]
                self._init_plot_layout(primary_item)
                self._draw_plot(primary_item, group)

            logger.info(f"绘制 {len(self.checked_para)} 个参数的{self.display_mode}图，分组大小：{group_size}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"绘图失败：{str(e)}")
            logger.error(f"绘图失败：{str(e)}")

    def _clear_old_plots(self):
        """清空绘图控件"""
        self._clear_layout(self.scroll_layout)
        self.layout_dict.clear()
        self.linear_Selection_dict.clear()
        self.current_time_range = [None, None]  # 重置时间范围

    def on_show_time(self):
        """按时间显示（修复时间轴范围）"""
        self.display_mode = 'time'
        # 重新生成时间序列（确保单位正确）
        relative_seconds = self.time_array if self.time_array is not None else np.arange(len(self.df))
        self.time_unit = self._get_auto_time_unit(relative_seconds[-1])
        factor = self.unit_factors[self.time_unit]
        for item in self.checked_para:
            self.time_series[item] = relative_seconds / factor
        self._draw_plots()

    def on_show_date(self):
        """按日期显示"""
        self.display_mode = 'date'
        self._draw_plots()

    def on_Calculate(self):
        """计算选区时域特征"""
        try:
            # 获取选中区域的索引
            if self.current_time_range[0] is None:
                QMessageBox.warning(self, "警告", "未选择时间范围！")
                return

            if self.display_mode == 'time':
                # 修复：按时间显示时的索引计算
                relative_time = self.current_time_range[0] * self.unit_factors[self.time_unit]
                start_idx = np.argmin(np.abs(self.time_array - relative_time))
                relative_time_end = self.current_time_range[1] * self.unit_factors[self.time_unit]
                end_idx = np.argmin(np.abs(self.time_array - relative_time_end))
            else:
                time_seq = self.raw_time_series.astype('int64') // 10 ** 9
                start_idx = np.argmin(np.abs(time_seq - self.current_time_range[0]))
                end_idx = np.argmin(np.abs(time_seq - self.current_time_range[1]))

            # 确保索引有效
            start_idx = max(0, start_idx)
            end_idx = min(len(self.df) - 1, end_idx)
            if start_idx >= end_idx:
                QMessageBox.warning(self, "警告", "选中区域无效！")
                return

            # 计算特征
            self._df = self.df.iloc[start_idx:end_idx + 1]
            features_list = []
            for item in self.checked_para:
                features_list.append(self._calculate_time_features(item))

            # 显示特征
            self.df_Features = pd.DataFrame(features_list, columns=self._get_feature_columns())
            self.ui.tV_TimeFeatures.setModel(PandasModel(self.df_Features))

            logger.info(f"计算 {len(self.checked_para)} 个参数的时域特征")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"特征计算失败：{str(e)}")
            logger.error(f"特征计算失败：{str(e)}")

    def _calculate_time_features(self, item):
        """计算单个参数的时域特征"""
        data = self._df[item].dropna()
        if data.empty:
            return [item] + [np.nan] * 14

        # 基础特征
        max_val = data.max()
        min_val = data.min()
        peak_to_peak = max_val - min_val
        mean_val = data.mean()
        var_val = data.var()
        std_val = data.std()
        rms_val = np.sqrt(np.mean(np.square(data)))
        skew_val = data.skew()
        kurt_val = data.kurt()

        # 衍生特征
        waveform_factor = rms_val / mean_val if mean_val != 0 else np.nan
        crest_factor = max_val / rms_val if rms_val != 0 else np.nan
        pulse_factor = max_val / mean_val if mean_val != 0 else np.nan
        sqrt_mean = np.mean(np.power(np.abs(data), 0.5))
        margin_factor = max_val / np.power(sqrt_mean, 2) if sqrt_mean != 0 else np.nan

        return [
            item, max_val, min_val, peak_to_peak, mean_val, var_val, std_val,
            rms_val, kurt_val, margin_factor, skew_val, waveform_factor,
            crest_factor, pulse_factor, margin_factor
        ]

    def _get_feature_columns(self):
        """获取特征列名"""
        try:
            from dataanalysis.share_DataAnalysis import ShareInfo
            return ShareInfo.features
        except ImportError:
            return [
                '参数名', '最大值', '最小值', '峰峰值', '均值', '方差', '标准差',
                '均方根', '峭度', '裕度因子', '偏度', '波形因子', '峰值因子', '脉冲因子', '裕度'
            ]

    def on_All_Calculate_time_Features(self):
        """批量计算时域特征"""
        try:
            sample_text = self.ui.lE_Sample.text().strip()
            if not sample_text.isdigit():
                raise ValueError("采样数必须为正整数")
            sample = int(sample_text)
            max_sample = len(self.df)
            if sample <= 0 or sample > max_sample:
                raise ValueError(f"采样数必须在1到{max_sample}之间")

            # 此处需根据ShareInfo的features_func实现，这里仅做示例
            QMessageBox.information(self, "提示", "批量特征计算功能需结合具体业务实现")

        except ValueError as e:
            QMessageBox.warning(self, "警告", str(e))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"批量计算失败：{str(e)}")

    def on_Transfer(self):
        """传输数据到下游节点"""
        try:
            if hasattr(self, 'df_Features') and not self.df_Features.empty:
                if self.node.LoadData(self.df_Features):
                    self.node.eval()
                    QMessageBox.information(self, "成功", "数据传输完成！")
                else:
                    raise ValueError("节点数据加载失败")
            else:
                QMessageBox.warning(self, "警告", "无特征数据可传输！")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"数据传输失败：{str(e)}")


class PandasModel(QAbstractTableModel):
    """Pandas DataFrame的Qt表格模型"""

    def __init__(self, data: pd.DataFrame):
        super().__init__()
        self._data = data
        self._header = data.columns.tolist()

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and role == Qt.DisplayRole:
            value = self._data.iat[index.row(), index.column()]
            if isinstance(value, (int, float, np.number)):
                return f"{value:.4f}"
            return str(value)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self._header[section]
            elif orientation == Qt.Vertical:
                return str(section)
        return None


# 外部调用函数
def create_process_time_window(node):
    return Win_ProcessTime(node)


def _time_on_load(self):
    try:
        if self.node.getInput(0) is None:
            self.node.markDirty()
            self.node.markInvalid()
            QMessageBox.warning(self, "警告", "上游节点无输入数据！")
            return

        res = self.node.getInput(0).serialize()
        self.df = res["value"].copy()
        self.df_Features = pd.DataFrame()
        self._set_transfer_data(pd.DataFrame())
        self.ui.tV_TimeFeatures.setModel(None)

        if self.df.empty:
            QMessageBox.warning(self, "警告", "加载的数据为空！")
            return

        max_sample = len(self.df)
        current_sample = int(self.ui.lE_Sample.text())
        if current_sample > max_sample or current_sample <= 0:
            self.ui.lE_Sample.setText(str(max_sample // 2 if max_sample // 2 > 0 else 1))

        self._parse_time_column()
        self.node.eval()
        self.on_initUI()
        QMessageBox.information(self, "成功", f"加载数据成功：{self.df.shape}")
        logger.info(f"加载数据成功：{self.df.shape}")

    except Exception as e:
        self.node.markInvalid()
        QMessageBox.critical(self, "错误", f"数据加载失败：{str(e)}")
        logger.error(f"数据加载失败：{str(e)}")


def _time_on_calculate(self):
    try:
        if self.current_time_range[0] is None:
            QMessageBox.warning(self, "警告", "未选择时间范围！")
            return

        if self.display_mode == "time":
            relative_time = self.current_time_range[0] * self.unit_factors[self.time_unit]
            start_idx = np.argmin(np.abs(self.time_array - relative_time))
            relative_time_end = self.current_time_range[1] * self.unit_factors[self.time_unit]
            end_idx = np.argmin(np.abs(self.time_array - relative_time_end))
        else:
            time_seq = self.raw_time_series.astype("int64") // 10 ** 9
            start_idx = np.argmin(np.abs(time_seq - self.current_time_range[0]))
            end_idx = np.argmin(np.abs(time_seq - self.current_time_range[1]))

        start_idx = max(0, start_idx)
        end_idx = min(len(self.df) - 1, end_idx)
        if start_idx >= end_idx:
            QMessageBox.warning(self, "警告", "选中区域无效！")
            return

        self._df = self.df.iloc[start_idx:end_idx + 1]
        features_list = [self._calculate_time_features(item) for item in self.checked_para]
        self.df_Features = pd.DataFrame(features_list, columns=self._get_feature_columns())
        self.ui.tV_TimeFeatures.setModel(PandasModel(self.df_Features))
        self._set_transfer_data(self.df_Features)
        logger.info(f"计算 {len(self.checked_para)} 个参数的时域特征")

    except Exception as e:
        QMessageBox.critical(self, "错误", f"特征计算失败：{str(e)}")
        logger.error(f"特征计算失败：{str(e)}")


def _time_get_target_columns(self):
    target_columns = list(self.checked_para)
    if target_columns:
        return target_columns
    return [
        col for col in self.df.columns
        if col != self.time_column and pd.api.types.is_numeric_dtype(self.df[col])
    ]


def _time_compute_feature_output(self, data, feature_name):
    clean_data = pd.Series(data).dropna()
    if clean_data.empty:
        return np.nan

    columns = self._get_feature_columns()
    max_val = clean_data.max()
    min_val = clean_data.min()
    mean_val = clean_data.mean()
    var_val = clean_data.var()
    std_val = clean_data.std()
    rms_val = np.sqrt(np.mean(np.square(clean_data)))
    skew_val = clean_data.skew()
    kurt_val = clean_data.kurt()
    waveform_factor = rms_val / mean_val if mean_val != 0 else np.nan
    crest_factor = max_val / rms_val if rms_val != 0 else np.nan
    pulse_factor = max_val / mean_val if mean_val != 0 else np.nan
    sqrt_mean = np.mean(np.power(np.abs(clean_data), 0.5))
    margin_factor = max_val / np.power(sqrt_mean, 2) if sqrt_mean != 0 else np.nan

    feature_map = {
        columns[1]: max_val,
        columns[2]: min_val,
        columns[3]: max_val - min_val,
        columns[4]: mean_val,
        columns[5]: var_val,
        columns[6]: std_val,
        columns[7]: rms_val,
        columns[8]: kurt_val,
        columns[9]: margin_factor,
        columns[10]: skew_val,
        columns[11]: waveform_factor,
        columns[12]: crest_factor,
        columns[13]: pulse_factor,
        columns[14]: margin_factor,
    }
    return feature_map.get(feature_name, np.nan)


def _time_on_all_calculate(self):
    try:
        sample_text = self.ui.lE_Sample.text().strip()
        if not sample_text.isdigit():
            raise ValueError("采样点数必须为正整数！")

        sample = int(sample_text)
        max_sample = len(self.df)
        if sample <= 0 or sample > max_sample:
            raise ValueError(f"采样点数必须在 1 到 {max_sample} 之间")

        feature_name = self.ui.cB_Features.currentText().strip()
        if not feature_name:
            raise ValueError("请先选择要输出的时域特征")

        target_columns = self._get_target_columns()
        if not target_columns:
            raise ValueError("当前没有可用的数值列")

        records = []
        for start_idx in range(0, len(self.df), sample):
            end_idx = min(start_idx + sample, len(self.df))
            window_df = self.df.iloc[start_idx:end_idx]
            if window_df.empty:
                continue

            record = {
                "WindowIndex": len(records) + 1,
                "StartIndex": start_idx,
                "EndIndex": end_idx - 1,
            }
            if self.time_column and self.raw_time_series is not None:
                record["StartTime"] = str(self.raw_time_series.iloc[start_idx])
                record["EndTime"] = str(self.raw_time_series.iloc[end_idx - 1])

            for col in target_columns:
                record[col] = self._compute_feature_output(window_df[col], feature_name)

            records.append(record)

        output_df = pd.DataFrame(records)
        if output_df.empty:
            raise ValueError("未生成有效的特征输出数据")

        self.ui.tV_TimeFeatures.setModel(PandasModel(output_df))
        self._set_transfer_data(output_df)
        QMessageBox.information(self, "成功", f"已生成 {feature_name} 的时域特征输出")

    except ValueError as e:
        QMessageBox.warning(self, "警告", str(e))
    except Exception as e:
        QMessageBox.critical(self, "错误", f"批量计算失败：{str(e)}")


def _time_on_transfer(self):
    try:
        if not self.df_OutputFeatures.empty:
            if self.node.LoadData(self.df_OutputFeatures):
                self.node.eval()
                QMessageBox.information(self, "成功", "数据传输完成！")
            else:
                raise ValueError("节点数据加载失败")
        else:
            QMessageBox.warning(self, "警告", "无特征数据可传输！")

    except Exception as e:
        QMessageBox.critical(self, "错误", f"数据传输失败：{str(e)}")


def _time_set_busy_state(self, busy):
    widgets = [
        self.ui.btn_Load,
        self.ui.btn_Calculate,
        self.ui.btn_AllFeaturesCalculate,
        self.ui.btn_Show_Time,
        self.ui.btn_Show_Date,
        self.ui.btn_Transfer,
    ]
    for widget in widgets:
        widget.setEnabled(not busy)
    if not busy:
        self.ui.btn_Transfer.setEnabled(not self.df_OutputFeatures.empty)


def _time_feature_row(window_df, item, feature_columns):
    data = window_df[item].dropna()
    if data.empty:
        return [item] + [np.nan] * (len(feature_columns) - 1)

    max_val = data.max()
    min_val = data.min()
    mean_val = data.mean()
    var_val = data.var()
    std_val = data.std()
    rms_val = np.sqrt(np.mean(np.square(data)))
    skew_val = data.skew()
    kurt_val = data.kurt()
    peak_to_peak = max_val - min_val
    waveform_factor = rms_val / mean_val if mean_val != 0 else np.nan
    crest_factor = max_val / rms_val if rms_val != 0 else np.nan
    pulse_factor = max_val / mean_val if mean_val != 0 else np.nan
    sqrt_mean = np.mean(np.power(np.abs(data), 0.5))
    margin_factor = max_val / np.power(sqrt_mean, 2) if sqrt_mean != 0 else np.nan

    return [
        item,
        max_val,
        min_val,
        peak_to_peak,
        mean_val,
        var_val,
        std_val,
        rms_val,
        kurt_val,
        margin_factor,
        skew_val,
        waveform_factor,
        crest_factor,
        pulse_factor,
        margin_factor,
    ]


def _time_feature_value(data, feature_name, feature_columns):
    clean_data = pd.Series(data).dropna()
    if clean_data.empty:
        return np.nan

    max_val = clean_data.max()
    min_val = clean_data.min()
    mean_val = clean_data.mean()
    var_val = clean_data.var()
    std_val = clean_data.std()
    rms_val = np.sqrt(np.mean(np.square(clean_data)))
    skew_val = clean_data.skew()
    kurt_val = clean_data.kurt()
    waveform_factor = rms_val / mean_val if mean_val != 0 else np.nan
    crest_factor = max_val / rms_val if rms_val != 0 else np.nan
    pulse_factor = max_val / mean_val if mean_val != 0 else np.nan
    sqrt_mean = np.mean(np.power(np.abs(clean_data), 0.5))
    margin_factor = max_val / np.power(sqrt_mean, 2) if sqrt_mean != 0 else np.nan

    feature_map = {
        feature_columns[1]: max_val,
        feature_columns[2]: min_val,
        feature_columns[3]: max_val - min_val,
        feature_columns[4]: mean_val,
        feature_columns[5]: var_val,
        feature_columns[6]: std_val,
        feature_columns[7]: rms_val,
        feature_columns[8]: kurt_val,
        feature_columns[9]: margin_factor,
        feature_columns[10]: skew_val,
        feature_columns[11]: waveform_factor,
        feature_columns[12]: crest_factor,
        feature_columns[13]: pulse_factor,
        feature_columns[14]: margin_factor,
    }
    return feature_map.get(feature_name, np.nan)


def _time_build_feature_table(selected_df, checked_para, feature_columns):
    rows = [_time_feature_row(selected_df, item, feature_columns) for item in checked_para]
    return pd.DataFrame(rows, columns=feature_columns)


def _time_build_window_feature_output(df, target_columns, feature_name, sample, time_column, raw_time_series, feature_columns):
    records = []
    total_rows = len(df)
    for start_idx in range(0, total_rows, sample):
        end_idx = min(start_idx + sample, total_rows)
        window_df = df.iloc[start_idx:end_idx]
        if window_df.empty:
            continue

        record = {
            "WindowIndex": len(records) + 1,
            "StartIndex": start_idx,
            "EndIndex": end_idx - 1,
        }
        if time_column and raw_time_series is not None:
            record["StartTime"] = str(raw_time_series.iloc[start_idx])
            record["EndTime"] = str(raw_time_series.iloc[end_idx - 1])

        for col in target_columns:
            record[col] = _time_feature_value(window_df[col], feature_name, feature_columns)

        records.append(record)

    output_df = pd.DataFrame(records)
    if output_df.empty:
        raise ValueError("未生成有效的时域特征输出数据。")
    return output_df


def _time_finish_feature_table(self, result_df):
    self.df_Features = result_df.copy()
    self.ui.tV_TimeFeatures.setModel(PandasModel(self.df_Features))
    self._set_transfer_data(self.df_Features)
    _time_set_busy_state(self, False)
    logger.info(f"完成后台计算 {len(self.df_Features)} 条时域特征记录")


def _time_finish_feature_output(self, result_df, feature_name):
    self.ui.tV_TimeFeatures.setModel(PandasModel(result_df))
    self._set_transfer_data(result_df)
    _time_set_busy_state(self, False)
    QMessageBox.information(self, "成功", f"已生成 {feature_name} 的时域特征输出。")


def _time_handle_background_error(self, title, message):
    _time_set_busy_state(self, False)
    QMessageBox.critical(self, "错误", f"{title}：{message}")


def _time_on_calculate_async(self):
    try:
        if self.current_time_range[0] is None:
            QMessageBox.warning(self, "提示", "请先选择时间范围。")
            return

        if self.display_mode == "time":
            relative_time = self.current_time_range[0] * self.unit_factors[self.time_unit]
            start_idx = np.argmin(np.abs(self.time_array - relative_time))
            relative_time_end = self.current_time_range[1] * self.unit_factors[self.time_unit]
            end_idx = np.argmin(np.abs(self.time_array - relative_time_end))
        else:
            time_seq = self.raw_time_series.astype("int64") // 10 ** 9
            start_idx = np.argmin(np.abs(time_seq - self.current_time_range[0]))
            end_idx = np.argmin(np.abs(time_seq - self.current_time_range[1]))

        start_idx = max(0, start_idx)
        end_idx = min(len(self.df) - 1, end_idx)
        if start_idx >= end_idx:
            QMessageBox.warning(self, "提示", "当前选区无效。")
            return

        selected_df = self.df.iloc[start_idx:end_idx + 1].copy()
        checked_para = list(self.checked_para)
        feature_columns = list(self._get_feature_columns())

        from dataanalysis.async_task import BusyTaskMixin

        if not BusyTaskMixin._start_background_task(
            self,
            "时域特征",
            "正在计算选区时域特征，请稍候...",
            _time_build_feature_table,
            lambda result_df: _time_finish_feature_table(self, result_df),
            lambda message: _time_handle_background_error(self, "时域特征计算失败", message),
            selected_df,
            checked_para,
            feature_columns,
        ):
            QMessageBox.information(self, "提示", "当前已有任务在执行，请稍候。")
            return

        _time_set_busy_state(self, True)
        logger.info(f"开始后台计算 {len(checked_para)} 个参数的时域特征")

    except Exception as exc:
        QMessageBox.critical(self, "错误", f"时域特征计算失败：{exc}")
        logger.error(f"时域特征计算失败：{exc}")


def _time_compute_feature_output_async(self, data, feature_name):
    return _time_feature_value(data, feature_name, self._get_feature_columns())


def _time_on_all_calculate_async(self):
    try:
        sample_text = self.ui.lE_Sample.text().strip()
        if not sample_text.isdigit():
            raise ValueError("采样点数必须为正整数。")

        sample = int(sample_text)
        max_sample = len(self.df)
        if sample <= 0 or sample > max_sample:
            raise ValueError(f"采样点数必须在 1 到 {max_sample} 之间。")

        feature_name = self.ui.cB_Features.currentText().strip()
        if not feature_name:
            raise ValueError("请先选择要输出的时域特征。")

        target_columns = self._get_target_columns()
        if not target_columns:
            raise ValueError("当前没有可用的数值列。")

        raw_time_series = self.raw_time_series.copy() if self.raw_time_series is not None else None

        from dataanalysis.async_task import BusyTaskMixin

        if not BusyTaskMixin._start_background_task(
            self,
            "时域特征输出",
            "正在计算时域特征输出，请稍候...",
            _time_build_window_feature_output,
            lambda result_df: _time_finish_feature_output(self, result_df, feature_name),
            lambda message: _time_handle_background_error(self, "时域特征输出失败", message),
            self.df.copy(),
            target_columns,
            feature_name,
            sample,
            self.time_column,
            raw_time_series,
            list(self._get_feature_columns()),
        ):
            QMessageBox.information(self, "提示", "当前已有任务在执行，请稍候。")
            return

        _time_set_busy_state(self, True)

    except ValueError as exc:
        QMessageBox.warning(self, "提示", str(exc))
    except Exception as exc:
        QMessageBox.critical(self, "错误", f"时域特征输出失败：{exc}")


def _time_on_transfer_async(self):
    try:
        if not self.df_OutputFeatures.empty:
            if self.node.LoadData(self.df_OutputFeatures):
                self.node.eval()
                QMessageBox.information(self, "成功", "数据传递完成。")
            else:
                raise ValueError("节点数据加载失败。")
        else:
            QMessageBox.warning(self, "提示", "没有可传递的特征数据。")

    except Exception as exc:
        QMessageBox.critical(self, "错误", f"数据传递失败：{exc}")


Win_ProcessTime.on_Load = _time_on_load
Win_ProcessTime.on_Calculate = _time_on_calculate_async
Win_ProcessTime._get_target_columns = _time_get_target_columns
Win_ProcessTime._compute_feature_output = _time_compute_feature_output_async
Win_ProcessTime.on_All_Calculate_time_Features = _time_on_all_calculate_async
Win_ProcessTime.on_Transfer = _time_on_transfer_async
