import pandas as pd
from PyQt5.QtWidgets import QLabel, QMessageBox, QWidget

from dataanalysis.async_task import BusyTaskMixin
from dataanalysis.buttonNode import ButtonNode
from dataanalysis.ui.ProcessResample_ui import Ui_Resample


PROCESS_DOWN_SAMPLE = "降采样"
PROCESS_UP_SAMPLE = "升采样"
PROCESS_ALIGN = "时间对齐"


class Win_ProcessResample(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.ui = Ui_Resample()
        self.ui.setupUi(self)
        self.setWindowTitle("DataAnalysis [Resample & Align]")

        self.node = node
        setattr(self.node, "window", self)

        self.df = pd.DataFrame()
        self.df2 = pd.DataFrame()
        self.df_processed = pd.DataFrame()
        self.time_column_1 = ""
        self.time_column_2 = ""

        self._info_labels = {}
        self._init_ui()
        self._bind_signals()

    def _init_ui(self):
        self.ui.groupBox.setTitle("处理类型")
        self.ui.groupBox_DownSample.setTitle("降采样参数")
        self.ui.groupBox_UpSample.setTitle("升采样参数")
        self.ui.groupBox_Align.setTitle("时间对齐说明")
        self.ui.groupBox_2.setTitle("数据信息")

        self.ui.label_Down.setText("时间间隔：")
        self.ui.label_Up.setText("采样频率：")
        self.ui.label_Align.setText("请先加载两组数据，系统将按时间轴进行对齐。")

        self.ui.btn_Load.setText("Load 1")
        self.ui.btn_Load2.setText("Load 2")
        self.ui.btn_Transfer.setText("Transfer")

        self.ui.cB_ProcessType.clear()
        self.ui.cB_ProcessType.addItems([PROCESS_DOWN_SAMPLE, PROCESS_UP_SAMPLE, PROCESS_ALIGN])

        self.ui.cB_DownSample.clear()
        self.ui.cB_DownSample.addItems(["1s", "5s", "30s", "1min", "5min"])

        self.ui.cB_UpSample.clear()
        self.ui.cB_UpSample.addItems(["1200Hz", "1000Hz", "800Hz", "400Hz", "200Hz"])

        self._build_info_panel()
        self.on_process_type_changed(self.ui.cB_ProcessType.currentText())

    def _bind_signals(self):
        self.ui.btn_Load.clicked.connect(self.on_Load)
        self.ui.btn_Load2.clicked.connect(self.on_Load2)
        self.ui.btn_Transfer.clicked.connect(self.on_Transfer)
        self.ui.cB_ProcessType.currentTextChanged.connect(self.on_process_type_changed)

    def _build_info_panel(self):
        self._clear_layout(self.ui.verticalLayout_data)
        rows = [
            ("dataset_1", "数据组 1：未加载"),
            ("dataset_2", "数据组 2：未加载"),
            ("output", "输出结果：未生成"),
        ]
        for key, text in rows:
            label = QLabel(text, self)
            label.setWordWrap(True)
            self.ui.verticalLayout_data.addWidget(label)
            self._info_labels[key] = label
        self.ui.verticalLayout_data.addStretch(1)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def on_process_type_changed(self, text):
        self.ui.groupBox_DownSample.setVisible(text == PROCESS_DOWN_SAMPLE)
        self.ui.groupBox_UpSample.setVisible(text == PROCESS_UP_SAMPLE)
        self.ui.groupBox_Align.setVisible(text == PROCESS_ALIGN)
        self.ui.btn_Load2.setVisible(text == PROCESS_ALIGN)

    def _update_info_labels(self):
        self._info_labels["dataset_1"].setText(self._describe_dataset("数据组 1", self.df, self.time_column_1))
        self._info_labels["dataset_2"].setText(self._describe_dataset("数据组 2", self.df2, self.time_column_2))
        if self.df_processed.empty:
            self._info_labels["output"].setText("输出结果：未生成")
        else:
            self._info_labels["output"].setText(self._describe_dataset("输出结果", self.df_processed, self._guess_time_column(self.df_processed)))

    def _describe_dataset(self, title, df, time_column):
        if df.empty:
            return f"{title}：未加载"

        lines = [f"{title}：{len(df)} 行 × {len(df.columns)} 列"]
        if time_column and time_column in df.columns:
            lines.append(f"时间列：{time_column}")
            lines.append(f"时间范围：{df[time_column].min()} ~ {df[time_column].max()}")
        return "\n".join(lines)

    def _load_input_dataframe(self, input_index):
        input_node = self.node.getInput(input_index)
        if input_node is None:
            raise ValueError("对应输入端口没有可用数据。")

        result = input_node.serialize()
        df = result.get("value", pd.DataFrame())
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("加载的数据为空。")
        return df.copy()

    def _guess_time_column(self, df):
        keywords = ["日期", "时间", "time", "date", "datetime", "timestamp", "ts"]
        lower_map = {str(col).lower(): col for col in df.columns}

        for keyword in keywords:
            for lower_name, original_name in lower_map.items():
                if keyword.lower() == lower_name or keyword.lower() in lower_name:
                    if pd.to_datetime(df[original_name], errors="coerce").notna().any():
                        return original_name

        for column in df.columns:
            converted = pd.to_datetime(df[column], errors="coerce")
            if converted.notna().any():
                return column

        return ""

    def _prepare_dataframe(self, df):
        time_column = self._guess_time_column(df)
        if not time_column:
            raise ValueError("数据中未识别到可用时间列。")

        prepared = df.copy()
        prepared[time_column] = pd.to_datetime(prepared[time_column], errors="coerce")
        prepared = prepared.dropna(subset=[time_column]).sort_values(by=time_column).reset_index(drop=True)
        if prepared.empty:
            raise ValueError("时间列无法转换为有效时间。")

        return prepared, time_column

    def on_Load(self):
        try:
            df = self._load_input_dataframe(0)
            self.df, self.time_column_1 = self._prepare_dataframe(df)
            self.df_processed = pd.DataFrame()
            self.node.markValid()
            self._update_info_labels()
            QMessageBox.information(self, "成功", "数据组 1 加载完成。")
        except Exception as exc:
            self.node.markInvalid()
            QMessageBox.warning(self, "提示", str(exc))

    def on_Load2(self):
        try:
            df = self._load_input_dataframe(1)
            self.df2, self.time_column_2 = self._prepare_dataframe(df)
            self.df_processed = pd.DataFrame()
            self._update_info_labels()
            QMessageBox.information(self, "成功", "数据组 2 加载完成。")
        except Exception as exc:
            QMessageBox.warning(self, "提示", str(exc))

    def on_Transfer(self):
        process_type = self.ui.cB_ProcessType.currentText()

        if self.df.empty:
            QMessageBox.warning(self, "提示", "请先加载数据组 1。")
            return

        if process_type == PROCESS_ALIGN and self.df2.empty:
            QMessageBox.warning(self, "提示", "时间对齐前请先加载数据组 2。")
            return

        if process_type == PROCESS_DOWN_SAMPLE:
            interval = self.ui.cB_DownSample.currentText()
            BusyTaskMixin._start_background_task(
                self,
                "降采样",
                "正在执行降采样，请稍候...",
                self._run_down_sample,
                self._on_process_success,
                self._on_process_error,
                interval,
            )
            return

        if process_type == PROCESS_UP_SAMPLE:
            frequency_text = self.ui.cB_UpSample.currentText()
            frequency_hz = int(frequency_text.replace("Hz", ""))
            BusyTaskMixin._start_background_task(
                self,
                "升采样",
                "正在执行升采样，请稍候...",
                self._run_up_sample,
                self._on_process_success,
                self._on_process_error,
                frequency_hz,
            )
            return

        BusyTaskMixin._start_background_task(
            self,
            "时间对齐",
            "正在执行时间对齐，请稍候...",
            self._run_time_align,
            self._on_process_success,
            self._on_process_error,
        )

    def _run_down_sample(self, interval):
        freq_map = {
            "1s": "1s",
            "5s": "5s",
            "30s": "30s",
            "1min": "1min",
            "5min": "5min",
        }
        freq = freq_map[interval]
        df = self.df.copy().set_index(self.time_column_1)
        processed = df.groupby(pd.Grouper(freq=freq)).first().dropna(how="all").reset_index()
        if processed.empty:
            raise ValueError("降采样后结果为空。")
        return processed

    def _run_up_sample(self, frequency_hz):
        df = self.df.copy()
        df["_time_second"] = df[self.time_column_1].dt.floor("s")
        base_rows = df.groupby("_time_second", as_index=False).first()
        if base_rows.empty:
            raise ValueError("升采样前没有可用数据。")

        expanded = base_rows.loc[base_rows.index.repeat(frequency_hz)].reset_index(drop=True)
        expanded[self.time_column_1] = expanded["_time_second"]
        expanded = expanded.drop(columns=["_time_second"])
        if expanded.empty:
            raise ValueError("升采样后结果为空。")
        return expanded

    def _run_time_align(self):
        df1 = self.df.copy()
        df2 = self.df2.copy()

        common_start = max(df1[self.time_column_1].min(), df2[self.time_column_2].min())
        common_end = min(df1[self.time_column_1].max(), df2[self.time_column_2].max())
        if common_start > common_end:
            raise ValueError("两组数据时间范围没有交集，无法对齐。")

        df1 = df1[(df1[self.time_column_1] >= common_start) & (df1[self.time_column_1] <= common_end)].reset_index(drop=True)
        df2 = df2[(df2[self.time_column_2] >= common_start) & (df2[self.time_column_2] <= common_end)].reset_index(drop=True)
        if df1.empty or df2.empty:
            raise ValueError("筛选交集时间范围后没有可对齐数据。")

        if self.time_column_2 != self.time_column_1:
            df2 = df2.rename(columns={self.time_column_2: self.time_column_1})

        df1["seq_num"] = df1.groupby(self.time_column_1).cumcount()
        df2["seq_num"] = df2.groupby(self.time_column_1).cumcount()

        index_1 = df1[[self.time_column_1, "seq_num"]].drop_duplicates()
        index_2 = df2[[self.time_column_1, "seq_num"]].drop_duplicates()
        global_index = pd.merge(index_1, index_2, on=[self.time_column_1, "seq_num"], how="outer")
        global_index = global_index.sort_values(by=[self.time_column_1, "seq_num"]).reset_index(drop=True)

        df1 = df1.merge(global_index, on=[self.time_column_1, "seq_num"], how="right")
        df2 = df2.merge(global_index, on=[self.time_column_1, "seq_num"], how="right")

        df1 = df1.sort_values(by=[self.time_column_1, "seq_num"]).reset_index(drop=True)
        df2 = df2.sort_values(by=[self.time_column_1, "seq_num"]).reset_index(drop=True)

        df1.columns = [
            column if column in [self.time_column_1, "seq_num"] else f"{column}_df1"
            for column in df1.columns
        ]
        df2.columns = [
            column if column in [self.time_column_1, "seq_num"] else f"{column}_df2"
            for column in df2.columns
        ]

        aligned = pd.merge(df1, df2, on=[self.time_column_1, "seq_num"], how="outer")
        aligned = aligned.sort_values(by=[self.time_column_1, "seq_num"]).reset_index(drop=True)

        value_columns = [column for column in aligned.columns if column not in [self.time_column_1, "seq_num"]]
        aligned = aligned.dropna(how="all", subset=value_columns)
        aligned = aligned.drop(columns=["seq_num"]).reset_index(drop=True)
        if aligned.empty:
            raise ValueError("时间对齐后结果为空。")
        return aligned

    def _on_process_success(self, processed_df):
        self.df_processed = processed_df.copy()
        if hasattr(self.node, "LoadData") and self.node.LoadData(self.df_processed):
            self.node.eval()
            self.node.evalChildren()
            self._update_info_labels()
            QMessageBox.information(self, "成功", "处理完成，结果已传递到下游节点。")
            return

        self._update_info_labels()
        QMessageBox.warning(self, "提示", "处理完成，但结果未能自动传递到下游节点。")

    def _on_process_error(self, message):
        self.df_processed = pd.DataFrame()
        self._update_info_labels()
        QMessageBox.critical(self, "错误", f"数据处理失败：{message}")

    def closeEvent(self, event):
        self.hide()
        event.ignore()

    def __del__(self):
        if hasattr(self.node, "window") and self.node.window is self:
            setattr(self.node, "window", None)
