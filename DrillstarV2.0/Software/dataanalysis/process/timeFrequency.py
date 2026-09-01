import functools

import matplotlib
import numpy as np
import pandas as pd
import pyqtgraph as pg
import scipy.signal as signal
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QPen
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QLabel, QMessageBox, QPushButton, QWidget

from dataanalysis.buttonNode import ButtonNode
from dataanalysis.process.mpl_figure_dialog import MatplotlibFigureDialog
from dataanalysis.ui.ProcessTimeFrequency_ui import Ui_TimeFrequency


matplotlib.use("Qt5Agg")
matplotlib.rcParams["font.sans-serif"] = ["SimHei"]
matplotlib.rcParams["axes.unicode_minus"] = False
pg.setConfigOptions(antialias=True)


class Win_ProcessTimeFrequency(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.ui = Ui_TimeFrequency()
        self.ui.setupUi(self)
        self.setWindowTitle("DataAnalysis [TimeFrequency]")
        self.setMinimumSize(800, 600)

        self.node = node
        self.df = pd.DataFrame()
        self.select_para = []
        self.linear_selection_dict = {}
        self.layout_dict = {}
        self.current_time_range = [None, None]
        self.time_col = None
        self.time_series = None
        self.time_array = None
        self._stft_windows = []

        self.ui.lE_Sample.setText("1000")
        self.ui.btn_Transfer.setVisible(False)

        self.region_pen = QPen(QColor(0, 0, 0), 2)
        self.region_brush = QColor(0, 0, 255, 30)
        self.color_pool = [
            QColor(255, 0, 0),
            QColor(0, 255, 0),
            QColor(0, 0, 255),
            QColor(255, 255, 0),
            QColor(255, 0, 255),
            QColor(0, 255, 255),
        ]

        self.ui.btn_Load.clicked.connect(self.on_Load)
        self.ui.btn_Show.clicked.connect(self.on_Show)

    def _clear_layout(self, layout):
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout(child_layout)

    def on_Load(self):
        if self.node.getInput(0) is None:
            self.node.markDirty()
            self.node.markInvalid()
            QMessageBox.warning(self, "警告", "上游节点无输入数据")
            return

        try:
            result = self.node.getInput(0).serialize()
            self.df = result.get("value", pd.DataFrame()).copy()
            if self.df.empty:
                QMessageBox.warning(self, "警告", "加载的数据为空")
                return

            self.node.eval()
            self._auto_detect_time_column()
            self.on_initUI()
            QMessageBox.information(self, "成功", f"加载数据成功：{len(self.df)} 行 x {len(self.df.columns)} 列")
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

        fs_text = self.ui.lE_Sample.text().strip()
        fs = int(fs_text) if fs_text.isdigit() and int(fs_text) > 0 else 1000
        self.time_array = np.arange(len(self.df)) / fs
        QMessageBox.warning(self, "提示", "未检测到时间列，已使用样本索引换算为时间轴")

    def on_initUI(self):
        self.select_para.clear()
        self._clear_layout(self.ui.verticalLayout_data)
        self._clear_layout(self.ui.verticalLayout_para)
        self.linear_selection_dict.clear()
        self.layout_dict.clear()

        for item in self.df.columns.tolist():
            if item == self.time_col or not pd.api.types.is_numeric_dtype(self.df[item]):
                continue

            row_layout = QHBoxLayout()
            label = QLabel(item)
            label.setAlignment(Qt.AlignCenter)
            label.setMinimumWidth(100)

            button = QPushButton("STFT")
            button.setMinimumWidth(80)
            button.clicked.connect(functools.partial(self.on_STFT, item))

            row_layout.addWidget(label)
            row_layout.addWidget(button)
            self.ui.verticalLayout_para.addLayout(row_layout)
            self.select_para.append(item)

    def on_Show(self):
        if not self.select_para:
            QMessageBox.warning(self, "警告", "没有可用于绘图的参数")
            return
        if self.time_array is None:
            QMessageBox.warning(self, "警告", "时间轴未初始化")
            return

        self._clear_layout(self.ui.verticalLayout_data)
        self.linear_selection_dict.clear()
        self.layout_dict.clear()

        default_end_idx = max(1, min(len(self.time_array) - 1, int(len(self.df) * 0.1)))
        self.current_time_range = [self.time_array[0], self.time_array[default_end_idx]]

        for idx, item in enumerate(self.select_para):
            self.init_Layout(item, idx)
            self.draw_Layout(item)

        self._update_time_range_label()

    def init_Layout(self, item, idx):
        x_axis = pg.AxisItem(orientation="bottom", pen="k")
        x_axis.setLabel("时间 (s)" if self.time_col else "样本时间 (s)")
        x_axis.setTickFont(QFont("Arial", 10))

        y_axis = pg.AxisItem(orientation="left", pen="k")
        y_axis.setLabel(item)
        y_axis.setTickFont(QFont("Arial", 10))

        widget = pg.PlotWidget(axisItems={"bottom": x_axis, "left": y_axis})
        widget.setBackground("w")
        widget.showGrid(x=True, y=True, alpha=0.3)
        self.layout_dict[item] = widget
        self.ui.verticalLayout_data.addWidget(widget)

    def draw_Layout(self, item):
        widget = self.layout_dict[item]
        pen_color = self.color_pool[self.select_para.index(item) % len(self.color_pool)]
        widget.plot(self.time_array, self.df[item].to_numpy(), pen=pen_color)

        region = pg.LinearRegionItem(
            self.current_time_range,
            pen=self.region_pen,
            brush=self.region_brush,
            movable=True,
        )
        region.setZValue(10)
        region.sigRegionChanged.connect(functools.partial(self._on_region_changed, item))
        widget.addItem(region)
        self.linear_selection_dict[item] = region

    def _on_region_changed(self, current_item):
        min_time, max_time = self.linear_selection_dict[current_item].getRegion()
        self.current_time_range = [min_time, max_time]

        for item, region in self.linear_selection_dict.items():
            if item == current_item:
                continue
            try:
                region.sigRegionChanged.disconnect()
            except TypeError:
                pass
            region.setRegion(self.current_time_range)
            region.sigRegionChanged.connect(functools.partial(self._on_region_changed, item))

        self._update_time_range_label()

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

    def on_STFT(self, para):
        try:
            if self.current_time_range[0] is None:
                QMessageBox.warning(self, "警告", "请先在时域图中选择时间范围")
                return

            fs_text = self.ui.lE_Sample.text().strip()
            fs = int(fs_text) if fs_text.isdigit() and int(fs_text) > 0 else 1000

            mask = (self.time_array >= self.current_time_range[0]) & (self.time_array <= self.current_time_range[1])
            sig = self.df.loc[mask, para].to_numpy()
            if len(sig) == 0:
                QMessageBox.warning(self, "警告", "选中时间范围内没有数据")
                return

            nperseg = min(256, len(sig))
            noverlap = nperseg // 2
            f, t, zxx = signal.stft(
                sig,
                fs=fs,
                window="hann",
                nperseg=nperseg,
                noverlap=noverlap,
                detrend=False,
                return_onesided=True,
            )

            zxx_db = 20 * np.log10(np.abs(zxx) + 1e-8)
            self._plot_2d_stft(para, t, f, zxx_db)
            self._plot_3d_stft(para, t, f, zxx_db)
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"STFT 计算失败：{exc}")

    def _plot_2d_stft(self, para, t, f, zxx_db):
        fig = Figure(figsize=(10, 6))
        ax = fig.add_subplot(111)
        image = ax.pcolormesh(
            t,
            f,
            zxx_db,
            shading="gouraud",
            cmap="inferno",
            vmin=np.min(zxx_db),
            vmax=np.max(zxx_db),
        )
        colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
        colorbar.set_label("幅值 (dB)")
        ax.set_title(f"{para} - STFT 2D 时频图")
        ax.set_xlabel("时间 (s)")
        ax.set_ylabel("频率 (Hz)")
        ax.grid(alpha=0.3, linestyle="--")
        fig.tight_layout()

        dialog = MatplotlibFigureDialog(fig, f"{para} - STFT 2D 时频图", self)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._stft_windows.append(dialog)

    def _plot_3d_stft(self, para, t, f, zxx_db):
        fig = Figure(figsize=(10, 6))
        ax = fig.add_subplot(111, projection="3d")
        mesh_t, mesh_f = np.meshgrid(t, f)
        surface = ax.plot_surface(
            mesh_t,
            mesh_f,
            zxx_db,
            cmap="plasma",
            linewidth=0,
            antialiased=True,
            shade=True,
        )
        colorbar = fig.colorbar(surface, ax=ax, fraction=0.046, pad=0.04)
        colorbar.set_label("幅值 (dB)")
        ax.set_title(f"{para} - STFT 3D 时频图")
        ax.set_xlabel("时间 (s)")
        ax.set_ylabel("频率 (Hz)")
        ax.set_zlabel("幅值 (dB)")
        ax.view_init(elev=30, azim=45)
        fig.tight_layout()

        dialog = MatplotlibFigureDialog(fig, f"{para} - STFT 3D 时频图", self)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._stft_windows.append(dialog)


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
    win = Win_ProcessTimeFrequency(node)
    win.show()
    sys.exit(app.exec_())
