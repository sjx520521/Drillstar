from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QMessageBox
import pandas as pd

from dataanalysis.buttonNode import ButtonNode
from dataanalysis.ui.oilFuncStandardization_ui import Ui_Standardization


WINDOW_TITLE = "Special [Standardization]"
DEFAULT_K_VALUE = "1"
DEFAULT_B_VALUE = "0"
INPUT_INDEX = 0


class Win_Standardization(QWidget):
    """对输入表格中的数值列执行 y = k*x + b 线性换算。"""

    def __init__(self, node: ButtonNode):
        super().__init__()
        self.ui = Ui_Standardization()
        self.ui.setupUi(self)
        self.setWindowTitle(WINDOW_TITLE)

        self.node = node
        self.df = pd.DataFrame()
        self.df_cal = pd.DataFrame()
        self.coefficient_k_dict = {}
        self.intercept_b_dict = {}

        self.ui.btn_Load.clicked.connect(self.on_Load)
        self.ui.btn_Cal.clicked.connect(self.on_Cal)
        self.ui.btn_Transfer.clicked.connect(self.on_Transfer)

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
            del item

    def _is_numeric_column(self, series: pd.Series) -> bool:
        return pd.api.types.is_numeric_dtype(series.dtype)

    def on_Load(self):
        input_data = self.node.getInput(INPUT_INDEX)
        if input_data is None:
            self.node.markDirty()
            self.node.markInvalid()
            return

        try:
            res = input_data.serialize()
            self.df = res.get("value", pd.DataFrame())
            if self.df.empty:
                return
        except Exception:
            return

        self.node.eval()
        self.on_initUI()

    def on_initUI(self):
        self._clear_layout(self.ui.verticalLayout)
        self.coefficient_k_dict.clear()
        self.intercept_b_dict.clear()
        self.ui.verticalLayout.setAlignment(Qt.AlignTop)
        self.ui.verticalLayout.setSpacing(8)

        for header in self.df.columns.tolist():
            h_layout = QHBoxLayout()
            h_layout.setContentsMargins(0, 0, 0, 0)
            h_layout.setSpacing(8)

            name_label = QLabel(str(header))
            h_layout.addWidget(name_label)
            h_layout.addStretch(1)

            if self._is_numeric_column(self.df[header]):
                k_label = QLabel("k")
                h_layout.addWidget(k_label)
                k_edit = QLineEdit(DEFAULT_K_VALUE)
                k_edit.setMaximumWidth(160)
                h_layout.addWidget(k_edit)

                b_label = QLabel("b")
                h_layout.addWidget(b_label)
                b_edit = QLineEdit(DEFAULT_B_VALUE)
                b_edit.setMaximumWidth(160)
                h_layout.addWidget(b_edit)

                self.coefficient_k_dict[header] = k_edit
                self.intercept_b_dict[header] = b_edit
            else:
                note_label = QLabel("非数值列，无需转换")
                note_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                note_label.setStyleSheet("color: #666666;")
                h_layout.addWidget(note_label)

            self.ui.verticalLayout.addLayout(h_layout)

        self.ui.verticalLayout.addStretch(1)

    def on_Cal(self):
        try:
            self.on_Standardization()
            self.df_cal = self.df_cal.round(2)
            QMessageBox.information(self, "提示", "计算完成")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"计算失败：{str(e)}")

    def on_Transfer(self):
        try:
            if self.df_cal.empty:
                raise ValueError("请先执行计算操作")

            if self.node.LoadData(self.df_cal):
                self.node.eval()
                self.node.evalChildren()

            QMessageBox.information(self, "提示", "标定处理完成")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"标定处理失败：{str(e)}")

    def on_Standardization(self):
        self.df_cal = self.df.copy()

        for header in self.df.columns.tolist():
            if header not in self.coefficient_k_dict:
                continue

            k_text = self.coefficient_k_dict[header].text().strip()
            b_text = self.intercept_b_dict[header].text().strip()

            try:
                k = float(k_text)
                b = float(b_text)
            except ValueError:
                raise ValueError(f"列【{header}】的 k/b 值必须为有效数字")

            self.df_cal[header] = k * self.df_cal[header] + b
