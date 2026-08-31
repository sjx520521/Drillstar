import re
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from dataanalysis.ui.oilFuncTimeConv_ui import Ui_OilFuncTimeConv

# --------------------------
# 全局配置（性能调优）
# --------------------------
CHUNK_SIZE = 16384  # 分块大小（2^14，CPU缓存友好）
MAX_DISPLAY_ROWS = 1000  # 表格最大展示行数


# --------------------------
# 异步加载数据线程（无锁+全量加载）
# --------------------------
class DataLoadThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(pd.DataFrame, list)
    error = pyqtSignal(str)

    def __init__(self, node):
        super().__init__()
        self.node = node
        self.setPriority(QThread.LowPriority)  # 降低线程优先级，不抢占UI资源

    def run(self):
        try:
            self.progress.emit(5, "获取上游数据...")
            # 安全检查
            if not hasattr(self.node, 'getInput'):
                self.error.emit("节点无getInput方法！")
                return
            if self.node.getInput(0) is None:
                self.error.emit("上游节点无输入数据！")
                return

            # 全量加载数据（不限制行数）
            res = self.node.getInput(0).serialize()
            # 兼容修复：支持serialize返回DataFrame或字典
            df = res if isinstance(res, pd.DataFrame) else res.get('value', pd.DataFrame())
            if df.empty:
                self.error.emit("加载的数据为空！")
                return

            # 数据类型优化（减少内存占用）
            self.progress.emit(50, "优化数据类型...")
            for col in df.columns:
                if df[col].dtype == 'object' and not pd.api.types.is_datetime64_any_dtype(df[col]):
                    try:
                        df[col] = df[col].astype('category')  # 分类类型减少内存
                    except:
                        pass  # 避免转换失败导致崩溃

            self.progress.emit(100, "数据加载完成！")
            self.finished.emit(df, df.columns.tolist())

        except Exception as e:
            self.error.emit(f"加载失败：{str(e)}")


# --------------------------
# 异步转换数据线程（向量化+增量合并+日期修复）
# --------------------------
class DataConvertThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(pd.DataFrame, pd.DataFrame)  # 全量数据+展示数据
    error = pyqtSignal(str)

    def __init__(self, df_original, time_col, target_time, output_format, selected_cols):
        super().__init__()
        self.df_original = df_original
        self.time_col = time_col
        self.target_time = target_time
        self.output_format = output_format
        self.selected_cols = selected_cols
        self.setPriority(QThread.NormalPriority)
        self.is_running = True  # 线程运行标志
        # 预计算全局基准时间和时间差（关键修复）
        self.global_base_time = None
        self._calc_global_base()

    def stop(self):
        self.is_running = False  # 优雅停止，避免强制终止

    def _calc_global_base(self):
        """预计算全局基准时间（整个数据集的第一个有效时间戳）"""
        if self.time_col not in self.df_original.columns:
            return
        time_series = self.df_original[self.time_col].dropna()
        if not time_series.empty:
            # 转换为datetime获取全局基准
            temp_series = pd.to_datetime(time_series, errors='coerce').dropna()
            if not temp_series.empty:
                self.global_base_time = temp_series.iloc[0]

    def run(self):
        try:
            if not self.is_running:
                return

            # 预检测时间格式（仅一次）
            input_format = self._detect_time_format()
            total_rows = len(self.df_original)
            total_chunks = (total_rows + CHUNK_SIZE - 1) // CHUNK_SIZE
            df_converted_all = []
            processed_rows = 0

            self.progress.emit(0, "初始化转换...")

            # 若无全局基准，直接返回错误
            if self.global_base_time is None:
                self.error.emit("数据中无有效时间戳！")
                return

            # 计算全局时间差（目标时间 - 全局基准时间）
            global_time_diff = self.target_time - self.global_base_time

            # 分块处理（增量合并，避免大列表占用内存）
            for i in range(total_chunks):
                if not self.is_running:
                    raise Exception("用户终止转换")

                # 计算分块索引
                start = i * CHUNK_SIZE
                end = min((i + 1) * CHUNK_SIZE, total_rows)
                chunk = self.df_original.iloc[start:end].copy()

                # 进度更新
                processed_rows += len(chunk)
                progress = int(processed_rows / total_rows * 85)
                self.progress.emit(progress, f"处理中 {processed_rows}/{total_rows} 行")

                # 时间转换（向量化+全局基准修复）
                if self.time_col in chunk.columns:
                    # 1. 转换为datetime（移除engine参数，兼容低版本pandas）
                    chunk[self.time_col] = pd.to_datetime(
                        chunk[self.time_col],
                        format=input_format if input_format != "auto" else None,
                        errors='coerce'
                    )

                    # 2. 时间对齐（全局基准+相对时间差，保留原始跨度）
                    valid_mask = chunk[self.time_col].notna()
                    if valid_mask.any():
                        # 直接叠加全局时间差，保留原始时间跨度
                        chunk.loc[valid_mask, self.time_col] += global_time_diff

                    # 3. 格式转换（安全处理空值，避免NaT报错）
                    chunk[self.time_col] = chunk[self.time_col].apply(
                        lambda x: x.strftime(self.output_format) if pd.notna(x) else x
                    )

                # 筛选列并添加到结果（增量合并）
                selected_cols = [c for c in self.selected_cols if c in chunk.columns]
                chunk = chunk[selected_cols]

                # 关键修改：将时间列的列名改为“时间”
                if self.time_col in chunk.columns:
                    chunk.rename(columns={self.time_col: "时间"}, inplace=True)

                df_converted_all.append(chunk)

                # 释放临时内存
                del chunk
                # 每100块清理一次内存（避免碎片）
                if i % 100 == 0:
                    import gc
                    gc.collect()

            # 最终合并（使用高效的concat策略）
            self.progress.emit(90, "合并数据...")
            df_converted = pd.concat(df_converted_all, ignore_index=True)
            del df_converted_all
            gc.collect()

            # 分离展示数据
            df_display = df_converted.head(MAX_DISPLAY_ROWS) if len(df_converted) > MAX_DISPLAY_ROWS else df_converted

            self.progress.emit(100, "转换完成！")
            self.finished.emit(df_converted, df_display)

        except Exception as e:
            self.error.emit(f"转换失败：{str(e)}")

    def _detect_time_format(self):
        """快速检测时间格式（仅用前50个样本）"""
        if self.time_col not in self.df_original.columns:
            return "auto"

        time_series = self.df_original[self.time_col].dropna().head(50)
        if time_series.empty:
            return "auto"

        sample = str(time_series.iloc[0]).strip()
        format_map = {
            r"\d{4}/\d{1,2}/\d{1,2} \d{1,2}:\d{1,2}:\d{1,2}": "%Y/%m/%d %H:%M:%S",
            r"\d{4}-\d{1,2}-\d{1,2} \d{1,2}:\d{1,2}:\d{1,2}": "%Y-%m-%d %H:%M:%S",
            r"\d{4}/\d{1,2}/\d{1,2}": "%Y/%m/%d",
            r"\d{4}-\d{1,2}-\d{1,2}": "%Y-%m-%d",
            r"\d{14}": "%Y%m%d%H%M%S",
        }

        for pattern, fmt in format_map.items():
            if re.match(pattern, sample):
                return fmt
        return "auto"


# --------------------------
# 高性能表格模型（兼容所有PyQt5版本）
# --------------------------
class AcceleratedTableModel(QAbstractTableModel):
    def __init__(self, df):
        super().__init__()
        self.df = df
        self.columns = df.columns.tolist()
        # 将数据转换为二维列表（加速访问）
        self.data_cache = df.values.tolist()

    def rowCount(self, parent=QModelIndex()):
        return len(self.data_cache)

    def columnCount(self, parent=QModelIndex()):
        return len(self.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        if role == Qt.DisplayRole:
            # 直接从缓存获取，避免df.iloc的开销
            return str(self.data_cache[index.row()][index.column()])
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self.columns[section]
            else:
                return str(section + 1)
        return None


# --------------------------
# 主窗口类（完全解耦+兼容优化+日期修复）
# --------------------------
class Win_OilFuncTimeConv(QWidget):
    def __init__(self, node):
        super().__init__()
        self.ui_container = QWidget()
        self.ui = Ui_OilFuncTimeConv()
        self.ui.setupUi(self.ui_container)

        # --------------------------
        # 关键修复：提前为node初始化data属性
        # --------------------------
        self.node = node
        if not hasattr(self.node, 'data'):
            self.node.data = {'value': pd.DataFrame()}  # 初始化为带value的字典
        if not hasattr(self.node, 'window'):
            self.node.window = self

        # 窗口配置（兼容版）
        self.setWindowTitle("时间转换")
        self.resize(1000, 700)

        # 数据存储（分离全量/展示数据）
        self.df_original = pd.DataFrame()
        self.df_converted_all = pd.DataFrame()
        self.df_converted_display = pd.DataFrame()
        self.column_checkboxes = {}  # 保留变量避免报错，实际不使用

        # 线程管理（避免重复创建）
        self.load_thread = None
        self.convert_thread = None

        # 初始化UI
        self._init_ui()
        self._bind_events()

        # 预分配内存（减少动态分配开销）
        self.progress_bar.setValue(0)

    def _init_ui(self):
        """UI初始化（极简+高性能）"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # 进度条（极简样式）
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFormat("%p% - %s")
        main_layout.addWidget(self.progress_bar)

        # 加载UI容器
        main_layout.addWidget(self.ui_container)

        # 表格初始化（兼容版）
        self._init_table()

        # UI优化
        self._optimize_ui()

    def _init_table(self):
        """表格优化（兼容所有PyQt5版本，支持列宽调整）"""
        self.table_view = QTableView()

        # 核心优化：禁用所有不必要的功能（兼容版）
        self.table_view.setSortingEnabled(False)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setFocusPolicy(Qt.StrongFocus)

        # 行/列优化（支持列宽调整）
        self.table_view.verticalHeader().setDefaultSectionSize(24)
        self.table_view.verticalHeader().setVisible(True)
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

        # 关键修改：设置列宽调整策略
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        # 最后一列拉伸以填充剩余空间
        self.table_view.horizontalHeader().setStretchLastSection(True)

        # 虚拟滚动（关键：保留核心优化）
        self.table_view.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)
        self.table_view.setHorizontalScrollMode(QAbstractItemView.ScrollPerItem)

        # 启用水平滚动条
        self.table_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 添加到滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.table_view)
        scroll_area.setMinimumHeight(400)

        # 插入到UI布局：仅移除旧的滚动区域，不处理其他控件
        for i in range(self.ui.verticalLayout_data.count()):
            item = self.ui.verticalLayout_data.itemAt(i)
            if item:  # 先判断item是否存在
                widget = item.widget()
                if widget and isinstance(widget, QScrollArea):
                    self.ui.verticalLayout_data.removeWidget(widget)
                    widget.deleteLater()

        # 在布局中添加表格滚动区域
        self.ui.verticalLayout_data.addWidget(scroll_area)

    def _optimize_ui(self):
        """UI元素优化（减少绘制开销，仅保留秒级显示）"""
        # 按钮样式简化
        self.ui.btn_Load.setStyleSheet("QPushButton { padding: 5px; }")
        self.ui.btn_Transfer.setStyleSheet("QPushButton { padding: 5px; }")
        self.ui.btn_Load.setText("Load")
        self.ui.btn_Transfer.setText("Convert")
        self.btn_Transfer = QPushButton("Transfer")
        self.btn_Transfer.setStyleSheet("QPushButton { padding: 5px; }")
        self.ui.horizontalLayout_3.addWidget(self.btn_Transfer)

        # 输入框优化：仅保留秒级显示
        self.edit_target_time = QDateTimeEdit()
        self.edit_target_time.setDateTime(QDateTime.currentDateTime())
        self.edit_target_time.setDisplayFormat("yyyy/MM/dd HH:mm:ss")  # 仅秒级
        self.edit_target_time.setCalendarPopup(True)
        # 插入到垂直布局中
        self.ui.verticalLayout_2.insertWidget(0, QLabel("目标时间："))
        self.ui.verticalLayout_2.insertWidget(1, self.edit_target_time)

        # 隐藏不必要的元素
        if hasattr(self.ui, 'label_offset'):
            self.ui.label_offset.setVisible(False)
        if hasattr(self.ui, 'line_offset'):
            self.ui.line_offset.setVisible(False)

    def _bind_events(self):
        """事件绑定（避免重复绑定）"""
        self.ui.btn_Load.clicked.connect(self.on_load)
        self.ui.btn_Transfer.clicked.connect(self.on_convert)
        self.btn_Transfer.clicked.connect(self.on_transfer)

    def _update_table(self, df):
        """更新表格（原子操作，避免UI阻塞）"""
        if df.empty:
            self.table_view.setModel(None)
            return

        # 异步更新模型（避免主线程阻塞）
        QTimer.singleShot(0, lambda: self._do_update_table(df))

    def _do_update_table(self, df):
        """实际更新表格（在主线程中执行）"""
        model = AcceleratedTableModel(df)
        self.table_view.setModel(model)

        # 自动调整列宽以适应内容
        self.table_view.resizeColumnsToContents()

        # 设置最小列宽，避免列太窄
        for i in range(model.columnCount()):
            current_width = self.table_view.columnWidth(i)
            self.table_view.setColumnWidth(i, max(current_width, 120))

    def on_load(self):
        """加载数据（安全线程管理）"""
        # 停止现有线程
        if self.load_thread and self.load_thread.isRunning():
            self.load_thread.terminate()
            self.load_thread.wait()

        # 创建新线程
        self.load_thread = DataLoadThread(self.node)
        self.load_thread.progress.connect(self._update_progress)
        self.load_thread.finished.connect(self._on_load_finished)
        self.load_thread.error.connect(self._show_error)

        # 启动线程
        self.load_thread.start()

    def on_convert(self):
        """转换数据（安全线程管理+日期修复，仅秒级精度）"""
        if self.df_original.empty:
            self._show_error("请先加载数据！")
            return

        # 获取配置
        time_col = self.ui.combo_time_col.currentText() if self.ui.combo_time_col.count() > 0 else ""
        target_time = self.edit_target_time.dateTime().toPyDateTime()
        output_format = "%Y/%m/%d %H:%M:%S"  # 仅秒级格式
        # 关键修改：直接使用所有列，不再依赖复选框
        selected_cols = self.df_original.columns.tolist()

        if not selected_cols:
            self._show_error("无有效列数据！")
            return

        if not time_col:
            self._show_error("请选择时间列！")
            return

        # 停止现有线程
        if self.convert_thread and self.convert_thread.isRunning():
            self.convert_thread.stop()
            self.convert_thread.wait()

        # 创建新线程
        self.convert_thread = DataConvertThread(
            self.df_original, time_col, target_time, output_format, selected_cols
        )
        self.convert_thread.progress.connect(self._update_progress)
        self.convert_thread.finished.connect(self._on_convert_finished)
        self.convert_thread.error.connect(self._show_error)

        # 启动线程
        self.convert_thread.start()

    def on_transfer(self):
        """传递数据（全量数据，正确封装为字典）"""
        if self.df_converted_all.empty:
            self._show_error("请先执行转换操作！")
            return

        try:
            # 确保node有LoadData方法
            if hasattr(self.node, 'LoadData'):
                success = self.node.LoadData(self.df_converted_all)
                if success:
                    QMessageBox.information(self, "成功", "全量数据已传递！")
                else:
                    raise ValueError("数据传递失败")
            else:
                # 关键修复：正确封装为带value键的字典，保证serialize能获取
                self.node.data = {'value': self.df_converted_all}
                # 为node添加默认的serialize方法（如果没有）
                if not hasattr(self.node, 'serialize'):
                    def serialize():
                        return self.node.data
                    self.node.serialize = serialize
                QMessageBox.information(self, "成功", "全量数据已手动传递！")

        except Exception as e:
            self._show_error(f"传递失败：{str(e)}")

    def _update_progress(self, value, text):
        """更新进度（非阻塞）"""
        QTimer.singleShot(0, lambda: self.progress_bar.setValue(value))
        QTimer.singleShot(0, lambda: self.progress_bar.setFormat(f"{text} ({value}%)"))

    def _on_load_finished(self, df, columns):
        """加载完成处理：保留原有逻辑，移除复选框渲染"""
        self.df_original = df
        # 关键修改：删除列复选框渲染逻辑，直接填充时间列下拉框
        self.ui.combo_time_col.clear()
        for col in columns:
            self.ui.combo_time_col.addItem(col)
        # 更新表格展示原始数据
        self._update_table(df.head(MAX_DISPLAY_ROWS))

        # 检测时间格式
        if columns:
            time_col = columns[0]
            converter = DataConvertThread(df, time_col, datetime.now(), "", columns)
            fmt = converter._detect_time_format()
            self.ui.line_input_format.setText(f"检测格式：{fmt}")

        QMessageBox.information(self, "成功", f"加载完成：{len(df)} 行")

    def _on_convert_finished(self, df_all, df_display):
        """转换完成处理：保留原有逻辑"""
        self.df_converted_all = df_all
        self.df_converted_display = df_display
        self._update_table(df_display)

        QMessageBox.information(self, "成功", f"转换完成：处理{len(df_all)}行，展示{len(df_display)}行")
        self.progress_bar.setValue(0)

    def _render_columns(self, columns):
        """空方法：保留以避免调用报错，不再渲染复选框"""
        pass

    def _show_error(self, msg):
        """显示错误（非阻塞）"""
        QTimer.singleShot(0, lambda: QMessageBox.warning(self, "警告", msg))
        QTimer.singleShot(0, lambda: self.progress_bar.setValue(0))

    def closeEvent(self, event):
        """安全关闭（释放所有资源）"""
        # 停止线程
        if self.load_thread and self.load_thread.isRunning():
            self.load_thread.terminate()
            self.load_thread.wait()
        if self.convert_thread and self.convert_thread.isRunning():
            self.convert_thread.stop()
            self.convert_thread.wait()

        # 释放内存
        self.df_original = pd.DataFrame()
        self.df_converted_all = pd.DataFrame()
        self.df_converted_display = pd.DataFrame()

        event.accept()


# --------------------------
# 外部调用函数（关键：提前初始化node属性）
# --------------------------
def create_timeconv_window(node):
    # 双重保险：为node初始化必要属性
    if not hasattr(node, 'data'):
        node.data = {'value': pd.DataFrame()}
    if not hasattr(node, 'window'):
        node.window = None
    return Win_OilFuncTimeConv(node)


_orig_timeconv_on_convert_finished = Win_OilFuncTimeConv._on_convert_finished
_orig_timeconv_on_transfer = Win_OilFuncTimeConv.on_transfer


def _timeconv_on_convert_finished_v2(self, df_all, df_display):
    _orig_timeconv_on_convert_finished(self, df_all, df_display)
    if hasattr(self.node, "markValid"):
        self.node.markValid()
    if hasattr(self.node, "markDirty"):
        self.node.markDirty(False)
    if hasattr(self.node, "markInvalid"):
        self.node.markInvalid(False)


def _timeconv_on_transfer_v2(self):
    _orig_timeconv_on_transfer(self)
    if self.df_converted_all.empty:
        return
    if hasattr(self.node, "markValid"):
        self.node.markValid()
    if hasattr(self.node, "markDirty"):
        self.node.markDirty(False)
    if hasattr(self.node, "markInvalid"):
        self.node.markInvalid(False)
    if hasattr(self.node, "eval"):
        self.node.eval()
    if hasattr(self.node, "evalChildren"):
        self.node.evalChildren()


Win_OilFuncTimeConv._on_convert_finished = _timeconv_on_convert_finished_v2
Win_OilFuncTimeConv.on_transfer = _timeconv_on_transfer_v2
