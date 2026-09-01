import numpy as np
import pandas as pd
from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.svm import SVC

from dataanalysis.buttonNode import ButtonNode


class SVMWorker(QThread):
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, df, target_column, feature_columns, params):
        super().__init__()
        self.df = df.copy()
        self.target_column = target_column
        self.feature_columns = list(feature_columns)
        self.params = dict(params)

    def run(self):
        try:
            x_df = self.df[self.feature_columns].apply(pd.to_numeric, errors="coerce")
            if x_df.isna().all(axis=None):
                raise ValueError("所选特征列无法转换为有效数值。")
            x_df = x_df.fillna(x_df.median(numeric_only=True)).fillna(0.0)

            y_raw = self.df[self.target_column]
            valid_mask = y_raw.notna()
            if valid_mask.sum() < 4:
                raise ValueError("目标列有效样本过少，无法稳定训练。")

            y_valid = y_raw[valid_mask].astype(str)
            class_count = y_valid.nunique()
            if class_count < 2:
                raise ValueError("目标列至少需要两个类别。")
            if class_count > max(20, int(len(y_valid) * 0.5)):
                raise ValueError("目标列类别过多，不适合当前 SVM 分类。")

            encoder = LabelEncoder()
            y_encoded = encoder.fit_transform(y_valid)
            x_valid = x_df.loc[valid_mask].copy()

            if len(x_valid) != len(y_encoded):
                raise ValueError("特征与目标数据长度不一致。")

            steps = []
            if self.params["standardize"]:
                steps.append(("scaler", StandardScaler()))

            gamma_value = self.params["gamma"]
            svc = SVC(
                C=self.params["c_value"],
                kernel=self.params["kernel"],
                degree=self.params["degree"],
                gamma="scale" if gamma_value <= 0 else gamma_value,
                coef0=self.params["coef0"],
                probability=self.params["probability"],
                tol=self.params["tol"],
                cache_size=self.params["cache_size"],
            )
            steps.append(("svc", svc))
            model = Pipeline(steps)

            class_counts = pd.Series(y_encoded).value_counts()
            can_stratify = len(class_counts) > 1 and class_counts.min() >= 2

            if len(x_valid) >= 12:
                x_fit, x_test, y_fit, y_test = train_test_split(
                    x_valid,
                    y_encoded,
                    test_size=self.params["test_size"],
                    random_state=42,
                    stratify=y_encoded if can_stratify else None,
                )
                evaluation_mode = "留出验证"
            else:
                x_fit, x_test, y_fit, y_test = x_valid, x_valid, y_encoded, y_encoded
                evaluation_mode = "全样本评估"

            model.fit(x_fit, y_fit)
            y_pred_test = model.predict(x_test)
            accuracy = accuracy_score(y_test, y_pred_test)

            predicted_valid = model.predict(x_valid)
            predicted_labels = encoder.inverse_transform(predicted_valid)

            result_df = self.df.copy()
            result_df["SVM_Prediction"] = ""
            result_df.loc[valid_mask, "SVM_Prediction"] = predicted_labels

            if self.params["probability"]:
                proba = model.predict_proba(x_valid).max(axis=1)
                result_df["SVM_Confidence"] = pd.NA
                result_df.loc[valid_mask, "SVM_Confidence"] = proba

            result_df["SVM_IsCorrect"] = pd.NA
            result_df.loc[valid_mask, "SVM_IsCorrect"] = predicted_labels == y_valid.to_numpy()

            label_ids = sorted(pd.Series(y_encoded).unique().tolist())
            target_names = encoder.inverse_transform(np.array(label_ids))
            report_text = classification_report(
                y_test,
                y_pred_test,
                labels=label_ids,
                target_names=target_names,
                zero_division=0,
            )

            summary_lines = [
                "SVM 训练完成",
                f"验证方式：{evaluation_mode}",
                f"目标列：{self.target_column}",
                f"特征列数量：{len(self.feature_columns)}",
                f"核函数：{self.params['kernel']}",
                f"类别数量：{len(encoder.classes_)}",
                f"准确率：{accuracy:.4f}",
                "",
                "分类报告：",
                report_text,
            ]

            self.finished_ok.emit(
                {
                    "result_df": result_df,
                    "summary_text": "\n".join(summary_lines),
                    "model": model,
                    "label_encoder": encoder,
                }
            )
        except Exception as exc:
            self.failed.emit(str(exc))


class Win_ModelSVM(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.node = node
        self.df = pd.DataFrame()
        self.df_result = pd.DataFrame()
        self.numeric_columns = []
        self.feature_checkboxes = {}
        self.model = None
        self.label_encoder = None
        self.worker = None
        self._busy = False

        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("DataAnalysis [SVM]")
        self.resize(1040, 720)

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        left_widget = QWidget(self)
        left_widget.setMinimumWidth(420)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        info_group = QGroupBox("数据信息")
        info_layout = QVBoxLayout(info_group)
        self.label_info = QLabel("状态：请先加载数据。")
        self.label_info.setWordWrap(True)
        info_layout.addWidget(self.label_info)
        left_layout.addWidget(info_group)

        busy_group = QGroupBox("运行状态")
        busy_layout = QVBoxLayout(busy_group)
        self.label_busy = QLabel("当前空闲。")
        self.label_busy.setWordWrap(True)
        self.progress_busy = QProgressBar()
        self.progress_busy.setRange(0, 0)
        self.progress_busy.hide()
        busy_layout.addWidget(self.label_busy)
        busy_layout.addWidget(self.progress_busy)
        left_layout.addWidget(busy_group)

        target_group = QGroupBox("训练配置")
        target_layout = QFormLayout(target_group)
        target_layout.setLabelAlignment(Qt.AlignLeft)

        self.combo_target = QComboBox()
        target_layout.addRow("目标列", self.combo_target)

        self.spin_test_size = QDoubleSpinBox()
        self.spin_test_size.setRange(0.10, 0.50)
        self.spin_test_size.setSingleStep(0.05)
        self.spin_test_size.setValue(0.20)
        self.spin_test_size.setSuffix("  测试占比")
        target_layout.addRow("验证方式", self.spin_test_size)

        self.check_probability = QCheckBox("输出分类置信度")
        self.check_probability.setChecked(True)
        target_layout.addRow("", self.check_probability)

        self.check_standardize = QCheckBox("训练前进行标准化")
        self.check_standardize.setChecked(True)
        target_layout.addRow("", self.check_standardize)
        left_layout.addWidget(target_group)

        feature_group = QGroupBox("特征列选择")
        feature_layout = QVBoxLayout(feature_group)
        feature_toolbar = QHBoxLayout()
        self.btn_select_all = QPushButton("全选")
        self.btn_select_none = QPushButton("清空")
        feature_toolbar.addWidget(self.btn_select_all)
        feature_toolbar.addWidget(self.btn_select_none)
        feature_toolbar.addStretch(1)
        feature_layout.addLayout(feature_toolbar)

        self.feature_scroll = QScrollArea()
        self.feature_scroll.setWidgetResizable(True)
        self.feature_scroll_widget = QWidget()
        self.feature_scroll_layout = QVBoxLayout(self.feature_scroll_widget)
        self.feature_scroll_layout.setContentsMargins(8, 8, 8, 8)
        self.feature_scroll_layout.setSpacing(6)
        self.feature_scroll.setWidget(self.feature_scroll_widget)
        feature_layout.addWidget(self.feature_scroll)
        left_layout.addWidget(feature_group, 1)

        param_group = QGroupBox("模型参数")
        param_layout = QFormLayout(param_group)
        param_layout.setLabelAlignment(Qt.AlignLeft)

        self.combo_kernel = QComboBox()
        self.combo_kernel.addItems(["linear", "rbf", "poly", "sigmoid"])
        param_layout.addRow("核函数", self.combo_kernel)

        self.spin_c = QDoubleSpinBox()
        self.spin_c.setRange(0.01, 100000.0)
        self.spin_c.setDecimals(3)
        self.spin_c.setSingleStep(0.1)
        self.spin_c.setValue(1.0)
        param_layout.addRow("C", self.spin_c)

        self.spin_gamma = QDoubleSpinBox()
        self.spin_gamma.setRange(0.0, 10000.0)
        self.spin_gamma.setDecimals(4)
        self.spin_gamma.setSingleStep(0.01)
        self.spin_gamma.setValue(0.0)
        self.spin_gamma.setToolTip("设为 0 时使用 scale")
        param_layout.addRow("Gamma", self.spin_gamma)

        self.spin_degree = QSpinBox()
        self.spin_degree.setRange(1, 10)
        self.spin_degree.setValue(3)
        param_layout.addRow("Degree", self.spin_degree)

        self.spin_coef0 = QDoubleSpinBox()
        self.spin_coef0.setRange(-1000.0, 1000.0)
        self.spin_coef0.setDecimals(3)
        self.spin_coef0.setSingleStep(0.1)
        self.spin_coef0.setValue(1.0)
        param_layout.addRow("Coef0", self.spin_coef0)

        self.spin_tol = QDoubleSpinBox()
        self.spin_tol.setRange(0.0001, 1.0)
        self.spin_tol.setDecimals(4)
        self.spin_tol.setSingleStep(0.0005)
        self.spin_tol.setValue(0.0010)
        param_layout.addRow("Tolerance", self.spin_tol)

        self.spin_cache_size = QSpinBox()
        self.spin_cache_size.setRange(50, 4096)
        self.spin_cache_size.setValue(200)
        self.spin_cache_size.setSuffix(" MB")
        param_layout.addRow("Cache", self.spin_cache_size)
        left_layout.addWidget(param_group)

        button_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load")
        self.btn_calculate = QPushButton("Calculate")
        self.btn_translate = QPushButton("Transfer")
        self.btn_translate.setEnabled(False)
        button_layout.addWidget(self.btn_load)
        button_layout.addWidget(self.btn_calculate)
        button_layout.addStretch(1)
        button_layout.addWidget(self.btn_translate)
        left_layout.addLayout(button_layout)

        right_group = QGroupBox("模型结果")
        right_layout = QVBoxLayout(right_group)
        self.text_result = QTextBrowser()
        right_layout.addWidget(self.text_result)

        root_layout.addWidget(left_widget, 0)
        root_layout.addWidget(right_group, 1)

        self.btn_load.clicked.connect(self.on_Load)
        self.btn_calculate.clicked.connect(self.on_Create)
        self.btn_translate.clicked.connect(self.on_Transfer)
        self.btn_select_all.clicked.connect(lambda: self._set_feature_selection(True))
        self.btn_select_none.clicked.connect(lambda: self._set_feature_selection(False))
        self.combo_target.currentTextChanged.connect(self._sync_target_and_features)
        self.combo_kernel.currentTextChanged.connect(self._sync_kernel_fields)

        self._sync_kernel_fields()
        self._update_result_text("请先加载数据。")
        self._set_busy(False)

    def _update_result_text(self, text: str):
        self.text_result.setPlainText(text)

    def _is_numeric_candidate(self, series: pd.Series) -> bool:
        numeric_series = pd.to_numeric(series, errors="coerce")
        return numeric_series.notna().sum() > 0

    def _clear_feature_layout(self):
        while self.feature_scroll_layout.count():
            item = self.feature_scroll_layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                while child_layout.count():
                    child_item = child_layout.takeAt(0)
                    if child_item.widget() is not None:
                        child_item.widget().deleteLater()

    def _build_feature_selector(self):
        self._clear_feature_layout()
        self.feature_checkboxes.clear()

        for column in self.numeric_columns:
            checkbox = QCheckBox(str(column))
            checkbox.setChecked(True)
            self.feature_scroll_layout.addWidget(checkbox)
            self.feature_checkboxes[column] = checkbox

        self.feature_scroll_layout.addStretch(1)
        self._sync_target_and_features()

    def _set_feature_selection(self, checked: bool):
        target_column = self.combo_target.currentText()
        for column, checkbox in self.feature_checkboxes.items():
            checkbox.setChecked(checked and column != target_column)

    def _sync_target_and_features(self):
        target_column = self.combo_target.currentText()
        for column, checkbox in self.feature_checkboxes.items():
            if column == target_column:
                checkbox.setChecked(False)
                checkbox.setEnabled(False)
            else:
                checkbox.setEnabled(not self._busy)

    def _selected_feature_columns(self):
        return [column for column, checkbox in self.feature_checkboxes.items() if checkbox.isChecked()]

    def _sync_kernel_fields(self):
        kernel = self.combo_kernel.currentText()
        self.spin_degree.setEnabled((kernel == "poly") and not self._busy)
        self.spin_gamma.setEnabled((kernel in {"rbf", "poly", "sigmoid"}) and not self._busy)
        self.spin_coef0.setEnabled((kernel in {"poly", "sigmoid"}) and not self._busy)

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.progress_busy.setVisible(busy)
        self.btn_load.setEnabled(not busy)
        self.btn_calculate.setEnabled(not busy)
        self.btn_translate.setEnabled((not busy) and (not self.df_result.empty))
        self.btn_select_all.setEnabled(not busy)
        self.btn_select_none.setEnabled(not busy)
        self.combo_target.setEnabled(not busy)
        self.spin_test_size.setEnabled(not busy)
        self.check_probability.setEnabled(not busy)
        self.check_standardize.setEnabled(not busy)
        self.combo_kernel.setEnabled(not busy)
        self.spin_c.setEnabled(not busy)
        self.spin_tol.setEnabled(not busy)
        self.spin_cache_size.setEnabled(not busy)
        self._sync_kernel_fields()

        if busy:
            self.label_busy.setText("正在执行 SVM 训练，请稍候。窗口可响应，但计算尚未完成。")
        else:
            self.label_busy.setText("当前空闲。")

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
                QMessageBox.warning(self, "警告", "加载的数据为空，无法进行 SVM 分析。")
                return

            self.df = value.copy()
            self.numeric_columns = [col for col in self.df.columns if self._is_numeric_candidate(self.df[col])]
            if not self.numeric_columns:
                QMessageBox.warning(self, "警告", "未检测到可用数值列。")
                return

            self.combo_target.clear()
            self.combo_target.addItems([str(col) for col in self.df.columns])
            self._build_feature_selector()
            self._sync_kernel_fields()
            self.df_result = pd.DataFrame()
            self.btn_translate.setEnabled(False)

            self.label_info.setText(
                f"状态：已加载 {self.df.shape[0]} 行、{self.df.shape[1]} 列。"
                f"\n可用数值特征列：{len(self.numeric_columns)}"
            )
            self._update_result_text("数据已加载，请选择目标列和特征列后开始训练。")

            self.node.eval()
            QMessageBox.information(self, "成功", "SVM 数据加载完成。")
        except Exception as exc:
            self.node.markInvalid()
            QMessageBox.critical(self, "错误", f"SVM 数据加载失败：{exc}")

    def on_Create(self):
        if self._busy:
            QMessageBox.information(self, "提示", "当前正在计算，请等待本次任务完成。")
            return
        if self.df.empty:
            QMessageBox.warning(self, "警告", "请先加载数据。")
            return

        target_column = self.combo_target.currentText()
        if not target_column:
            QMessageBox.warning(self, "警告", "请选择目标列。")
            return

        feature_columns = self._selected_feature_columns()
        if not feature_columns:
            QMessageBox.warning(self, "警告", "请至少选择一列特征。")
            return

        params = {
            "test_size": self.spin_test_size.value(),
            "probability": self.check_probability.isChecked(),
            "standardize": self.check_standardize.isChecked(),
            "kernel": self.combo_kernel.currentText(),
            "c_value": self.spin_c.value(),
            "gamma": self.spin_gamma.value(),
            "degree": self.spin_degree.value(),
            "coef0": self.spin_coef0.value(),
            "tol": self.spin_tol.value(),
            "cache_size": self.spin_cache_size.value(),
        }

        self.worker = SVMWorker(self.df, target_column, feature_columns, params)
        self.worker.finished_ok.connect(self._on_worker_finished)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.finished.connect(self._on_worker_cleanup)

        self._set_busy(True)
        self._update_result_text("SVM 正在后台计算，请稍候...\n\n当前窗口不会未响应，你可以等待结果返回。")
        self.worker.start()

    def _on_worker_finished(self, payload):
        self.df_result = payload["result_df"]
        self.model = payload["model"]
        self.label_encoder = payload["label_encoder"]
        self._update_result_text(payload["summary_text"])

    def _on_worker_failed(self, message: str):
        self.df_result = pd.DataFrame()
        self._update_result_text("SVM 计算失败。\n\n" + message)
        QMessageBox.critical(self, "错误", f"SVM 计算失败：{message}")

    def _on_worker_cleanup(self):
        self.worker = None
        self._set_busy(False)

    def on_Transfer(self):
        if self._busy:
            QMessageBox.information(self, "提示", "当前正在计算，请等待本次任务完成。")
            return
        if self.df_result.empty:
            QMessageBox.warning(self, "警告", "请先完成计算。")
            return

        try:
            if self.node.LoadData(self.df_result):
                self.node.eval()
                self.node.evalChildren()
            QMessageBox.information(self, "提示", "SVM 结果已传递。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"SVM 结果传递失败：{exc}")
