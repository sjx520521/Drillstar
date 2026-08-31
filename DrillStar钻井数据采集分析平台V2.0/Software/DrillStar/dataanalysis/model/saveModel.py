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
from dataanalysis.model.model_artifact import artifact_summary, resolve_model_artifact


class Win_SaveModel(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.node = node
        self.artifact = None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("DataAnalysis [保存模型]")
        self.resize(560, 360)

        root = QVBoxLayout(self)
        self.label_info = QLabel("请先加载已训练的模型节点，再保存模型包。")
        self.label_info.setWordWrap(True)
        root.addWidget(self.label_info)

        self.text_info = QTextBrowser()
        root.addWidget(self.text_info, 1)

        buttons = QHBoxLayout()
        self.btn_load = QPushButton("加载")
        self.btn_save = QPushButton("保存")
        self.btn_save.setEnabled(False)
        buttons.addWidget(self.btn_load)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_save)
        root.addLayout(buttons)

        self.btn_load.clicked.connect(self.on_Load)
        self.btn_save.clicked.connect(self.on_Save)

    def on_Load(self):
        input_node = self.node.getInput(0)
        if input_node is None:
            self.node.markDirty()
            self.node.markInvalid()
            QMessageBox.warning(self, "警告", "未连接上游模型节点。")
            return

        artifact = resolve_model_artifact(input_node)
        if artifact is None:
            QMessageBox.warning(
                self,
                "警告",
                "未找到已训练的模型包，请先完成模型计算。",
            )
            return

        self.artifact = artifact
        self.text_info.setPlainText(artifact_summary(artifact))
        self.label_info.setText("模型包已加载。")
        self.btn_save.setEnabled(True)
        self.node.markDirty(False)
        self.node.markInvalid(False)

    def on_Save(self):
        if self.artifact is None:
            QMessageBox.warning(self, "警告", "请先加载模型包。")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "保存模型",
            os.path.join(os.path.expanduser("~"), "Desktop", "drillstar_model.dsmodel"),
            "DrillStar模型 (*.dsmodel);;Joblib文件 (*.joblib);;所有文件 (*)",
        )
        if not filename:
            return
        if not os.path.splitext(filename)[1]:
            filename += ".dsmodel"

        try:
            joblib.dump(self.artifact, filename)
            QMessageBox.information(self, "成功", f"模型已保存：\n{filename}")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"保存失败：\n{exc}")
