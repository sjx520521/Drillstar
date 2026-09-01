import pandas as pd
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from dataanalysis.buttonNode import ButtonNode
from dataanalysis.model.model_artifact import (
    artifact_summary,
    resolve_model_artifact,
    run_artifact_prediction,
)


class Win_ModelPredict(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.node = node
        self.artifact = None
        self.df = pd.DataFrame()
        self.df_result = pd.DataFrame()
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("DataAnalysis [模型应用]")
        self.resize(720, 420)

        root = QVBoxLayout(self)
        self.label_info = QLabel("请将输入1连接到模型包，输入2连接到待应用数据。")
        self.label_info.setWordWrap(True)
        root.addWidget(self.label_info)

        self.text_info = QTextBrowser()
        root.addWidget(self.text_info, 1)

        buttons = QHBoxLayout()
        self.btn_load = QPushButton("加载")
        self.btn_predict = QPushButton("应用")
        self.btn_transfer = QPushButton("传递")
        self.btn_predict.setEnabled(False)
        self.btn_transfer.setEnabled(False)
        buttons.addWidget(self.btn_load)
        buttons.addWidget(self.btn_predict)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_transfer)
        root.addLayout(buttons)

        self.btn_load.clicked.connect(self.on_Load)
        self.btn_predict.clicked.connect(self.on_Predict)
        self.btn_transfer.clicked.connect(self.on_Transfer)

    def on_Load(self):
        model_node = self.node.getInput(0)
        data_node = self.node.getInput(1)

        if model_node is None:
            QMessageBox.warning(self, "警告", "输入1必须连接已训练或已加载的模型节点。")
            return
        if data_node is None:
            QMessageBox.warning(self, "警告", "输入2必须连接数据节点。")
            return

        artifact = resolve_model_artifact(model_node)
        if artifact is None:
            QMessageBox.warning(self, "警告", "输入1未找到有效模型包。")
            return

        try:
            data_value = data_node.serialize().get("value", pd.DataFrame())
            if not isinstance(data_value, pd.DataFrame) or data_value.empty:
                raise ValueError("输入2不包含非空数据表。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"数据加载失败：\n{exc}")
            return

        self.artifact = artifact
        self.df = data_value.copy()
        self.df_result = pd.DataFrame()
        self.btn_predict.setEnabled(True)
        self.btn_transfer.setEnabled(False)
        self.label_info.setText(f"已加载数据：{self.df.shape[0]} 行 x {self.df.shape[1]} 列")
        self.text_info.setPlainText(artifact_summary(artifact))
        self.node.markDirty(False)
        self.node.markInvalid(False)

    def on_Predict(self):
        if self.artifact is None or self.df.empty:
            QMessageBox.warning(self, "警告", "请先加载模型和数据。")
            return

        try:
            self.df_result = run_artifact_prediction(self.artifact, self.df)
            added = [col for col in self.df_result.columns if col not in self.df.columns]
            self.btn_transfer.setEnabled(True)
            self.text_info.setPlainText(
                artifact_summary(self.artifact)
                + "\n\n模型应用完成。\n新增列："
                + ", ".join(added)
            )
            QMessageBox.information(self, "成功", "模型应用完成。")
        except Exception as exc:
            self.df_result = pd.DataFrame()
            self.btn_transfer.setEnabled(False)
            QMessageBox.critical(self, "错误", f"模型应用失败：\n{exc}")

    def on_Transfer(self):
        if self.df_result.empty:
            QMessageBox.warning(self, "警告", "请先完成模型应用。")
            return

        try:
            if self.node.LoadData(self.df_result):
                self.node.eval()
                self.node.evalChildren()
            QMessageBox.information(self, "成功", "模型应用结果已传递。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"传递失败：\n{exc}")
