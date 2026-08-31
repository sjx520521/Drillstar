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
from sklearn.naive_bayes import GaussianNB, MultinomialNB, BernoulliNB, ComplementNB
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, MinMaxScaler, StandardScaler

from dataanalysis.buttonNode import ButtonNode
from dataanalysis.model.model_artifact import build_model_artifact


class NaiveBayesWorker(QThread):
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
            if y_valid.nunique() < 2:
                raise ValueError("目标列至少需要两个类别。")

            encoder = LabelEncoder()
            y_encoded = encoder.fit_transform(y_valid)
            x_valid = x_df.loc[valid_mask].copy()

            model_type = self.params["model_type"]
            var_smoothing = self.params["var_smoothing"]
            alpha = self.params["alpha"]

            scaler = None
            extra = {}
            if model_type in {"Multinomial", "Complement", "Bernoulli"}:
                scaler = MinMaxScaler()
                x_values = scaler.fit_transform(x_valid)
                if model_type == "Bernoulli":
                    x_values = (x_values > 0.5).astype(float)
                    extra["binarize_threshold"] = 0.5
            else:
                if self.params["standardize"]:
                    scaler = StandardScaler()
                    x_values = scaler.fit_transform(x_valid)
                else:
                    x_values = x_valid.to_numpy()

            if model_type == "Gaussian":
                model = GaussianNB(var_smoothing=var_smoothing)
            elif model_type == "Multinomial":
                model = MultinomialNB(alpha=alpha)
            elif model_type == "Bernoulli":
                model = BernoulliNB(alpha=alpha)
            else:
                model = ComplementNB(alpha=alpha)

            class_counts = pd.Series(y_encoded).value_counts()
            can_stratify = class_counts.min() >= 2

            if len(x_valid) >= 12:
                x_fit, x_test, y_fit, y_test = train_test_split(
                    x_values, y_encoded,
                    test_size=self.params["test_size"],
                    random_state=42,
                    stratify=y_encoded if can_stratify else None,
                )
                evaluation_mode = "留出验证"
            else:
                x_fit, x_test, y_fit, y_test = x_values, x_values, y_encoded, y_encoded
                evaluation_mode = "全样本评估"

            model.fit(x_fit, y_fit)
            y_pred_test = model.predict(x_test)
            accuracy = accuracy_score(y_test, y_pred_test)

            predicted_valid = model.predict(x_values)
            predicted_labels = encoder.inverse_transform(predicted_valid)

            result_df = self.df.copy()
            result_df["NB_Prediction"] = ""
            result_df.loc[valid_mask, "NB_Prediction"] = predicted_labels

            proba = model.predict_proba(x_values).max(axis=1)
            result_df["NB_Confidence"] = pd.NA
            result_df.loc[valid_mask, "NB_Confidence"] = proba

            result_df["NB_IsCorrect"] = pd.NA
            result_df.loc[valid_mask, "NB_IsCorrect"] = predicted_labels == y_valid.to_numpy()

            label_ids = sorted(pd.Series(y_encoded).unique().tolist())
            target_names = encoder.inverse_transform(np.array(label_ids))
            report_text = classification_report(
                y_test, y_pred_test,
                labels=label_ids,
                target_names=target_names,
                zero_division=0,
            )

            summary_lines = [
                "朴素贝叶斯训练完成",
                f"验证方式：{evaluation_mode}",
                f"模型类型：{model_type}NB",
                f"目标列：{self.target_column}",
                f"特征列数量：{len(self.feature_columns)}",
                f"类别数量：{len(encoder.classes_)}",
                f"准确率：{accuracy:.4f}",
                "",
                "分类报告：",
                report_text,
            ]

            self.finished_ok.emit({
                "result_df": result_df,
                "summary_text": "\n".join(summary_lines),
                "model": model,
                "label_encoder": encoder,
                "preprocessor": scaler,
                "extra": extra,
            })
        except Exception as exc:
            self.failed.emit(str(exc))


class Win_ModelNaiveBayes(QWidget):
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
        self.setWindowTitle("DataAnalysis [Naive Bayes]")
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

        self.check_standardize = QCheckBox("Gaussian 模式下标准化")
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

        self.combo_model_type = QComboBox()
        self.combo_model_type.addItems(["Gaussian", "Multinomial", "Bernoulli", "Complement"])
        self.combo_model_type.currentTextChanged.connect(self._sync_model_fields)
        param_layout.addRow("模型类型", self.combo_model_type)

        self.spin_var_smoothing = QDoubleSpinBox()
        self.spin_var_smoothing.setRange(1e-12, 1.0)
        self.spin_var_smoothing.setDecimals(10)
        self.spin_var_smoothing.setSingleStep(1e-9)
        self.spin_var_smoothing.setValue(1e-9)
        param_layout.addRow("Var Smoothing（Gaussian）", self.spin_var_smoothing)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.0, 100.0)
        self.spin_alpha.setDecimals(4)
        self.spin_alpha.setSingleStep(0.1)
        self.spin_alpha.setValue(1.0)
        param_layout.addRow("Alpha（平滑参数）", self.spin_alpha)
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

        self._sync_model_fields()
        self._update_result_text("请先加载数据。")
        self._set_busy(False)

    def _update_result_text(self, text: str):
        self.text_result.setPlainText(text)

    def _is_numeric_candidate(self, series: pd.Series) -> bool:
        return pd.to_numeric(series, errors="coerce").notna().sum() > 0

    def _sync_model_fields(self):
        model_type = self.combo_model_type.currentText()
        self.spin_var_smoothing.setEnabled((model_type == "Gaussian") and not self._busy)
        self.spin_alpha.setEnabled((model_type != "Gaussian") and not self._busy)
        self.check_standardize.setEnabled((model_type == "Gaussian") and not self._busy)

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
        return [col for col, cb in self.feature_checkboxes.items() if cb.isChecked()]

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
        self.combo_model_type.setEnabled(not busy)
        self._sync_model_fields()
        self.label_busy.setText("正在执行朴素贝叶斯训练，请稍候。" if busy else "当前空闲。")

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
                QMessageBox.warning(self, "警告", "加载的数据为空，无法进行朴素贝叶斯分析。")
                return
            self.df = value.copy()
            self.numeric_columns = [col for col in self.df.columns if self._is_numeric_candidate(self.df[col])]
            if not self.numeric_columns:
                QMessageBox.warning(self, "警告", "未检测到可用数值列。")
                return
            self.combo_target.clear()
            self.combo_target.addItems([str(col) for col in self.df.columns])
            self._build_feature_selector()
            self.df_result = pd.DataFrame()
            self.btn_translate.setEnabled(False)
            self.label_info.setText(
                f"状态：已加载 {self.df.shape[0]} 行、{self.df.shape[1]} 列。"
                f"\n可用数值特征列：{len(self.numeric_columns)}"
            )
            self._update_result_text("数据已加载，请选择目标列和特征列后开始训练。")
            self.node.eval()
            QMessageBox.information(self, "成功", "朴素贝叶斯数据加载完成。")
        except Exception as exc:
            self.node.markInvalid()
            QMessageBox.critical(self, "错误", f"朴素贝叶斯数据加载失败：{exc}")

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
            "standardize": self.check_standardize.isChecked(),
            "model_type": self.combo_model_type.currentText(),
            "var_smoothing": self.spin_var_smoothing.value(),
            "alpha": self.spin_alpha.value(),
        }

        self.worker = NaiveBayesWorker(self.df, target_column, feature_columns, params)
        self.worker.finished_ok.connect(self._on_worker_finished)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.finished.connect(self._on_worker_cleanup)
        self._set_busy(True)
        self._update_result_text("朴素贝叶斯正在后台计算，请稍候...")
        self.worker.start()

    def _on_worker_finished(self, payload):
        self.df_result = payload["result_df"]
        self.model = payload["model"]
        self.label_encoder = payload["label_encoder"]
        self.preprocessor = payload.get("preprocessor")
        self.feature_columns = list(self.worker.feature_columns) if self.worker is not None else []
        self.target_column = self.worker.target_column if self.worker is not None else None
        self.params = dict(self.worker.params) if self.worker is not None else {}
        self.model_artifact = build_model_artifact(
            model_name="NaiveBayes",
            model=self.model,
            task_type="classification",
            feature_columns=self.feature_columns,
            target_column=self.target_column,
            params=self.params,
            label_encoder=self.label_encoder,
            preprocessor=self.preprocessor,
            output_prefix="NB",
            extra=payload.get("extra"),
        )
        self._update_result_text(payload["summary_text"])

    def _on_worker_failed(self, message: str):
        self.df_result = pd.DataFrame()
        self._update_result_text("朴素贝叶斯计算失败。\n\n" + message)
        QMessageBox.critical(self, "错误", f"朴素贝叶斯计算失败：{message}")

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
            QMessageBox.information(self, "提示", "朴素贝叶斯结果已传递。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"朴素贝叶斯结果传递失败：{exc}")
