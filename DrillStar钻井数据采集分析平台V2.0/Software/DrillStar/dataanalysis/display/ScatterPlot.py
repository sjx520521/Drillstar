import math

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from dataanalysis.buttonNode import ButtonNode


pg.setConfigOptions(antialias=True, useOpenGL=False, enableExperimental=False)


class Win_DisplayScatterPlot(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.node = node
        self.df = pd.DataFrame()
        self.numeric_columns = []
        self.annotation_item = None

        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("数据展示 [散点图]")
        self.resize(980, 620)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        control_widget = QWidget(self)
        control_widget.setFixedWidth(280)
        control_layout = QVBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(10)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)

        self.cB_x = QComboBox()
        self.cB_y = QComboBox()
        self.check_trend = QCheckBox("显示趋势线")
        self.check_trend.setChecked(True)

        form_layout.addRow("X 列", self.cB_x)
        form_layout.addRow("Y 列", self.cB_y)
        form_layout.addRow("", self.check_trend)

        control_layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        self.btn_Load = QPushButton("Load")
        self.btn_Draw = QPushButton("Draw")
        self.btn_Clear = QPushButton("Clear")
        btn_layout.addWidget(self.btn_Load)
        btn_layout.addWidget(self.btn_Draw)
        btn_layout.addWidget(self.btn_Clear)
        control_layout.addLayout(btn_layout)

        self.label_status = QLabel("状态：请先加载数据。")
        self.label_status.setWordWrap(True)
        self.label_formula = QLabel("趋势线：未计算")
        self.label_formula.setWordWrap(True)
        control_layout.addWidget(self.label_status)
        control_layout.addWidget(self.label_formula)
        control_layout.addStretch(1)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("w")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.35)
        self.plot_widget.getAxis("bottom").setTickFont(QFont("Arial", 10))
        self.plot_widget.getAxis("left").setTickFont(QFont("Arial", 10))
        self.plot_widget.addLegend(labelTextColor="k")

        main_layout.addWidget(control_widget)
        main_layout.addWidget(self.plot_widget, 1)

        self.btn_Load.clicked.connect(self.on_Load)
        self.btn_Draw.clicked.connect(self.on_Draw)
        self.btn_Clear.clicked.connect(self.on_Clear)

    def _get_numeric_columns(self):
        columns = []
        for column in self.df.columns:
            series = pd.to_numeric(self.df[column], errors="coerce")
            if series.notna().sum() > 0:
                columns.append(column)
        return columns

    def _format_formula(self, slope: float, intercept: float, r_squared: float) -> str:
        sign = "+" if intercept >= 0 else "-"
        return f"趋势线：y = {slope:.6g}x {sign} {abs(intercept):.6g}    R^2 = {r_squared:.6f}"

    def on_Load(self):
        input_node = self.node.getInput(0)
        if input_node is None:
            self.node.markDirty()
            self.node.markInvalid()
            QMessageBox.warning(self, "警告", "上游节点没有可用数据。")
            return

        try:
            result = input_node.serialize()
            value = result.get("value")
            if not isinstance(value, pd.DataFrame) or value.empty:
                QMessageBox.warning(self, "警告", "加载的数据为空，无法绘制散点图。")
                return

            self.df = value.copy()
            self.numeric_columns = self._get_numeric_columns()
            if len(self.numeric_columns) < 2:
                QMessageBox.warning(self, "警告", "散点图至少需要两列数值数据。")
                return

            self.cB_x.clear()
            self.cB_y.clear()
            self.cB_x.addItems([str(col) for col in self.numeric_columns])
            self.cB_y.addItems([str(col) for col in self.numeric_columns])
            if len(self.numeric_columns) > 1:
                self.cB_y.setCurrentIndex(1)

            self.label_status.setText(
                f"状态：已加载 {self.df.shape[0]} 行、{self.df.shape[1]} 列，"
                f"可绘制数值列 {len(self.numeric_columns)} 列。"
            )
            self.label_formula.setText("趋势线：未计算")
            self.node.eval()
            QMessageBox.information(self, "成功", "散点图数据加载完成。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"散点图数据加载失败：{exc}")

    def on_Draw(self):
        if self.df.empty:
            QMessageBox.warning(self, "警告", "请先加载数据。")
            return

        x_column = self.cB_x.currentText()
        y_column = self.cB_y.currentText()
        if not x_column or not y_column:
            QMessageBox.warning(self, "警告", "请选择 X 列和 Y 列。")
            return

        try:
            plot_df = pd.DataFrame(
                {
                    "x": pd.to_numeric(self.df[x_column], errors="coerce"),
                    "y": pd.to_numeric(self.df[y_column], errors="coerce"),
                }
            ).dropna()

            if plot_df.empty:
                raise ValueError("所选列没有可用的成对数值数据。")
            if len(plot_df) < 2:
                raise ValueError("有效数据点不足，无法绘制散点图。")

            self.on_Clear()

            self.plot_widget.setLabel("bottom", x_column)
            self.plot_widget.setLabel("left", y_column)

            scatter_item = pg.ScatterPlotItem(
                x=plot_df["x"].to_numpy(),
                y=plot_df["y"].to_numpy(),
                pen=pg.mkPen(60, 120, 216, 180),
                brush=pg.mkBrush(60, 120, 216, 130),
                size=7,
                name="样本点",
            )
            self.plot_widget.addItem(scatter_item)

            if self.check_trend.isChecked():
                x_values = plot_df["x"].to_numpy(dtype=float)
                y_values = plot_df["y"].to_numpy(dtype=float)

                slope, intercept = np.polyfit(x_values, y_values, 1)
                y_pred = slope * x_values + intercept
                ss_res = float(np.sum((y_values - y_pred) ** 2))
                ss_tot = float(np.sum((y_values - np.mean(y_values)) ** 2))
                r_squared = 1.0 - ss_res / ss_tot if not math.isclose(ss_tot, 0.0) else 1.0

                x_line = np.linspace(np.min(x_values), np.max(x_values), 200)
                y_line = slope * x_line + intercept
                self.plot_widget.plot(
                    x_line,
                    y_line,
                    pen=pg.mkPen(color=(220, 53, 69), width=2),
                    name="趋势线",
                )

                formula_text = self._format_formula(slope, intercept, r_squared)
                self.label_formula.setText(formula_text)

                self.annotation_item = pg.TextItem(
                    html=f"<div style='background-color:rgba(255,255,255,180); color:#222; padding:4px;'>"
                    f"{formula_text}</div>",
                    anchor=(0, 1),
                )
                self.annotation_item.setPos(float(np.min(x_values)), float(np.max(y_values)))
                self.plot_widget.addItem(self.annotation_item)
            else:
                self.label_formula.setText("趋势线：未显示")

            self.label_status.setText(f"状态：已绘制 {len(plot_df)} 个数据点。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"散点图绘制失败：{exc}")

    def on_Clear(self):
        self.plot_widget.clear()
        self.plot_widget.addLegend(labelTextColor="k")
        self.annotation_item = None
        self.label_formula.setText("趋势线：未计算")
