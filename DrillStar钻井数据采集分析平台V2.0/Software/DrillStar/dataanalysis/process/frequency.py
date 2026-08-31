import functools

import matplotlib
import numpy as np
import pandas as pd
import pyqtgraph as pg
from matplotlib.figure import Figure
from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QLabel, QMessageBox, QPushButton, QWidget

from dataanalysis.buttonNode import ButtonNode
from dataanalysis.process.mpl_figure_dialog import MatplotlibFigureDialog
from dataanalysis.ui.Processfrequency_ui import Ui_Frequency


matplotlib.use("Qt5Agg")
matplotlib.rcParams["font.sans-serif"] = ["SimHei"]
matplotlib.rcParams["axes.unicode_minus"] = False
pg.setConfigOptions(antialias=True)


class FFTThread(QThread):
    fft_finished = pyqtSignal(np.ndarray, np.ndarray, str)
    fft_error = pyqtSignal(str)

    def __init__(self, data, fs, para):
        super().__init__()
        self.data = data
        self.fs = fs
        self.para = para

    def run(self):
        try:
            sample_count = len(self.data)
            if sample_count == 0:
                self.fft_error.emit("选中时间范围内没有可计算的数据")
                return

            time_step = 1 / self.fs
            fft_sig = np.fft.fft(self.data)
            freq = np.linspace(0.0, 1.0 / (2.0 * time_step), sample_count // 2, endpoint=True)
            amplitude_spec = np.abs(fft_sig[: sample_count // 2]) * 2.0 / sample_count
            self.fft_finished.emit(freq, amplitude_spec, self.para)
        except Exception as exc:
            self.fft_error.emit(f"FFT 计算失败：{exc}")


class Win_ProcessFrequency(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.ui = Ui_Frequency()
        self.ui.setupUi(self)
        self.setWindowTitle("DataAnalysis [Frequency]")
        self.setMinimumSize(800, 600)

        self.node = node
        self.df = pd.DataFrame()
        self.select_para = []
        self.linear_selection_dict = {}
        self.plot_layout_dict = {}
        self.button_dict = {}
        self.current_time_range = [None, None]
        self.fft_thread = None
        self.time_col = None
        self.time_array = None
        self.time_series = None
        self._fft_windows = []

        self.ui.lE_Sample.setText("1000")
        self.ui.btn_Transfer.setVisible(False)
        self.color_pool = [
            QColor(255, 0, 0),
            QColor(0, 255, 0),
            QColor(0, 0, 255),
            QColor(255, 255, 0),
            QColor(255, 0, 255),
            QColor(0, 255, 255),
        ]

        self.ui.btn_Load.clicked.connect(self.on_load)
        self.ui.btn_Show.clicked.connect(self.on_show)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout(child_layout)

    def on_load(self):
        try:
            input_node = self.node.getInput(0)
            if input_node is None:
                QMessageBox.warning(self, "警告", "上游节点无输入数据")
                return

            result = input_node.serialize()
            self.df = result.get("value", pd.DataFrame()).copy()
            if self.df.empty:
                QMessageBox.warning(self, "警告", "加载的数据为空")
                return

            self._auto_detect_time_column()
            self._init_param_ui()
            QMessageBox.information(
                self,
                "成功",
                f"加载数据成功：{len(self.df)} 行 x {len(self.df.columns)} 列",
            )
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"数据加载失败：{exc}")

    def _auto_detect_time_column(self):
        self.time_col = None
        self.time_series = None
        self.time_array = None

        for col in self.df.columns:
            try:
                candidate = pd.to_datetime(self.df[col], errors="raise")
                self.time_col = col
                self.time_series = candidate
                self.time_array = (candidate - candidate.iloc[0]).dt.total_seconds().to_numpy()
                QMessageBox.information(self, "提示", f"自动识别时间列：{self.time_col}")
                return
            except (ValueError, TypeError):
                continue

        QMessageBox.warning(self, "警告", "数据中未检测到可用时间列")

    def _init_param_ui(self):
        self._clear_layout(self.ui.verticalLayout_para)
        self._clear_layout(self.ui.verticalLayout_data)

        self.select_para.clear()
        self.button_dict.clear()
        self.linear_selection_dict.clear()
        self.plot_layout_dict.clear()

        for col in self.df.columns:
            if col == self.time_col or not pd.api.types.is_numeric_dtype(self.df[col]):
                continue

            self.select_para.append(col)
            row_layout = QHBoxLayout()

            label = QLabel(col)
            label.setAlignment(Qt.AlignCenter)
            label.setMinimumWidth(100)

            button = QPushButton("FFT")
            button.setMinimumWidth(80)
            button.clicked.connect(functools.partial(self.on_fft, col))

            row_layout.addWidget(label)
            row_layout.addWidget(button)
            self.ui.verticalLayout_para.addLayout(row_layout)
            self.button_dict[button] = col

        if not self.select_para:
            QMessageBox.warning(self, "警告", "数据中没有可用于频域分析的数值列")

    def on_show(self):
        if not self.select_para:
            QMessageBox.warning(self, "警告", "没有可显示的参数")
            return
        if self.time_array is None:
            QMessageBox.warning(self, "警告", "未检测到时间列")
            return

        self._clear_layout(self.ui.verticalLayout_data)
        self.linear_selection_dict.clear()
        self.plot_layout_dict.clear()

        for idx, para in enumerate(self.select_para):
            self._create_plot_widget(para, idx)

        default_end_idx = max(1, min(len(self.time_array) - 1, int(len(self.df) * 0.1)))
        self.current_time_range = [self.time_array[0], self.time_array[default_end_idx]]
        self._sync_linear_regions(self.current_time_range)
        self._update_time_range_label()

    def _create_plot_widget(self, para, idx):
        x_axis = pg.AxisItem(orientation="bottom")
        x_axis.setLabel("时间 (s)")
        y_axis = pg.AxisItem(orientation="left")
        y_axis.setLabel(para)

        plot_widget = pg.PlotWidget(axisItems={"bottom": x_axis, "left": y_axis})
        plot_widget.setBackground("w")
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        plot_widget.plot(self.time_array, self.df[para].to_numpy(), pen=self.color_pool[idx % len(self.color_pool)])

        region = pg.LinearRegionItem(
            [self.time_array[0], self.time_array[min(1, len(self.time_array) - 1)]],
            pen=QColor(0, 0, 0),
            brush=QColor(0, 0, 255, 30),
        )
        region.sigRegionChanged.connect(functools.partial(self.on_region_changed, para))
        plot_widget.addItem(region)

        self.plot_layout_dict[para] = plot_widget
        self.linear_selection_dict[para] = region
        self.ui.verticalLayout_data.addWidget(plot_widget)

    def on_region_changed(self, para):
        try:
            min_time, max_time = self.linear_selection_dict[para].getRegion()
            self.current_time_range = [min_time, max_time]
            self._sync_linear_regions(self.current_time_range, source_para=para)
            self._update_time_range_label()
        except Exception:
            pass

    def _sync_linear_regions(self, time_range, source_para=None):
        for para, region in self.linear_selection_dict.items():
            if para == source_para:
                continue
            try:
                region.sigRegionChanged.disconnect()
            except TypeError:
                pass
            region.setRegion(time_range)
            region.sigRegionChanged.connect(functools.partial(self.on_region_changed, para))

    def _update_time_range_label(self):
        if self.time_series is None or self.current_time_range[0] is None:
            self.ui.label_time_range.setText("当前选中时间：无")
            return

        start_idx = int(np.argmin(np.abs(self.time_array - self.current_time_range[0])))
        end_idx = int(np.argmin(np.abs(self.time_array - self.current_time_range[1])))
        start_time = self.time_series.iloc[start_idx]
        end_time = self.time_series.iloc[end_idx]

        start_str = start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        end_str = end_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.ui.label_time_range.setText(f"当前选中时间：\n{start_str}\n至\n{end_str}")

    def on_fft(self, para):
        try:
            fs_text = self.ui.lE_Sample.text().strip()
            fs = int(fs_text) if fs_text.isdigit() and int(fs_text) > 0 else 1000

            if self.current_time_range[0] is None:
                QMessageBox.warning(self, "警告", "请先在时域图中选择时间范围")
                return

            mask = (self.time_array >= self.current_time_range[0]) & (self.time_array <= self.current_time_range[1])
            data = self.df.loc[mask, para].to_numpy()
            if len(data) == 0:
                QMessageBox.warning(self, "警告", "选中时间范围内没有数据")
                return

            if self.fft_thread and self.fft_thread.isRunning():
                self.fft_thread.terminate()

            self.fft_thread = FFTThread(data, fs, para)
            self.fft_thread.fft_finished.connect(self.on_fft_finished)
            self.fft_thread.fft_error.connect(self.on_fft_error)
            self.fft_thread.start()
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"FFT 准备失败：{exc}")

    def on_fft_finished(self, freq, amplitude_spec, para):
        fig = Figure(figsize=(10, 6))
        ax = fig.add_subplot(111)
        ax.plot(freq, amplitude_spec, color="blue", linewidth=2)
        ax.set_xlabel("频率 (Hz)")
        ax.set_ylabel(f"幅值 ({para})")
        ax.set_title(f"{para} - FFT 频谱分析")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        dialog = MatplotlibFigureDialog(fig, f"{para} - FFT 频谱分析", self)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._fft_windows.append(dialog)

    def on_fft_error(self, error_msg):
        QMessageBox.critical(self, "错误", error_msg)

    def closeEvent(self, event):
        if self.fft_thread and self.fft_thread.isRunning():
            self.fft_thread.terminate()
        event.accept()


def _frequency_on_load_fixed(self):
    try:
        input_node = self.node.getInput(0)
        if input_node is None:
            if hasattr(self.node, "markDirty"):
                self.node.markDirty()
            if hasattr(self.node, "markInvalid"):
                self.node.markInvalid()
            QMessageBox.warning(self, "提示", "上游节点无输入数据。")
            return

        result = input_node.serialize()
        self.df = result.get("value", pd.DataFrame()).copy()
        if self.df.empty:
            if hasattr(self.node, "markInvalid"):
                self.node.markInvalid()
            QMessageBox.warning(self, "提示", "加载的数据为空。")
            return

        if hasattr(self.node, "eval"):
            self.node.eval()
        else:
            if hasattr(self.node, "markDirty"):
                self.node.markDirty(False)
            if hasattr(self.node, "markInvalid"):
                self.node.markInvalid(False)

        self._auto_detect_time_column()
        self._init_param_ui()
        QMessageBox.information(
            self,
            "成功",
            f"加载数据成功：{len(self.df)} 行 x {len(self.df.columns)} 列",
        )
    except Exception as exc:
        if hasattr(self.node, "markInvalid"):
            self.node.markInvalid()
        QMessageBox.critical(self, "错误", f"数据加载失败：{exc}")


Win_ProcessFrequency.on_load = _frequency_on_load_fixed


if __name__ == "__main__":
    import sys

    class MockButtonNode:
        def __init__(self):
            self.inputs = [None]
            time_idx = pd.date_range(start="2025-01-01 00:00:00", periods=1000, freq="1ms")
            self.data = {
                "value": pd.DataFrame(
                    {
                        "time": time_idx,
                        "col1": np.random.randn(1000),
                        "col2": np.sin(np.linspace(0, 100, 1000)),
                    }
                )
            }

        def getInput(self, idx):
            return self

        def serialize(self):
            return self.data

        def markDirty(self):
            pass

        def markInvalid(self):
            pass

        def eval(self):
            pass

    app = QApplication(sys.argv)
    node = MockButtonNode()
    win = Win_ProcessFrequency(node)
    win.show()
    sys.exit(app.exec_())
