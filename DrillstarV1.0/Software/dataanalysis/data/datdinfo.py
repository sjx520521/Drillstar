import pandas as pd
from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtWidgets import (
    QLabel,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from dataanalysis.buttonNode import ButtonNode
from dataanalysis.ui.datainfo_ui import Ui_datainfo


class Win_DataInfo(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.ui = Ui_datainfo()
        self.ui.setupUi(self)
        self.setWindowTitle("DataAnalysis [数据信息]")

        self.node = node
        self.df = pd.DataFrame()
        self._is_closed = False
        self._column_labels = []

        self._init_scroll_area()
        self._init_info_panel()
        self._init_node_window()

        self.ui.btn_Load.clicked.connect(self.on_Load)
        self.installEventFilter(self)

    def _init_scroll_area(self):
        info_layout = self.ui.verticalLayout_info
        container_layout = self.ui.verticalLayout_3

        while container_layout.count():
            item = container_layout.takeAt(0)
            if item.layout() is info_layout:
                break

        self.scroll_area = QScrollArea(self.ui.groupBox)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.scroll_widget = QWidget(self.scroll_area)
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(6)
        self.scroll_layout.addLayout(info_layout)
        self.scroll_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_widget)
        container_layout.addWidget(self.scroll_area)

    def _init_info_panel(self):
        for label in [self.ui.label_name, self.ui.label_size, self.ui.label_columns]:
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            label.setStyleSheet("QLabel { padding: 2px; }")

        self.ui.label_columns.setText("字段列表：")

        self.columns_container = QWidget(self.scroll_widget)
        self.columns_layout = QVBoxLayout(self.columns_container)
        self.columns_layout.setContentsMargins(8, 0, 0, 0)
        self.columns_layout.setSpacing(4)

        insert_index = self.scroll_layout.indexOf(self.ui.label_columns) + 1
        self.scroll_layout.insertWidget(insert_index, self.columns_container)

        self._reset_labels()

    def _init_node_window(self):
        if not hasattr(self.node, "window") or self.node.window is None:
            setattr(self.node, "window", self)

    def _reset_labels(self):
        self.ui.label_name.setText("数据类型：未加载")
        self.ui.label_size.setText("数据规模：0 行 x 0 列")
        self.ui.label_columns.setText("字段列表：")
        self._set_column_lines([])

    def _set_column_lines(self, columns):
        for label in self._column_labels:
            self.columns_layout.removeWidget(label)
            label.deleteLater()
        self._column_labels.clear()

        if not columns:
            empty_label = QLabel("暂无字段")
            empty_label.setStyleSheet("QLabel { padding: 2px; color: #666666; }")
            empty_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.columns_layout.addWidget(empty_label)
            self._column_labels.append(empty_label)
            return

        for index, column in enumerate(columns, start=1):
            label = QLabel(f"{index}. {column}")
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            label.setStyleSheet("QLabel { padding: 2px; }")
            self.columns_layout.addWidget(label)
            self._column_labels.append(label)

    def eventFilter(self, obj, event):
        if obj == self and event.type() == QEvent.Close:
            self.hide()
            self._is_closed = True
            return True
        return super().eventFilter(obj, event)

    def on_Load(self):
        self.df = pd.DataFrame()
        self._reset_labels()

        try:
            input_node = self.node.getInput(0)
            if input_node is None:
                self.node.markDirty()
                self.node.markInvalid()
                QMessageBox.warning(self, "警告", "上游节点没有可用数据。")
                return

            try:
                res = input_node.serialize()
            except Exception as exc:
                QMessageBox.critical(self, "错误", f"上游节点序列化失败：{exc}")
                self.node.markInvalid()
                return

            if not isinstance(res, dict):
                QMessageBox.critical(self, "错误", "上游节点返回的数据格式不正确。")
                self.node.markInvalid()
                return

            self.df = res.get("value", pd.DataFrame())
            data_title = res.get("title", "未命名数据")

            if not isinstance(self.df, pd.DataFrame):
                QMessageBox.critical(self, "错误", "加载结果不是有效的数据表。")
                self.node.markInvalid()
                return

            self.node.eval()

            self.ui.label_name.setText(f"数据类型：{data_title}")
            self.ui.label_size.setText(f"数据规模：{self.df.shape[0]} 行 x {self.df.shape[1]} 列")
            self._set_column_lines(self.df.columns.tolist())

            if self.df.empty:
                QMessageBox.information(self, "提示", "数据已加载，但当前数据表为空。")
            else:
                QMessageBox.information(
                    self,
                    "成功",
                    f"数据加载完成，共 {self.df.shape[0]} 行、{self.df.shape[1]} 列。",
                )
        except Exception as exc:
            self.node.markInvalid()
            QMessageBox.critical(self, "错误", f"加载数据失败：{exc}")

    def re_show(self):
        self._is_closed = False
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        self.hide()
        self._is_closed = True
        event.ignore()
