import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from dataanalysis.async_task import BusyTaskMixin
from dataanalysis.buttonNode import ButtonNode
from dataanalysis.model.model_artifact import build_model_artifact


class Win_ModelPCA(QWidget, BusyTaskMixin):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.node = node
        self.df = pd.DataFrame()
        self.df_result = pd.DataFrame()
        self.numeric_columns = []
        self.column_checkboxes = {}
        self.model = None

        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("DataAnalysis [PCA]")
        self.resize(420, 520)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        info_group = QGroupBox("PCA 参数")
        info_layout = QFormLayout(info_group)
        info_layout.setLabelAlignment(Qt.AlignLeft)

        self.label_info = QLabel("状态：请先加载数据。")
        self.label_info.setWordWrap(True)
        info_layout.addRow(self.label_info)

        self.spin_components = QSpinBox()
        self.spin_components.setMinimum(1)
        self.spin_components.setValue(2)
        info_layout.addRow("主成分数", self.spin_components)

        self.checkbox_standardize = QCheckBox("计算前进行标准化")
        self.checkbox_standardize.setChecked(True)
        info_layout.addRow(self.checkbox_standardize)
        root_layout.addWidget(info_group)

        column_group = QGroupBox("特征列选择")
        column_layout = QVBoxLayout(column_group)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_content_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_content_layout.setContentsMargins(8, 8, 8, 8)
        self.scroll_content_layout.setSpacing(6)
        self.scroll_area.setWidget(self.scroll_widget)
        column_layout.addWidget(self.scroll_area)
        root_layout.addWidget(column_group, 1)

        self.label_result = QLabel("结果：尚未计算。")
        self.label_result.setWordWrap(True)
        root_layout.addWidget(self.label_result)

        button_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load")
        self.btn_calculate = QPushButton("Calculate")
        self.btn_transfer = QPushButton("Transfer")
        self.btn_transfer.setEnabled(False)
        button_layout.addWidget(self.btn_load)
        button_layout.addWidget(self.btn_calculate)
        button_layout.addStretch(1)
        button_layout.addWidget(self.btn_transfer)
        root_layout.addLayout(button_layout)

        self.btn_load.clicked.connect(self.on_Load)
        self.btn_calculate.clicked.connect(self.on_Calculate)
        self.btn_transfer.clicked.connect(self.on_Transfer)

    def _clear_column_layout(self):
        while self.scroll_content_layout.count():
            item = self.scroll_content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _is_numeric_candidate(self, series: pd.Series) -> bool:
        numeric_series = pd.to_numeric(series, errors="coerce")
        return numeric_series.notna().sum() > 0

    def _build_column_selector(self):
        self._clear_column_layout()
        self.column_checkboxes.clear()
        for column in self.numeric_columns:
            checkbox = QCheckBox(str(column))
            checkbox.setChecked(True)
            self.scroll_content_layout.addWidget(checkbox)
            self.column_checkboxes[column] = checkbox
        self.scroll_content_layout.addStretch(1)

    def on_Load(self):
        input_node = self.node.getInput(0)
        if input_node is None:
            self.node.markDirty()
            self.node.markInvalid()
            QMessageBox.warning(self, "警告", "上游节点没有可用数据。")
            return

        try:
            result = input_node.serialize()
            value = result.get("value", pd.DataFrame())
            if not isinstance(value, pd.DataFrame) or value.empty:
                QMessageBox.warning(self, "警告", "加载的数据为空，无法进行 PCA 分析。")
                return

            self.df = value.copy()
            self.numeric_columns = [col for col in self.df.columns if self._is_numeric_candidate(self.df[col])]
            if not self.numeric_columns:
                QMessageBox.warning(self, "警告", "未检测到可用于 PCA 的数值列。")
                return

            max_components = max(1, min(len(self.numeric_columns), len(self.df)))
            self.spin_components.setMaximum(max_components)
            self.spin_components.setValue(min(2, max_components))
            self._build_column_selector()

            self.df_result = pd.DataFrame()
            self.btn_transfer.setEnabled(False)
            self.label_info.setText(
                f"状态：已加载 {self.df.shape[0]} 行、{self.df.shape[1]} 列，可用数值特征 {len(self.numeric_columns)} 列。"
            )
            self.label_result.setText("结果：尚未计算。")
            self.node.eval()
            QMessageBox.information(self, "成功", "PCA 数据加载完成。")
        except Exception as exc:
            self.node.markInvalid()
            QMessageBox.critical(self, "错误", f"PCA 数据加载失败：{exc}")

    def _calculate_pca(self, selected_columns, component_count, standardize):
        x_df = self.df[selected_columns].apply(pd.to_numeric, errors="coerce")
        if x_df.isna().all(axis=None):
            raise ValueError("所选特征列无法转换为数值。")

        x_df = x_df.fillna(x_df.median(numeric_only=True)).fillna(0.0)
        component_count = min(component_count, len(selected_columns), len(x_df))
        if component_count < 1:
            raise ValueError("主成分数设置无效。")

        x_values = x_df.values
        scaler = None
        if standardize:
            scaler = StandardScaler()
            x_values = scaler.fit_transform(x_values)

        model = PCA(n_components=component_count)
        transformed = model.fit_transform(x_values)
        columns = [f"PCA_PC{i + 1}" for i in range(component_count)]
        df_result = pd.DataFrame(transformed, columns=columns, index=self.df.index)
        return df_result, model, scaler, list(selected_columns)

    def on_Calculate(self):
        if self.df.empty:
            QMessageBox.warning(self, "警告", "请先加载数据。")
            return

        selected_columns = [col for col, checkbox in self.column_checkboxes.items() if checkbox.isChecked()]
        if not selected_columns:
            QMessageBox.warning(self, "警告", "请至少选择一列特征。")
            return

        self._start_background_task(
            "PCA分析",
            "正在执行 PCA 计算，请稍候...",
            self._calculate_pca,
            self._on_calculate_finished,
            self._on_calculate_failed,
            selected_columns,
            self.spin_components.value(),
            self.checkbox_standardize.isChecked(),
        )

    def _on_calculate_finished(self, result):
        self.df_result, self.model, self.preprocessor, self.feature_columns = result
        self.model_artifact = build_model_artifact(
            model_name="PCA",
            model=self.model,
            task_type="pca",
            feature_columns=self.feature_columns,
            preprocessor=self.preprocessor,
            output_prefix="PCA",
        )
        explained = [f"{ratio:.4f}" for ratio in self.model.explained_variance_ratio_]
        self.btn_transfer.setEnabled(True)
        self.label_result.setText(f"结果：PCA 计算完成。方差贡献率 {', '.join(explained)}")
        QMessageBox.information(self, "成功", "PCA 计算完成。")

    def _on_calculate_failed(self, message):
        self.df_result = pd.DataFrame()
        self.btn_transfer.setEnabled(False)
        QMessageBox.critical(self, "错误", f"PCA 计算失败：{message}")

    def on_Transfer(self):
        if self.df_result.empty:
            QMessageBox.warning(self, "警告", "请先完成计算。")
            return

        try:
            if self.node.LoadData(self.df_result):
                self.node.eval()
                self.node.evalChildren()
            QMessageBox.information(self, "提示", "PCA 结果已传递。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"PCA 结果传递失败：{exc}")
