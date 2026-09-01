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
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from dataanalysis.buttonNode import ButtonNode


class KMeansWorker(QThread):
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, df, feature_columns, params):
        super().__init__()
        self.df = df.copy()
        self.feature_columns = list(feature_columns)
        self.params = dict(params)

    def run(self):
        try:
            x_df = self.df[self.feature_columns].apply(pd.to_numeric, errors="coerce")
            if x_df.isna().all(axis=None):
                raise ValueError("所选特征列无法转换为有效数值。")
            x_df = x_df.fillna(x_df.median(numeric_only=True)).fillna(0.0)

            n_clusters = self.params["n_clusters"]
            if len(x_df) <= n_clusters:
                raise ValueError("样本数必须大于聚类数。")

            x_values = x_df.to_numpy()
            if self.params["standardize"]:
                x_values = StandardScaler().fit_transform(x_values)

            random_state = self.params["random_state"]
            model = KMeans(
                n_clusters=n_clusters,
                init=self.params["init_method"],
                n_init=self.params["n_init"],
                max_iter=self.params["max_iter"],
                tol=self.params["tol"],
                random_state=random_state if random_state > 0 else None,
            )

            labels = model.fit_predict(x_values)
            distances = model.transform(x_values).min(axis=1)

            silhouette = silhouette_score(x_values, labels) if n_clusters >= 2 else float("nan")
            davies = davies_bouldin_score(x_values, labels) if n_clusters >= 2 else float("nan")
            cluster_sizes = pd.Series(labels).value_counts().sort_index()

            result_df = self.df.copy()
            result_df["KMeans_Cluster"] = labels
            result_df["KMeans_Distance"] = distances

            center_df = pd.DataFrame(model.cluster_centers_, columns=self.feature_columns)
            center_df.index = [f"Cluster_{idx}" for idx in range(len(center_df))]

            summary_lines = [
                "K-Means 聚类完成",
                f"特征列数量：{len(self.feature_columns)}",
                f"聚类数：{n_clusters}",
                f"惯性 Inertia：{model.inertia_:.4f}",
                f"Silhouette：{silhouette:.4f}",
                f"Davies-Bouldin：{davies:.4f}",
                "",
                "各簇样本数：",
            ]
            for cluster_id, size in cluster_sizes.items():
                summary_lines.append(f"Cluster {cluster_id}: {size}")

            summary_lines.extend(
                [
                    "",
                    "聚类中心：",
                    center_df.round(4).to_string(),
                ]
            )

            self.finished_ok.emit(
                {
                    "result_df": result_df,
                    "summary_text": "\n".join(summary_lines),
                    "model": model,
                }
            )
        except Exception as exc:
            self.failed.emit(str(exc))


class Win_ModelKmeans(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.node = node
        self.df = pd.DataFrame()
        self.df_result = pd.DataFrame()
        self.numeric_columns = []
        self.feature_checkboxes = {}
        self.model = None
        self.worker = None
        self._busy = False

        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("DataAnalysis [K-Means]")
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

        param_group = QGroupBox("聚类参数")
        param_layout = QFormLayout(param_group)
        param_layout.setLabelAlignment(Qt.AlignLeft)

        self.spin_n_clusters = QSpinBox()
        self.spin_n_clusters.setRange(2, 100)
        self.spin_n_clusters.setValue(3)
        param_layout.addRow("聚类数", self.spin_n_clusters)

        self.combo_init = QComboBox()
        self.combo_init.addItems(["k-means++", "random"])
        param_layout.addRow("初始化方式", self.combo_init)

        self.spin_n_init = QSpinBox()
        self.spin_n_init.setRange(1, 100)
        self.spin_n_init.setValue(10)
        param_layout.addRow("重复初始化", self.spin_n_init)

        self.spin_max_iter = QSpinBox()
        self.spin_max_iter.setRange(10, 10000)
        self.spin_max_iter.setValue(300)
        param_layout.addRow("最大迭代次数", self.spin_max_iter)

        self.spin_tol = QDoubleSpinBox()
        self.spin_tol.setRange(0.0001, 1.0)
        self.spin_tol.setDecimals(4)
        self.spin_tol.setSingleStep(0.0005)
        self.spin_tol.setValue(0.0010)
        param_layout.addRow("Tolerance", self.spin_tol)

        self.spin_random_state = QSpinBox()
        self.spin_random_state.setRange(0, 999999)
        self.spin_random_state.setValue(42)
        param_layout.addRow("随机种子", self.spin_random_state)

        self.check_standardize = QCheckBox("聚类前进行标准化")
        self.check_standardize.setChecked(True)
        param_layout.addRow("", self.check_standardize)
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

        right_group = QGroupBox("聚类结果")
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

    def _set_feature_selection(self, checked: bool):
        for checkbox in self.feature_checkboxes.values():
            checkbox.setChecked(checked)

    def _selected_feature_columns(self):
        return [column for column, checkbox in self.feature_checkboxes.items() if checkbox.isChecked()]

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.progress_busy.setVisible(busy)
        self.btn_load.setEnabled(not busy)
        self.btn_calculate.setEnabled(not busy)
        self.btn_translate.setEnabled((not busy) and (not self.df_result.empty))
        self.btn_select_all.setEnabled(not busy)
        self.btn_select_none.setEnabled(not busy)
        self.spin_n_clusters.setEnabled(not busy)
        self.combo_init.setEnabled(not busy)
        self.spin_n_init.setEnabled(not busy)
        self.spin_max_iter.setEnabled(not busy)
        self.spin_tol.setEnabled(not busy)
        self.spin_random_state.setEnabled(not busy)
        self.check_standardize.setEnabled(not busy)
        for checkbox in self.feature_checkboxes.values():
            checkbox.setEnabled(not busy)

        if busy:
            self.label_busy.setText("正在执行 K-Means 聚类，请稍候。窗口可响应，但计算尚未完成。")
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
                QMessageBox.warning(self, "警告", "加载的数据为空，无法进行 K-Means 分析。")
                return

            self.df = value.copy()
            self.numeric_columns = [col for col in self.df.columns if self._is_numeric_candidate(self.df[col])]
            if not self.numeric_columns:
                QMessageBox.warning(self, "警告", "未检测到可用数值列。")
                return

            self._build_feature_selector()
            self.spin_n_clusters.setMaximum(max(2, min(100, len(self.df) - 1)))
            if self.spin_n_clusters.value() >= len(self.df):
                self.spin_n_clusters.setValue(max(2, min(3, len(self.df) - 1)))
            self.df_result = pd.DataFrame()
            self.btn_translate.setEnabled(False)
            self.label_info.setText(
                f"状态：已加载 {self.df.shape[0]} 行、{self.df.shape[1]} 列。"
                f"\n可用数值特征列：{len(self.numeric_columns)}"
            )
            self._update_result_text("数据已加载，请选择特征列并设置聚类参数。")

            self.node.eval()
            QMessageBox.information(self, "成功", "K-Means 数据加载完成。")
        except Exception as exc:
            self.node.markInvalid()
            QMessageBox.critical(self, "错误", f"K-Means 数据加载失败：{exc}")

    def on_Create(self):
        if self._busy:
            QMessageBox.information(self, "提示", "当前正在计算，请等待本次任务完成。")
            return
        if self.df.empty:
            QMessageBox.warning(self, "警告", "请先加载数据。")
            return

        feature_columns = self._selected_feature_columns()
        if not feature_columns:
            QMessageBox.warning(self, "警告", "请至少选择一列特征。")
            return

        params = {
            "n_clusters": self.spin_n_clusters.value(),
            "init_method": self.combo_init.currentText(),
            "n_init": self.spin_n_init.value(),
            "max_iter": self.spin_max_iter.value(),
            "tol": self.spin_tol.value(),
            "random_state": self.spin_random_state.value(),
            "standardize": self.check_standardize.isChecked(),
        }

        self.worker = KMeansWorker(self.df, feature_columns, params)
        self.worker.finished_ok.connect(self._on_worker_finished)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.finished.connect(self._on_worker_cleanup)

        self._set_busy(True)
        self._update_result_text("K-Means 正在后台计算，请稍候...\n\n当前窗口不会未响应，你可以等待结果返回。")
        self.worker.start()

    def _on_worker_finished(self, payload):
        self.df_result = payload["result_df"]
        self.model = payload["model"]
        self._update_result_text(payload["summary_text"])

    def _on_worker_failed(self, message: str):
        self.df_result = pd.DataFrame()
        self._update_result_text("K-Means 计算失败。\n\n" + message)
        QMessageBox.critical(self, "错误", f"K-Means 计算失败：{message}")

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
            QMessageBox.information(self, "提示", "K-Means 结果已传递。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"K-Means 结果传递失败：{exc}")
