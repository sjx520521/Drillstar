import math
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
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

from dataanalysis.buttonNode import ButtonNode
from dataanalysis.model.plot_widgets import ModelPlotWidget

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False


def _build_sequences(x: np.ndarray, y: np.ndarray, seq_len: int):
    xs, ys = [], []
    for i in range(len(x) - seq_len):
        xs.append(x[i: i + seq_len])
        ys.append(y[i + seq_len])
    return np.array(xs, dtype=np.float32), np.array(ys, dtype=np.float32)


if _TORCH_AVAILABLE:
    class _PositionalEncoding(nn.Module):
        def __init__(self, d_model: int, max_len: int = 500, dropout: float = 0.1):
            super().__init__()
            self.dropout = nn.Dropout(dropout)
            pe = torch.zeros(max_len, d_model)
            position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
            div_term = torch.exp(
                torch.arange(0, d_model, 2, dtype=torch.float) * (-math.log(10000.0) / d_model)
            )
            pe[:, 0::2] = torch.sin(position * div_term)
            if d_model % 2 == 1:
                pe[:, 1::2] = torch.cos(position * div_term[: d_model // 2])
            else:
                pe[:, 1::2] = torch.cos(position * div_term)
            self.register_buffer("pe", pe.unsqueeze(0))

        def forward(self, x):
            x = x + self.pe[:, : x.size(1)]
            return self.dropout(x)

    class _InformerNet(nn.Module):
        def __init__(self, input_size, d_model, nhead, num_encoder_layers, dim_feedforward, dropout):
            super().__init__()
            self.input_proj = nn.Linear(input_size, d_model)
            self.pos_enc = _PositionalEncoding(d_model, dropout=dropout)
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=dim_feedforward,
                dropout=dropout,
                batch_first=True,
            )
            self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_encoder_layers)
            self.fc = nn.Linear(d_model, 1)

        def forward(self, x):
            x = self.pos_enc(self.input_proj(x))
            x = self.encoder(x)
            return self.fc(x[:, -1, :])


class InformerWorker(QThread):
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, df, target_column, feature_columns, params):
        super().__init__()
        self.df = df.copy()
        self.target_column = target_column
        self.feature_columns = list(feature_columns)
        self.params = dict(params)

    def run(self):
        if not _TORCH_AVAILABLE:
            self.failed.emit("Informer 需要 PyTorch，请先安装：pip install torch")
            return
        try:
            import torch
            import torch.nn as nn
            from torch.utils.data import DataLoader, TensorDataset

            x_df = self.df[self.feature_columns].apply(pd.to_numeric, errors="coerce")
            if x_df.isna().all(axis=None):
                raise ValueError("所选特征列无法转换为有效数值。")
            x_df = x_df.fillna(x_df.median(numeric_only=True)).fillna(0.0)

            y_raw = pd.to_numeric(self.df[self.target_column], errors="coerce")
            valid_mask = y_raw.notna()
            if valid_mask.sum() < 10:
                raise ValueError("有效样本过少（至少需要10条），无法构建序列。")

            x_arr = x_df.loc[valid_mask].to_numpy(dtype=np.float32)
            y_arr = y_raw[valid_mask].to_numpy(dtype=np.float32)

            x_scaler = StandardScaler()
            y_scaler = StandardScaler()
            x_scaled = x_scaler.fit_transform(x_arr)
            y_scaled = y_scaler.fit_transform(y_arr.reshape(-1, 1)).ravel()

            seq_len = self.params["seq_len"]
            if len(x_scaled) <= seq_len:
                raise ValueError(f"样本数（{len(x_scaled)}）必须大于序列长度（{seq_len}）。")

            xs, ys = _build_sequences(x_scaled, y_scaled, seq_len)
            split = max(1, int(len(xs) * (1 - self.params["test_ratio"])))
            x_train, x_test = xs[:split], xs[split:]
            y_train, y_test = ys[:split], ys[split:]

            d_model = self.params["d_model"]
            nhead = self.params["nhead"]
            if d_model % nhead != 0:
                nhead = 1
                while nhead * 2 <= d_model:
                    nhead *= 2

            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            train_ds = TensorDataset(torch.from_numpy(x_train), torch.from_numpy(y_train))
            train_loader = DataLoader(train_ds, batch_size=self.params["batch_size"], shuffle=True)

            model = _InformerNet(
                input_size=x_scaled.shape[1],
                d_model=d_model,
                nhead=nhead,
                num_encoder_layers=self.params["num_layers"],
                dim_feedforward=self.params["dim_feedforward"],
                dropout=self.params["dropout"],
            ).to(device)

            optimizer = torch.optim.Adam(model.parameters(), lr=self.params["lr"])
            criterion = nn.MSELoss()

            for _ in range(self.params["epochs"]):
                model.train()
                for xb, yb in train_loader:
                    xb, yb = xb.to(device), yb.to(device)
                    optimizer.zero_grad()
                    loss = criterion(model(xb).squeeze(), yb)
                    loss.backward()
                    optimizer.step()

            model.eval()
            with torch.no_grad():
                x_test_t = torch.from_numpy(x_test).to(device)
                y_pred_scaled = model(x_test_t).squeeze().cpu().numpy()

            y_pred = y_scaler.inverse_transform(y_pred_scaled.reshape(-1, 1)).ravel()
            y_true = y_scaler.inverse_transform(y_test.reshape(-1, 1)).ravel()

            rmse = np.sqrt(mean_squared_error(y_true, y_pred))
            mae = mean_absolute_error(y_true, y_pred)
            r2 = r2_score(y_true, y_pred)

            with torch.no_grad():
                x_all_t = torch.from_numpy(xs).to(device)
                y_all_pred_scaled = model(x_all_t).squeeze().cpu().numpy()
            y_all_pred = y_scaler.inverse_transform(y_all_pred_scaled.reshape(-1, 1)).ravel()

            valid_indices = y_raw[valid_mask].index.tolist()
            pred_indices = valid_indices[seq_len:]

            result_df = self.df.copy()
            result_df["Informer_Prediction"] = np.nan
            result_df.loc[pred_indices, "Informer_Prediction"] = y_all_pred

            summary_lines = [
                "Informer（Transformer-based）时序预测完成",
                f"目标列：{self.target_column}",
                f"特征列数量：{len(self.feature_columns)}",
                f"序列长度：{seq_len}",
                f"d_model：{d_model}  注意力头数：{nhead}  编码层数：{self.params['num_layers']}",
                f"训练轮次：{self.params['epochs']}",
                f"测试集 RMSE：{rmse:.4f}",
                f"测试集 MAE：{mae:.4f}",
                f"测试集 R²：{r2:.4f}",
            ]

            self.finished_ok.emit({
                "result_df": result_df,
                "summary_text": "\n".join(summary_lines),
                "model": model,
            })
        except Exception as exc:
            self.failed.emit(str(exc))


class Win_ModelInformer(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.node = node
        self.df = pd.DataFrame()
        self.df_result = pd.DataFrame()
        self.numeric_columns = []
        self.feature_checkboxes = {}
        self.target_column = None
        self.model = None
        self.worker = None
        self._busy = False
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("DataAnalysis [Informer]")
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
        target_layout.addRow("目标列（连续值）", self.combo_target)

        self.spin_test_ratio = QDoubleSpinBox()
        self.spin_test_ratio.setRange(0.05, 0.50)
        self.spin_test_ratio.setSingleStep(0.05)
        self.spin_test_ratio.setValue(0.20)
        self.spin_test_ratio.setSuffix("  测试占比")
        target_layout.addRow("测试集比例", self.spin_test_ratio)
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

        self.spin_seq_len = QSpinBox()
        self.spin_seq_len.setRange(2, 500)
        self.spin_seq_len.setValue(16)
        param_layout.addRow("序列长度", self.spin_seq_len)

        self.spin_d_model = QSpinBox()
        self.spin_d_model.setRange(8, 512)
        self.spin_d_model.setValue(64)
        param_layout.addRow("d_model（编码维度）", self.spin_d_model)

        self.spin_nhead = QSpinBox()
        self.spin_nhead.setRange(1, 16)
        self.spin_nhead.setValue(4)
        param_layout.addRow("注意力头数", self.spin_nhead)

        self.spin_num_layers = QSpinBox()
        self.spin_num_layers.setRange(1, 8)
        self.spin_num_layers.setValue(2)
        param_layout.addRow("编码器层数", self.spin_num_layers)

        self.spin_dim_feedforward = QSpinBox()
        self.spin_dim_feedforward.setRange(32, 2048)
        self.spin_dim_feedforward.setValue(256)
        param_layout.addRow("前馈网络维度", self.spin_dim_feedforward)

        self.spin_dropout = QDoubleSpinBox()
        self.spin_dropout.setRange(0.0, 0.9)
        self.spin_dropout.setDecimals(2)
        self.spin_dropout.setSingleStep(0.05)
        self.spin_dropout.setValue(0.1)
        param_layout.addRow("Dropout", self.spin_dropout)

        self.spin_epochs = QSpinBox()
        self.spin_epochs.setRange(1, 5000)
        self.spin_epochs.setValue(50)
        param_layout.addRow("训练轮次", self.spin_epochs)

        self.spin_batch_size = QSpinBox()
        self.spin_batch_size.setRange(1, 1024)
        self.spin_batch_size.setValue(32)
        param_layout.addRow("Batch Size", self.spin_batch_size)

        self.spin_lr = QDoubleSpinBox()
        self.spin_lr.setRange(0.00001, 1.0)
        self.spin_lr.setDecimals(5)
        self.spin_lr.setSingleStep(0.0001)
        self.spin_lr.setValue(0.0005)
        param_layout.addRow("学习率", self.spin_lr)
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

        right_group = QGroupBox("预测结果")
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

        if not _TORCH_AVAILABLE:
            self._update_result_text("警告：未检测到 PyTorch，Informer 功能不可用。\n请安装：pip install torch")
        else:
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
        self.spin_test_ratio.setEnabled(not busy)
        self.spin_seq_len.setEnabled(not busy)
        self.spin_d_model.setEnabled(not busy)
        self.spin_nhead.setEnabled(not busy)
        self.spin_num_layers.setEnabled(not busy)
        self.spin_dim_feedforward.setEnabled(not busy)
        self.spin_dropout.setEnabled(not busy)
        self.spin_epochs.setEnabled(not busy)
        self.spin_batch_size.setEnabled(not busy)
        self.spin_lr.setEnabled(not busy)
        self.label_busy.setText("正在训练 Informer 模型，请稍候。" if busy else "当前空闲。")

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
                QMessageBox.warning(self, "警告", "加载的数据为空，无法进行 Informer 分析。")
                return
            self.df = value.copy()
            self.numeric_columns = [col for col in self.df.columns if self._is_numeric_candidate(self.df[col])]
            if not self.numeric_columns:
                QMessageBox.warning(self, "警告", "未检测到可用数值列。")
                return
            self.combo_target.clear()
            self.combo_target.addItems([str(col) for col in self.numeric_columns])
            self._build_feature_selector()
            self.df_result = pd.DataFrame()
            self.plot_widget.clear("Run Informer to show the prediction chart.")
            self.btn_translate.setEnabled(False)
            self.label_info.setText(
                f"状态：已加载 {self.df.shape[0]} 行、{self.df.shape[1]} 列。"
                f"\n可用数值特征列：{len(self.numeric_columns)}"
            )
            self._update_result_text("数据已加载，请选择目标列和特征列后开始训练。")
            self.node.eval()
            QMessageBox.information(self, "成功", "Informer 数据加载完成。")
        except Exception as exc:
            self.node.markInvalid()
            QMessageBox.critical(self, "错误", f"Informer 数据加载失败：{exc}")

    def on_Create(self):
        if not _TORCH_AVAILABLE:
            QMessageBox.critical(self, "错误", "未安装 PyTorch，无法运行 Informer。\n请执行：pip install torch")
            return
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
            "test_ratio": self.spin_test_ratio.value(),
            "seq_len": self.spin_seq_len.value(),
            "d_model": self.spin_d_model.value(),
            "nhead": self.spin_nhead.value(),
            "num_layers": self.spin_num_layers.value(),
            "dim_feedforward": self.spin_dim_feedforward.value(),
            "dropout": self.spin_dropout.value(),
            "epochs": self.spin_epochs.value(),
            "batch_size": self.spin_batch_size.value(),
            "lr": self.spin_lr.value(),
        }

        self.worker = InformerWorker(self.df, target_column, feature_columns, params)
        self.worker.finished_ok.connect(self._on_worker_finished)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.finished.connect(self._on_worker_cleanup)
        self._set_busy(True)
        self._update_result_text("Informer 正在后台训练，请稍候...")
        self.worker.start()

    def _on_worker_finished(self, payload):
        self.df_result = payload["result_df"]
        self.model = payload["model"]
        self.target_column = self.worker.target_column if self.worker is not None else self.combo_target.currentText()
        self.plot_widget.plot_timeseries_prediction(
            self.df_result,
            self.target_column,
            "Informer_Prediction",
        )
        self._update_result_text(payload["summary_text"])

    def _on_worker_failed(self, message: str):
        self.df_result = pd.DataFrame()
        self.plot_widget.clear("Informer failed.")
        self._update_result_text("Informer 计算失败。\n\n" + message)
        QMessageBox.critical(self, "错误", f"Informer 计算失败：{message}")

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
            QMessageBox.information(self, "提示", "Informer 结果已传递。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"Informer 结果传递失败：{exc}")
