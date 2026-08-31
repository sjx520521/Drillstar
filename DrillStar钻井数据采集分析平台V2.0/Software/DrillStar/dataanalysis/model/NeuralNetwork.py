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
from sklearn.metrics import accuracy_score, classification_report, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

from dataanalysis.buttonNode import ButtonNode
from dataanalysis.model.model_artifact import build_model_artifact
from dataanalysis.model.plot_widgets import ModelPlotWidget


class NeuralNetworkWorker(QThread):
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

            x_valid = x_df.loc[valid_mask].copy()
            task = self.params["task"]

            hidden_layer_str = self.params["hidden_layers"]
            try:
                hidden_layers = tuple(int(x.strip()) for x in hidden_layer_str.split(",") if x.strip())
                if not hidden_layers:
                    raise ValueError()
            except Exception:
                raise ValueError("隐藏层格式错误，请用逗号分隔整数，例如：128,64,32")

            steps = [("scaler", StandardScaler())]

            if task == "分类":
                y_valid = y_raw[valid_mask].astype(str)
                if y_valid.nunique() < 2:
                    raise ValueError("目标列至少需要两个类别。")
                encoder = LabelEncoder()
                y_encoded = encoder.fit_transform(y_valid)

                mlp = MLPClassifier(
                    hidden_layer_sizes=hidden_layers,
                    activation=self.params["activation"],
                    solver=self.params["solver"],
                    alpha=self.params["alpha"],
                    learning_rate_init=self.params["learning_rate_init"],
                    max_iter=self.params["max_iter"],
                    random_state=42,
                    early_stopping=self.params["early_stopping"],
                )
                steps.append(("mlp", mlp))
                model = Pipeline(steps)

                class_counts = pd.Series(y_encoded).value_counts()
                can_stratify = class_counts.min() >= 2
                if len(x_valid) >= 12:
                    x_fit, x_test, y_fit, y_test = train_test_split(
                        x_valid, y_encoded,
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
                result_df["NN_Prediction"] = ""
                result_df.loc[valid_mask, "NN_Prediction"] = predicted_labels

                proba = model.predict_proba(x_valid).max(axis=1)
                result_df["NN_Confidence"] = pd.NA
                result_df.loc[valid_mask, "NN_Confidence"] = proba

                result_df["NN_IsCorrect"] = pd.NA
                result_df.loc[valid_mask, "NN_IsCorrect"] = predicted_labels == y_valid.to_numpy()

                label_ids = sorted(pd.Series(y_encoded).unique().tolist())
                target_names = encoder.inverse_transform(np.array(label_ids))
                report_text = classification_report(
                    y_test, y_pred_test,
                    labels=label_ids,
                    target_names=target_names,
                    zero_division=0,
                )
                summary_lines = [
                    "神经网络（MLP）分类训练完成",
                    f"验证方式：{evaluation_mode}",
                    f"目标列：{self.target_column}",
                    f"特征列数量：{len(self.feature_columns)}",
                    f"隐藏层结构：{hidden_layers}",
                    f"激活函数：{self.params['activation']}",
                    f"类别数量：{len(encoder.classes_)}",
                    f"准确率：{accuracy:.4f}",
                    "",
                    "分类报告：",
                    report_text,
                ]
                payload_extra = {"label_encoder": encoder}

            else:
                y_raw_num = pd.to_numeric(y_raw[valid_mask], errors="coerce")
                valid_mask2 = y_raw_num.notna()
                y_values = y_raw_num[valid_mask2].to_numpy()
                x_values_reg = x_valid.loc[valid_mask2].copy()

                mlp = MLPRegressor(
                    hidden_layer_sizes=hidden_layers,
                    activation=self.params["activation"],
                    solver=self.params["solver"],
                    alpha=self.params["alpha"],
                    learning_rate_init=self.params["learning_rate_init"],
                    max_iter=self.params["max_iter"],
                    random_state=42,
                    early_stopping=self.params["early_stopping"],
                )
                steps.append(("mlp", mlp))
                model = Pipeline(steps)

                if len(x_values_reg) >= 12:
                    x_fit, x_test, y_fit, y_test = train_test_split(
                        x_values_reg, y_values,
                        test_size=self.params["test_size"],
                        random_state=42,
                    )
                    evaluation_mode = "留出验证"
                else:
                    x_fit, x_test, y_fit, y_test = x_values_reg, x_values_reg, y_values, y_values
                    evaluation_mode = "全样本评估"

                model.fit(x_fit, y_fit)
                y_pred_test = model.predict(x_test)
                rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
                r2 = r2_score(y_test, y_pred_test)

                predicted_valid = model.predict(x_values_reg)
                result_df = self.df.copy()
                result_df["NN_Prediction"] = np.nan
                result_df.loc[valid_mask2.index[valid_mask2], "NN_Prediction"] = predicted_valid
                result_df["NN_Residual"] = np.nan
                result_df.loc[valid_mask2.index[valid_mask2], "NN_Residual"] = y_values - predicted_valid

                summary_lines = [
                    "神经网络（MLP）回归训练完成",
                    f"验证方式：{evaluation_mode}",
                    f"目标列：{self.target_column}",
                    f"特征列数量：{len(self.feature_columns)}",
                    f"隐藏层结构：{hidden_layers}",
                    f"激活函数：{self.params['activation']}",
                    f"RMSE：{rmse:.4f}",
                    f"R²：{r2:.4f}",
                ]
                payload_extra = {"label_encoder": None}
                encoder = None

            self.finished_ok.emit({
                "result_df": result_df,
                "summary_text": "\n".join(summary_lines),
                "model": model,
                **payload_extra,
            })
        except Exception as exc:
            self.failed.emit(str(exc))


class Win_ModelNeuralNetwork(QWidget):
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
        self.setWindowTitle("DataAnalysis [Neural Network]")
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

        self.combo_task = QComboBox()
        self.combo_task.addItems(["分类", "回归"])
        target_layout.addRow("任务类型", self.combo_task)

        self.spin_test_size = QDoubleSpinBox()
        self.spin_test_size.setRange(0.10, 0.50)
        self.spin_test_size.setSingleStep(0.05)
        self.spin_test_size.setValue(0.20)
        self.spin_test_size.setSuffix("  测试占比")
        target_layout.addRow("验证方式", self.spin_test_size)
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

        from PyQt5.QtWidgets import QLineEdit
        self.edit_hidden_layers = QLineEdit("128,64")
        self.edit_hidden_layers.setToolTip("用逗号分隔各层神经元数，例如：128,64,32")
        param_layout.addRow("隐藏层结构", self.edit_hidden_layers)

        self.combo_activation = QComboBox()
        self.combo_activation.addItems(["relu", "tanh", "logistic", "identity"])
        param_layout.addRow("激活函数", self.combo_activation)

        self.combo_solver = QComboBox()
        self.combo_solver.addItems(["adam", "sgd", "lbfgs"])
        param_layout.addRow("优化器", self.combo_solver)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.0001, 10.0)
        self.spin_alpha.setDecimals(4)
        self.spin_alpha.setSingleStep(0.0001)
        self.spin_alpha.setValue(0.0001)
        param_layout.addRow("L2 正则（Alpha）", self.spin_alpha)

        self.spin_learning_rate = QDoubleSpinBox()
        self.spin_learning_rate.setRange(0.0001, 1.0)
        self.spin_learning_rate.setDecimals(4)
        self.spin_learning_rate.setSingleStep(0.001)
        self.spin_learning_rate.setValue(0.001)
        param_layout.addRow("学习率", self.spin_learning_rate)

        self.spin_max_iter = QSpinBox()
        self.spin_max_iter.setRange(50, 10000)
        self.spin_max_iter.setValue(500)
        param_layout.addRow("最大迭代次数", self.spin_max_iter)

        self.check_early_stopping = QCheckBox("启用早停")
        self.check_early_stopping.setChecked(True)
        param_layout.addRow("", self.check_early_stopping)
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
        self.plot_widget = ModelPlotWidget()
        right_layout.addWidget(self.plot_widget)
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

        self._update_result_text("请先加载数据。")
        self._set_busy(False)

    def _update_result_text(self, text: str):
        self.text_result.setPlainText(text)

    def _is_numeric_candidate(self, series: pd.Series) -> bool:
        return pd.to_numeric(series, errors="coerce").notna().sum() > 0

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
        self.combo_task.setEnabled(not busy)
        self.spin_test_size.setEnabled(not busy)
        self.combo_activation.setEnabled(not busy)
        self.combo_solver.setEnabled(not busy)
        self.spin_alpha.setEnabled(not busy)
        self.spin_learning_rate.setEnabled(not busy)
        self.spin_max_iter.setEnabled(not busy)
        self.check_early_stopping.setEnabled(not busy)
        self.label_busy.setText("正在执行神经网络训练，请稍候。" if busy else "当前空闲。")

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
                QMessageBox.warning(self, "警告", "加载的数据为空，无法进行神经网络分析。")
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
            self.plot_widget.clear("Run the neural network to show the chart.")
            self.btn_translate.setEnabled(False)
            self.label_info.setText(
                f"状态：已加载 {self.df.shape[0]} 行、{self.df.shape[1]} 列。"
                f"\n可用数值特征列：{len(self.numeric_columns)}"
            )
            self._update_result_text("数据已加载，请选择目标列和特征列后开始训练。")
            self.node.eval()
            QMessageBox.information(self, "成功", "神经网络数据加载完成。")
        except Exception as exc:
            self.node.markInvalid()
            QMessageBox.critical(self, "错误", f"神经网络数据加载失败：{exc}")

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
            "task": self.combo_task.currentText(),
            "test_size": self.spin_test_size.value(),
            "hidden_layers": self.edit_hidden_layers.text(),
            "activation": self.combo_activation.currentText(),
            "solver": self.combo_solver.currentText(),
            "alpha": self.spin_alpha.value(),
            "learning_rate_init": self.spin_learning_rate.value(),
            "max_iter": self.spin_max_iter.value(),
            "early_stopping": self.check_early_stopping.isChecked(),
        }

        self.worker = NeuralNetworkWorker(self.df, target_column, feature_columns, params)
        self.worker.finished_ok.connect(self._on_worker_finished)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.finished.connect(self._on_worker_cleanup)
        self._set_busy(True)
        self._update_result_text("神经网络正在后台训练，请稍候...")
        self.worker.start()

    def _on_worker_finished(self, payload):
        self.df_result = payload["result_df"]
        self.model = payload["model"]
        self.label_encoder = payload.get("label_encoder")
        self.feature_columns = list(self.worker.feature_columns) if self.worker is not None else []
        self.target_column = self.worker.target_column if self.worker is not None else None
        self.params = dict(self.worker.params) if self.worker is not None else {}
        self.model_artifact = build_model_artifact(
            model_name="NeuralNetwork",
            model=self.model,
            task_type="classification" if self.label_encoder is not None else "regression",
            feature_columns=self.feature_columns,
            target_column=self.target_column,
            params=self.params,
            label_encoder=self.label_encoder,
            output_prefix="NN",
        )
        if self.label_encoder is None:
            self.plot_widget.plot_regression(
                self.df_result,
                self.target_column,
                "NN_Prediction",
                "NN_Residual",
            )
        else:
            self.plot_widget.clear("Classification results are shown in the report.")
        self._update_result_text(payload["summary_text"])

    def _on_worker_failed(self, message: str):
        self.df_result = pd.DataFrame()
        self.plot_widget.clear("Neural network failed.")
        self._update_result_text("神经网络计算失败。\n\n" + message)
        QMessageBox.critical(self, "错误", f"神经网络计算失败：{message}")

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
            QMessageBox.information(self, "提示", "神经网络结果已传递。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"神经网络结果传递失败：{exc}")
