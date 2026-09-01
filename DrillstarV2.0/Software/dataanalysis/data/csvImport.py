import os
import logging
import pandas as pd
import numpy as np
from typing import Optional
from PyQt5.QtWidgets import (
    QWidget, QMessageBox, QFileDialog, QAbstractItemView, QHeaderView
)
from PyQt5.QtCore import (
    Qt, QAbstractTableModel, pyqtSignal, QThread, pyqtSlot
)
from dataanalysis.ui.csvImport_ui import Ui_CSVImport
from dataanalysis.buttonNode import ButtonNode

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# 常量定义
WINDOW_TITLE = "DataAnalysis [CSV Import]"
FILE_FILTER = "CSV Files (*.csv);;All Files (*.*)"
DEFAULT_FILE_PATH = os.path.expanduser("~")  # 使用用户主目录作为默认路径
PROGRESS_MAX = 100
TIME_COLUMN_KEYWORDS = ("时间", "日期", "time", "date", "datetime", "timestamp", "ts")
INDEX_COLUMN_KEYWORDS = ("index", "id", "序号", "编号", "行号", "unnamed")


class DataLoaderThread(QThread):
    """后台数据加载线程，避免UI冻结"""
    progress_update = pyqtSignal(int)
    data_loaded = pyqtSignal(pd.DataFrame)
    error_occurred = pyqtSignal(str)

    def __init__(self, file_path: str, encoding: str = "utf-8"):
        super().__init__()
        self.file_path = file_path
        self.encoding = encoding
        self._is_running = True

    def stop(self):
        """优雅停止线程"""
        self._is_running = False

    def _count_lines_fast(self):
        """快速统计文件行数（优化后的方法）"""
        try:
            with open(self.file_path, 'r', encoding=self.encoding, buffering=1024 * 1024) as f:
                # 读取第一行（表头），然后统计剩余行数
                header = f.readline()
                if not header:
                    return 0  # 空文件
                # 用缓冲区批量读取，统计换行符数量
                line_count = 0
                buffer = f.read(1024 * 1024)
                while buffer and self._is_running:
                    line_count += buffer.count('\n')
                    buffer = f.read(1024 * 1024)
                return line_count
        except Exception as e:
            logger.error(f"统计行数失败：{e}")
            return -1  # 返回-1表示无法统计，后续用分块数估算

    def _is_continuous_increment(self, series: pd.Series) -> bool:
        """
        判断一列是否为连续自增整数列（自增列特征）
        :param series: 待判断的列
        :return: True表示是连续自增整数列，False反之
        """
        # 过滤空值
        series = series.dropna()
        if len(series) == 0:
            return False

        # 检查是否为整数类型
        if not pd.api.types.is_integer_dtype(series.dtype):
            # 浮点数但值为整数的情况（如1.0,2.0）
            if not pd.api.types.is_float_dtype(series.dtype):
                return False
            if not np.all(series == series.astype(int)):
                return False

        # 转换为整数数组
        arr = series.astype(int).values
        # 检查是否从1开始连续自增（或从0开始）
        return np.array_equal(arr, np.arange(arr[0], arr[0] + len(arr)))

    def _is_time_like_column(self, column_name, series: pd.Series) -> bool:
        name = str(column_name).strip().lower()
        if any(keyword in name for keyword in TIME_COLUMN_KEYWORDS):
            return True

        sample = series.dropna()
        if sample.empty:
            return False

        if pd.api.types.is_datetime64_any_dtype(sample.dtype):
            return True

        sample_text = sample.head(50).astype(str).str.strip()
        datetime_like = sample_text.str.contains(r"[-/:T ]", regex=True)
        if datetime_like.sum() < max(3, len(sample_text) // 2):
            return False

        converted = pd.to_datetime(sample_text[datetime_like], errors="coerce")
        return converted.notna().sum() >= max(3, len(converted) // 2)

    def _is_likely_index_column(self, column_name) -> bool:
        name = str(column_name).strip().lower()
        if name.isdigit():
            return True
        return any(keyword in name for keyword in INDEX_COLUMN_KEYWORDS)

    def _remove_auto_increment_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        仅删除自增列（核心逻辑）
        1. 无表头场景：列名为数字索引，删除第一列
        2. 有表头场景：判断列是否为连续自增整数，删除第一个匹配的列
        """
        deleted = False

        first_col = df.columns[0]

        # 场景1：无表头（列名为数字索引，如0、1、2...）
        if first_col == 0 or str(first_col).isdigit():
            first_col = df.columns[0]
            df = df.drop(columns=[first_col])
            logger.info(f"自动删除无表头自增列：第一列（索引{first_col}）")
            deleted = True

        # 场景2：有表头时，仅在第一列明显像索引列时才删除，避免误删时间列或正常测量列
        else:
            if (
                self._is_likely_index_column(first_col)
                and not self._is_time_like_column(first_col, df[first_col])
                and self._is_continuous_increment(df[first_col])
            ):
                df = df.drop(columns=[first_col])
                logger.info(f"自动删除有表头自增列：{first_col}")
                deleted = True

        if not deleted:
            logger.info("未检测到自增列，无需删除")

        return df

    def run(self):
        try:
            self.progress_update.emit(5)  # 初始化进度

            # 快速统计行数
            total_rows = self._count_lines_fast()
            self.progress_update.emit(10)

            chunk_size = 10000
            chunks = []
            processed_rows = 0

            # 读取CSV分块
            self.progress_update.emit(15)
            for chunk in pd.read_csv(
                    self.file_path,
                    encoding=self.encoding,
                    chunksize=chunk_size
            ):
                if not self._is_running:
                    return  # 优雅停止

                # 提前删除chunk中的自增列（减少内存占用）
                chunk = self._remove_auto_increment_column(chunk)
                chunks.append(chunk)
                processed_rows += len(chunk)

                # 计算进度：根据实际行数或分块数估算
                if total_rows > 0:
                    progress = 15 + int(75 * processed_rows / total_rows)
                else:
                    # 无法统计行数时，按分块数估算（假设最多100个分块）
                    progress = 15 + min(int(75 * processed_rows / (chunk_size * 100)), 75)

                self.progress_update.emit(min(progress, 90))  # 限制最大进度为90%

            if not self._is_running:
                return

            # 合并分块
            df = pd.concat(chunks, ignore_index=True)
            # 最终检查并删除自增列（确保无遗漏）
            df = self._remove_auto_increment_column(df)

            self.progress_update.emit(100)
            self.data_loaded.emit(df)

        except pd.errors.EmptyDataError:
            self.error_occurred.emit("所选CSV文件为空")
        except UnicodeDecodeError:
            # 尝试常见编码，同时更新进度
            self.progress_update.emit(10)
            try:
                self.load_with_encoding("gbk")
            except Exception as e:
                self.error_occurred.emit(f"文件编码错误：{str(e)}")
        except Exception as e:
            self.error_occurred.emit(f"读取文件失败：{str(e)}")

    def load_with_encoding(self, encoding: str):
        """使用指定编码重新加载"""
        chunk_size = 10000
        chunks = []
        for chunk in pd.read_csv(self.file_path, encoding=encoding, chunksize=chunk_size):
            if not self._is_running:
                return
            # 删除chunk中的自增列
            chunk = self._remove_auto_increment_column(chunk)
            chunks.append(chunk)
        df = pd.concat(chunks, ignore_index=True)
        # 最终检查并删除自增列
        df = self._remove_auto_increment_column(df)

        self.progress_update.emit(100)
        self.data_loaded.emit(df)


class PandasModel(QAbstractTableModel):
    """优化的Pandas DataFrame模型，支持高效渲染和类型格式化"""

    def __init__(self, data: pd.DataFrame):
        super().__init__()
        self._data = data
        self._columns = data.columns.tolist()
        # 缓存数据类型，优化显示
        self._dtypes = data.dtypes

    def rowCount(self, parent=None) -> int:
        return len(self._data)

    def columnCount(self, parent=None) -> int:
        return len(self._columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        value = self._data.iloc[row, col]

        if role == Qt.ItemDataRole.DisplayRole:
            # 根据数据类型格式化显示
            if pd.api.types.is_numeric_dtype(self._dtypes[col]):
                if isinstance(value, float):
                    return f"{value:.4f}"  # 浮点数保留4位小数
                return str(value)
            elif pd.api.types.is_datetime64_any_dtype(self._dtypes[col]):
                return value.strftime("%Y-%m-%d %H:%M:%S")
            else:
                return str(value) if pd.notna(value) else ""

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            return self._columns[section]
        else:
            return str(section + 1)  # 行号从1开始

    def flags(self, index):
        """标记模型为不可编辑，符合PyQt规范"""
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

    def update_data(self, new_data: pd.DataFrame):
        """更新模型数据"""
        self.beginResetModel()
        self._data = new_data
        self._columns = new_data.columns.tolist()
        self._dtypes = new_data.dtypes
        self.endResetModel()


class Win_CSVImport(QWidget):
    """CSV导入窗口，优化后的实现"""

    def __init__(self, node: ButtonNode):
        super().__init__()
        self.ui = Ui_CSVImport()
        self.ui.setupUi(self)
        self._init_ui()
        self._init_variables(node)
        self._bind_signals()

        logger.info(f"CSV导入窗口初始化，关联节点：{node}")

    def _init_ui(self):
        """初始化UI组件"""
        self.setWindowTitle(WINDOW_TITLE)
        self.ui.btn_OpenFile.setText("Load")
        self.ui.btn_Transfer.setText("Transfer")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)  # 模态窗口

        # 表格配置
        self.ui.tV_DataView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ui.tV_DataView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ui.tV_DataView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.ui.tV_DataView.setSortingEnabled(True)  # 启用排序

        # 进度条配置
        self.ui.progressBar.setRange(0, PROGRESS_MAX)
        self.ui.progressBar.setValue(0)

        # 禁用初始按钮
        self.ui.btn_delete.setEnabled(False)
        self.ui.btn_Transfer.setEnabled(False)

    def _init_variables(self, node: ButtonNode):
        """初始化变量"""
        self.node = node
        self.df: Optional[pd.DataFrame] = None
        self.loader_thread: Optional[DataLoaderThread] = None
        self.model: Optional[PandasModel] = None

    def _bind_signals(self):
        """绑定信号与槽"""
        self.ui.btn_OpenFile.clicked.connect(self.on_choose_file)
        self.ui.btn_delete.clicked.connect(self.on_delete_column)
        self.ui.btn_Transfer.clicked.connect(self.on_load_data)

    @pyqtSlot()
    def on_choose_file(self):
        """选择CSV文件"""
        # 重置节点状态
        self.node.markInvalid()
        self.node.markDescendantsInvalid()

        # 打开文件对话框
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "选择CSV文件",
            DEFAULT_FILE_PATH,
            FILE_FILTER
        )

        if not filepath:
            logger.info("用户取消文件选择")
            return

        # 重置UI
        self.ui.cB_FilePath.clear()
        self.ui.cB_count.clear()
        self.ui.progressBar.setValue(0)
        self.ui.btn_delete.setEnabled(False)
        self.ui.btn_Transfer.setEnabled(False)

        # 添加文件路径到下拉框
        self.ui.cB_FilePath.addItem(filepath)

        # 启动后台线程加载数据
        self.loader_thread = DataLoaderThread(filepath)
        self.loader_thread.progress_update.connect(self.ui.progressBar.setValue)
        self.loader_thread.data_loaded.connect(self.on_data_loaded)
        self.loader_thread.error_occurred.connect(self.on_load_error)
        self.loader_thread.start()

    @pyqtSlot(pd.DataFrame)
    def on_data_loaded(self, df: pd.DataFrame):
        """数据加载完成后的处理"""
        self.df = df
        self.model = PandasModel(df)
        self.ui.tV_DataView.setModel(self.model)

        # 更新列选择下拉框
        self.ui.cB_count.clear()
        for i in range(self.model.columnCount()):
            self.ui.cB_count.addItem(str(i + 1))

        # 启用按钮
        self.ui.btn_delete.setEnabled(True if self.model.columnCount() > 0 else False)
        self.ui.btn_Transfer.setEnabled(True if self.model.columnCount() > 0 else False)

        logger.info(f"成功加载CSV文件，数据形状：{df.shape}（已自动检测并删除自增列）")
        QMessageBox.information(self, "成功", f"已加载 {len(df)} 行数据（已自动检测并删除自增列）")

    @pyqtSlot(str)
    def on_load_error(self, error_msg: str):
        """加载数据错误处理"""
        logger.error(f"数据加载错误：{error_msg}")
        QMessageBox.critical(self, "错误", error_msg)
        self.ui.progressBar.setValue(0)

    @pyqtSlot()
    def on_delete_column(self):
        """删除选中列"""
        if self.df is None or self.model is None:
            return

        try:
            # 获取选中列索引
            col_index = int(self.ui.cB_count.currentText()) - 1
            if col_index < 0 or col_index >= len(self.df.columns):
                raise IndexError("列索引超出范围")

            # 删除列
            self.df = self.df.drop(self.df.columns[col_index], axis=1)
            self.model.update_data(self.df)

            # 更新下拉框
            self.ui.cB_count.clear()
            for i in range(self.model.columnCount()):
                self.ui.cB_count.addItem(str(i + 1))

            # 如果没有列了，禁用删除按钮
            if self.model.columnCount() == 0:
                self.ui.btn_delete.setEnabled(False)
                self.ui.btn_Transfer.setEnabled(False)

            logger.info(f"删除列 {col_index + 1}，剩余列数：{len(self.df.columns)}")

        except IndexError as e:
            logger.error(f"列删除失败：{e}")
            QMessageBox.warning(self, "警告", "无效的列索引")
        except Exception as e:
            logger.error(f"列删除异常：{e}")
            QMessageBox.critical(self, "错误", f"删除列失败：{str(e)}")

    @pyqtSlot()
    def on_load_data(self):
        """将数据加载到节点"""
        if self.df is None:
            QMessageBox.warning(self, "警告", "请先加载数据")
            return

        try:
            # 加载数据到节点
            if self.node.LoadData(self.df):
                self.node.markValid()
                self.node.eval()
                self.node.evalChildren()
                logger.info("数据成功加载到节点")
                QMessageBox.information(self, "成功", "数据已成功加载到节点")
            else:
                raise RuntimeError("节点数据加载方法返回False")

        except Exception as e:
            logger.error(f"节点数据加载失败：{e}")
            QMessageBox.critical(self, "错误", f"加载数据到节点失败：{str(e)}")

    def closeEvent(self, event):
        """关闭窗口时清理线程"""
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.terminate()
            self.loader_thread.wait()
        event.accept()
