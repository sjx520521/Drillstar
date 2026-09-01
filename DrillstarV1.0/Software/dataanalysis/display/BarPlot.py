import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
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


class Win_DisplayBarPlot(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.node = node
        self.df = pd.DataFrame()
        self.max_bars = 80

        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("数据展示 [柱状图]")
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
        self.cB_category = QComboBox()
        self.cB_value = QComboBox()
        form_layout.addRow("类别列", self.cB_category)
        form_layout.addRow("数值列", self.cB_value)
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
        self.label_note = QLabel("说明：类别过多时将自动抽样显示，避免图面过密。")
        self.label_note.setWordWrap(True)
        control_layout.addWidget(self.label_status)
        control_layout.addWidget(self.label_note)
        control_layout.addStretch(1)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("w")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.25)
        self.plot_widget.getAxis("bottom").setTickFont(QFont("Arial", 9))
        self.plot_widget.getAxis("left").setTickFont(QFont("Arial", 10))

        main_layout.addWidget(control_widget)
        main_layout.addWidget(self.plot_widget, 1)

        self.btn_Load.clicked.connect(self.on_Load)
        self.btn_Draw.clicked.connect(self.on_Draw)
        self.btn_Clear.clicked.connect(self.on_Clear)

    def _numeric_columns(self):
        columns = []
        for column in self.df.columns:
            series = pd.to_numeric(self.df[column], errors="coerce")
            if series.notna().sum() > 0:
                columns.append(column)
        return columns

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
                QMessageBox.warning(self, "警告", "加载的数据为空，无法绘制柱状图。")
                return

            self.df = value.copy()
            numeric_columns = self._numeric_columns()
            if not numeric_columns:
                QMessageBox.warning(self, "警告", "未检测到可用数值列。")
                return

            self.cB_value.clear()
            self.cB_value.addItems([str(col) for col in numeric_columns])

            self.cB_category.clear()
            self.cB_category.addItem("行号")
            self.cB_category.addItems([str(col) for col in self.df.columns])

            self.label_status.setText(
                f"状态：已加载 {self.df.shape[0]} 行、{self.df.shape[1]} 列，"
                f"可绘制数值列 {len(numeric_columns)} 列。"
            )
            self.node.eval()
            QMessageBox.information(self, "成功", "柱状图数据加载完成。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"柱状图数据加载失败：{exc}")

    def on_Draw(self):
        if self.df.empty:
            QMessageBox.warning(self, "警告", "请先加载数据。")
            return

        category_column = self.cB_category.currentText()
        value_column = self.cB_value.currentText()
        if not value_column:
            QMessageBox.warning(self, "警告", "请选择数值列。")
            return

        try:
            value_series = pd.to_numeric(self.df[value_column], errors="coerce")
            if category_column == "行号":
                category_series = pd.Series(np.arange(len(self.df)), index=self.df.index).astype(str)
            else:
                category_series = self.df[category_column].astype(str)

            plot_df = pd.DataFrame({"category": category_series, "value": value_series}).dropna()
            if plot_df.empty:
                raise ValueError("所选列没有可用数据。")

            if len(plot_df) > self.max_bars:
                indices = np.linspace(0, len(plot_df) - 1, self.max_bars, dtype=int)
                plot_df = plot_df.iloc[indices].reset_index(drop=True)
                self.label_note.setText(f"说明：原始数据较多，当前已抽样显示 {len(plot_df)} 根柱。")
            else:
                self.label_note.setText("说明：当前已显示全部柱。")

            self.on_Clear()

            x_positions = np.arange(len(plot_df), dtype=float)
            bar_item = pg.BarGraphItem(
                x=x_positions,
                height=plot_df["value"].to_numpy(dtype=float),
                width=0.7,
                brush=(66, 133, 244, 180),
                pen=pg.mkPen(color=(33, 97, 180), width=1),
            )
            self.plot_widget.addItem(bar_item)

            tick_step = max(1, len(plot_df) // 12)
            ticks = [(float(i), str(plot_df.iloc[i]["category"])) for i in range(0, len(plot_df), tick_step)]
            self.plot_widget.getAxis("bottom").setTicks([ticks])
            self.plot_widget.setLabel("bottom", category_column)
            self.plot_widget.setLabel("left", value_column)
            self.plot_widget.setXRange(-0.8, len(plot_df) - 0.2, padding=0)

            self.label_status.setText(f"状态：已绘制 {len(plot_df)} 根柱。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"柱状图绘制失败：{exc}")

    def on_Clear(self):
        self.plot_widget.clear()
