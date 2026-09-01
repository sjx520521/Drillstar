import random

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QWidget

from dataanalysis.buttonNode import ButtonNode
from dataanalysis.ui.DisplayLinePlot_ui import Ui_LinePlot


pg.setConfigOptions(antialias=True, useOpenGL=False, enableExperimental=False)


class Win_DisplayLinePlot(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.ui = Ui_LinePlot()
        self.ui.setupUi(self)
        self.setWindowTitle("数据展示 [折线图]")

        self.node = node
        self.df = pd.DataFrame()
        self.select_para = []
        self.button_dict = {}
        self.layout_dict = {}

        self.draw_2to1_widget = None
        self.draw_3to1_widget = None
        self.draw_cnt = 0
        self.max_points = 12000
        self.legend = None

        self.ui.btn_Load.clicked.connect(self.on_Load)
        self.ui.btn_Clear.clicked.connect(self.on_Clear)
        self.ui.cB_type.setCurrentIndex(0)

    def clear_layout(self, layout):
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                self.clear_layout(item.layout())

    def _sample_data(self, x_data, y_data):
        if len(x_data) > self.max_points:
            step = max(1, len(x_data) // self.max_points)
            return x_data[::step], y_data[::step]
        return x_data, y_data

    def _build_plot_widget(self, y_label):
        x_axis = pg.AxisItem(orientation="bottom", pen="k", textPen="k")
        x_axis.setTickFont(QFont("Arial", 10))
        y_axis = pg.AxisItem("left", pen="k", textPen="k")
        y_axis.setTickFont(QFont("Arial", 10))
        y_axis.setLabel(y_label)

        plot_widget = pg.PlotWidget(axisItems={"bottom": x_axis, "left": y_axis})
        plot_widget.setBackground("w")
        plot_widget.showGrid(x=True, y=True, alpha=0.35)
        plot_widget.setClipToView(True)
        plot_widget.setDownsampling(mode="peak")
        plot_widget._drillstar_series = []
        plot_widget._drillstar_marker = pg.ScatterPlotItem(size=10, brush=pg.mkBrush(255, 170, 0), pen=pg.mkPen("k", width=1))
        plot_widget._drillstar_label = pg.TextItem(anchor=(0, 1), color=(0, 0, 0))
        plot_widget.addItem(plot_widget._drillstar_marker)
        plot_widget.addItem(plot_widget._drillstar_label)
        plot_widget._drillstar_marker.hide()
        plot_widget._drillstar_label.hide()
        plot_widget.scene().sigMouseClicked.connect(
            lambda event, widget=plot_widget: self._on_plot_clicked(widget, event)
        )
        return plot_widget

    def _plot_series(self, plot_widget, series, color, name=None):
        x_data, y_data = self._sample_data(series.index.to_numpy(), series.to_numpy())
        width = 1 if len(x_data) > 8000 else 1.2
        curve = plot_widget.plot(
            x_data,
            y_data,
            pen=pg.mkPen(color=color, width=width, cosmetic=True),
            name=name,
        )
        plot_widget._drillstar_series.append(
            {
                "name": name or "",
                "x": np.asarray(x_data, dtype=float),
                "y": np.asarray(y_data, dtype=float),
            }
        )
        return curve

    def _on_plot_clicked(self, plot_widget, event):
        if not plot_widget._drillstar_series:
            return

        scene_pos = event.scenePos()
        if not plot_widget.sceneBoundingRect().contains(scene_pos):
            return

        mouse_point = plot_widget.plotItem.vb.mapSceneToView(scene_pos)
        x_clicked = float(mouse_point.x())
        y_clicked = float(mouse_point.y())

        nearest = None
        best_score = None

        for series in plot_widget._drillstar_series:
            x_data = series["x"]
            y_data = series["y"]
            if x_data.size == 0:
                continue

            x_range = max(float(np.nanmax(x_data) - np.nanmin(x_data)), 1.0)
            y_range = max(float(np.nanmax(y_data) - np.nanmin(y_data)), 1.0)

            dx = (x_data - x_clicked) / x_range
            dy = (y_data - y_clicked) / y_range
            score = dx * dx + dy * dy
            idx = int(np.nanargmin(score))
            candidate_score = float(score[idx])

            if best_score is None or candidate_score < best_score:
                best_score = candidate_score
                nearest = {
                    "name": series["name"],
                    "x": float(x_data[idx]),
                    "y": float(y_data[idx]),
                }

        if nearest is None:
            return

        label_prefix = f"{nearest['name']}\n" if nearest["name"] else ""
        label_text = f"{label_prefix}X: {nearest['x']:.6g}\nY: {nearest['y']:.6g}"
        plot_widget._drillstar_marker.setData([nearest["x"]], [nearest["y"]])
        plot_widget._drillstar_label.setText(label_text)
        plot_widget._drillstar_label.setPos(nearest["x"], nearest["y"])
        plot_widget._drillstar_marker.show()
        plot_widget._drillstar_label.show()

    def on_Load(self):
        if self.node.getInput(0) is None:
            self.node.markDirty()
            self.node.markInvalid()
            QMessageBox.warning(self, "警告", "上游节点无数据输入。")
            return

        try:
            res = self.node.getInput(0).serialize()
            value = res.get("value")
            if not isinstance(value, pd.DataFrame):
                QMessageBox.warning(self, "警告", "序列化结果中缺少有效数据表。")
                return

            self.df = value.copy()
            self.df = self.df.replace([None, "", " "], np.nan)
            for col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors="coerce")

            if self.df.empty:
                QMessageBox.warning(self, "警告", "加载的数据为空。")
                return

            self.node.eval()
            self.on_initUI()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"数据加载失败：{str(e)}")

    def on_initUI(self):
        self.select_para.clear()
        self.button_dict.clear()
        self.layout_dict.clear()
        self.clear_layout(self.ui.verticalLayout_data)
        self.clear_layout(self.ui.verticalLayout_plot)

        for item in self.df.columns.tolist():
            series = pd.to_numeric(self.df[item], errors="coerce").dropna()
            if series.empty:
                continue

            h_layout = QHBoxLayout()
            label = QLabel(str(item))
            h_layout.addWidget(label)

            btn = QPushButton()
            btn.setIcon(QIcon("icon/linePlot"))
            btn.setIconSize(QSize(25, 25))
            btn.setStyleSheet("background: transparent; border: 0px;")
            btn.clicked.connect(lambda checked=False, b=btn: self.on_draw(b))
            self.button_dict[btn] = item
            h_layout.addWidget(btn)

            self.ui.verticalLayout_data.addLayout(h_layout)
            self.select_para.append(item)

        if not self.select_para:
            QMessageBox.warning(self, "警告", "未发现可绘图的数值列。")

    def on_draw(self, button):
        para = self.button_dict.get(button)
        if para is None:
            QMessageBox.warning(self, "警告", "未选中有效参数。")
            return

        plot_type = self.ui.cB_type.currentText()
        if plot_type == "1to1":
            self.draw_cnt = 0
            self.draw_2to1_widget = None
            self.draw_3to1_widget = None
            self.on_draw_1to1(para)
        elif plot_type == "2to1":
            self.on_draw_2to1(para)
        elif plot_type == "3to1":
            self.on_draw_3to1(para)

    def on_draw_1to1(self, para):
        data = pd.to_numeric(self.df[para], errors="coerce").dropna()
        if data.empty:
            QMessageBox.warning(self, "警告", f"{para} 没有有效数据。")
            return

        plot_widget = self._build_plot_widget(para)
        self._plot_series(
            plot_widget,
            data,
            (random.randint(40, 220), random.randint(40, 220), random.randint(40, 220)),
        )
        self.ui.verticalLayout_plot.addWidget(plot_widget)
        self.layout_dict[para] = plot_widget

    def on_draw_2to1(self, para):
        data = pd.to_numeric(self.df[para], errors="coerce").dropna()
        if data.empty:
            QMessageBox.warning(self, "警告", f"{para} 没有有效数据。")
            return

        self.draw_cnt = min(self.draw_cnt + 1, 2)
        if self.draw_cnt == 1 or self.draw_2to1_widget is None:
            self.draw_2to1_widget = self._build_plot_widget("Amplitude")
            self.legend = self.draw_2to1_widget.addLegend(labelTextColor="k")
            self.legend.setBrush("w")
            self.ui.verticalLayout_plot.addWidget(self.draw_2to1_widget)

        colors = [(7, 7, 7), (255, 59, 59)]
        curve = self._plot_series(self.draw_2to1_widget, data, colors[self.draw_cnt - 1], para)
        self.legend.addItem(curve, para)

        if self.draw_cnt == 2:
            self.draw_cnt = 0

    def on_draw_3to1(self, para):
        data = pd.to_numeric(self.df[para], errors="coerce").dropna()
        if data.empty:
            QMessageBox.warning(self, "警告", f"{para} 没有有效数据。")
            return

        self.draw_cnt = min(self.draw_cnt + 1, 3)
        if self.draw_cnt == 1 or self.draw_3to1_widget is None:
            self.draw_3to1_widget = self._build_plot_widget("Amplitude")
            self.legend = self.draw_3to1_widget.addLegend(labelTextColor="k")
            self.legend.setBrush("w")
            self.ui.verticalLayout_plot.addWidget(self.draw_3to1_widget)

        colors = [(40, 120, 181), (200, 36, 35), (0, 128, 36)]
        curve = self._plot_series(self.draw_3to1_widget, data, colors[self.draw_cnt - 1], para)
        self.legend.addItem(curve, para)

        if self.draw_cnt == 3:
            self.draw_cnt = 0

    def on_Clear(self):
        self.clear_layout(self.ui.verticalLayout_plot)
        self.draw_cnt = 0
        self.draw_2to1_widget = None
        self.draw_3to1_widget = None
        self.legend = None
