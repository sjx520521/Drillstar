import os

import joblib
from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from dataanalysis.buttonNode import ButtonNode
from dataanalysis.model.model_artifact import artifact_summary, is_model_artifact


class Win_LoadModel(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.node = node
        self.artifact = None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("DataAnalysis [加载模型]")
        self.resize(560, 360)

        root = QVBoxLayout(self)
        self.label_info = QLabel("请选择已保存的 DrillStar 模型包。")
        self.label_info.setWordWrap(True)
        root.addWidget(self.label_info)

        self.text_info = QTextBrowser()
        root.addWidget(self.text_info, 1)

        buttons = QHBoxLayout()
        self.btn_open = QPushButton("打开")
        self.btn_transfer = QPushButton("传递")
        self.btn_transfer.setEnabled(False)
        buttons.addWidget(self.btn_open)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_transfer)
        root.addLayout(buttons)

        self.btn_open.clicked.connect(self.on_Open)
        self.btn_transfer.clicked.connect(self.on_Transfer)

    def on_Open(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "打开模型",
            os.path.join(os.path.expanduser("~"), "Desktop"),
            "DrillStar模型 (*.dsmodel);;Joblib文件 (*.joblib);;所有文件 (*)",
        )
        if not filename:
            return

        try:
            artifact = joblib.load(filename)
            if not is_model_artifact(artifact):
                raise ValueError("所选文件不是 DrillStar 模型包。")
            self.artifact = artifact
            self.text_info.setPlainText(artifact_summary(artifact))
            self.label_info.setText(f"已加载：{filename}")
            self.btn_transfer.setEnabled(True)
        except Exception as exc:
            self.artifact = None
            self.btn_transfer.setEnabled(False)
            QMessageBox.critical(self, "错误", f"加载失败：\n{exc}")

    def on_Transfer(self):
        if self.artifact is None:
            QMessageBox.warning(self, "警告", "请先打开模型包。")
            return

        try:
            if self.node.LoadData(self.artifact):
                self.node.eval()
                self.node.evalChildren()
            QMessageBox.information(self, "成功", "模型包已传递。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"传递失败：\n{exc}")
