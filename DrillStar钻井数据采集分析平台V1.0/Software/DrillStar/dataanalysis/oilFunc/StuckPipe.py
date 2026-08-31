import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QLabel, QMessageBox, QSizePolicy, QVBoxLayout, QWidget

from dataanalysis.async_task import BusyTaskMixin
from dataanalysis.buttonNode import ButtonNode
from dataanalysis.ui.oilFuncStuckPipe_ui import Ui_OilFuncStuckPipe


pg.setConfigOptions(antialias=True, useOpenGL=False, enableExperimental=False)


class DateTimeAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        labels = []
        for value in values:
            ts = pd.to_datetime(value, unit="s", errors="coerce")
            labels.append("" if pd.isna(ts) else ts.strftime("%m-%d\n%H:%M:%S"))
        return labels


def _normalize_text(value):
    return str(value).strip().lower().replace(" ", "")


class Win_OilFuncStuckPipe(QWidget, BusyTaskMixin):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.ui = Ui_OilFuncStuckPipe()
        self.ui.setupUi(self)
        self.ui.btn_Load.setText("Load")
        self.ui.btn_apply.setText("Calculate")
        self.ui.btn_Transfer.setText("Transfer")
        self.setWindowTitle("OilFunc [卡钻分析]")

        setattr(node, "window", self)
        self.node = node
        self.df_source = pd.DataFrame()
        self.df_output = pd.DataFrame()
        self.column_lookup = {}
        self.plot_widget = None
        self.max_points = 12000

        self.plot_layout = QVBoxLayout(self.ui.widget_plot)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)

        self._init_text()
        self._bind_signals()

    def _init_text(self):
        font = QFont()
        font.setPointSize(9)
        self.ui.label_standard.setFont(font)
        self.ui.label_standard.setTextFormat(Qt.RichText)
        self.ui.label_standard.setText(
            """
            <html><body style="line-height:1.45;">
            <p><b>当前判据说明：</b></p>
            <p>1. 系统对钻压、扭矩、转速分别取滚动中位数作为基线。</p>
            <p>2. 扭矩抬升、转速下降和钻压抬升共同表征卡钻风险变化。</p>
            <p>3. 系统输出风险值、风险趋势、风险等级及主导因素，便于继续传递至下游节点。</p>
            </body></html>
            """
        )

    def _bind_signals(self):
        self.ui.btn_Load.clicked.connect(self.on_load)
        self.ui.btn_apply.clicked.connect(self.on_analyze)
        self.ui.btn_Transfer.clicked.connect(self.on_transfer)

    def _get_input_df(self):
        input_node = self.node.getInput(0) if hasattr(self.node, "getInput") else None
        if input_node is None:
            return pd.DataFrame()
        result = input_node.serialize()
        if isinstance(result, dict):
            value = result.get("value", pd.DataFrame())
            return value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()
        if isinstance(result, pd.DataFrame):
            return result.copy()
        return pd.DataFrame()

    def _normalize_datetime_columns(self, df):
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                continue
            col_text = str(col).lower()
            if any(key in col_text for key in ["time", "date", "timestamp", "日期", "时间"]):
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                except Exception:
                    pass
        return df

    def _build_column_lookup(self):
        self.column_lookup = {str(col): col for col in self.df_source.columns}

    def _set_combo_items(self, combo, items, allow_empty=False):
        current_text = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        if allow_empty:
            combo.addItem("")
        combo.addItems(items)
        if current_text and combo.findText(current_text) >= 0:
            combo.setCurrentText(current_text)
        combo.blockSignals(False)

    def _get_actual_column(self, combo):
        text = combo.currentText().strip()
        if not text:
            return None
        return self.column_lookup.get(text)

    def _find_best_column(self, candidates, keywords):
        best_col = None
        best_score = -1
        for col in candidates:
            col_text = _normalize_text(col)
            raw_text = str(col)
            score = 0
            for keyword in keywords:
                kw_text = _normalize_text(keyword)
                if col_text == kw_text:
                    score += 10
                elif kw_text and kw_text in col_text:
                    score += 5
                if keyword in raw_text:
                    score += 2
            if score > best_score:
                best_score = score
                best_col = col
        return best_col if best_score > 0 else None

    def _fill_combos(self):
        all_cols = [str(col) for col in self.df_source.columns.tolist()]
        numeric_cols = [str(col) for col in self.df_source.select_dtypes(include=[np.number]).columns.tolist()]

        self._set_combo_items(self.ui.cB_Time, all_cols, allow_empty=True)
        self._set_combo_items(self.ui.cB_WOB, numeric_cols)
        self._set_combo_items(self.ui.cB_Torque, numeric_cols)
        self._set_combo_items(self.ui.cB_RPM, numeric_cols)

        time_col = self._find_best_column(all_cols, ["time", "date", "timestamp", "日期", "时间"])
        wob_col = self._find_best_column(numeric_cols, ["wob", "钻压", "weight"])
        torque_col = self._find_best_column(numeric_cols, ["torque", "toq", "扭矩"])
        rpm_col = self._find_best_column(numeric_cols, ["rpm", "转速", "rotary"])

        if time_col:
            self.ui.cB_Time.setCurrentText(str(time_col))
        if wob_col:
            self.ui.cB_WOB.setCurrentText(str(wob_col))
        if torque_col:
            self.ui.cB_Torque.setCurrentText(str(torque_col))
        if rpm_col:
            self.ui.cB_RPM.setCurrentText(str(rpm_col))

    def on_load(self):
        self.df_source = self._get_input_df()
        if self.df_source.empty:
            QMessageBox.warning(self, "提示", "上游节点没有可用数据。")
            return

        self.df_source = self._normalize_datetime_columns(self.df_source)
        self._build_column_lookup()
        self._fill_combos()
        self.df_output = pd.DataFrame()
        self.clear_plot()
        self.ui.label_summary.setText(
            f"当前状态：已加载 {self.df_source.shape[0]} 行 × {self.df_source.shape[1]} 列，系统已尝试自动识别钻压、扭矩和转速列。"
        )
        QMessageBox.information(self, "成功", f"已加载数据：{self.df_source.shape}")

    def _score_signal_change(self, series, direction="rise", window=25):
        clean_series = pd.to_numeric(series, errors="coerce")
        baseline = clean_series.rolling(window=window, min_periods=5).median()
        denominator = baseline.abs().replace(0, pd.NA)
        raw = (clean_series - baseline) / denominator if direction == "rise" else (baseline - clean_series) / denominator
        raw = raw.replace([np.inf, -np.inf], np.nan).fillna(0).clip(lower=0)
        scale = raw.quantile(0.95)
        if pd.isna(scale) or scale <= 0:
            scale = raw.max()
        if pd.isna(scale) or scale <= 0:
            scale = 1.0
        return (raw / scale).clip(0, 1)

    def _get_selected_columns(self):
        time_col = self._get_actual_column(self.ui.cB_Time)
        wob_col = self._get_actual_column(self.ui.cB_WOB)
        torque_col = self._get_actual_column(self.ui.cB_Torque)
        rpm_col = self._get_actual_column(self.ui.cB_RPM)
        if wob_col is None or torque_col is None or rpm_col is None:
            raise ValueError("请完整选择钻压、扭矩和转速列。")
        return time_col, wob_col, torque_col, rpm_col

    def _calculate_stuck_pipe_risk(self, time_col, wob_col, torque_col, rpm_col):
        result = self.df_source.copy()
        wob = pd.to_numeric(result[wob_col], errors="coerce")
        torque = pd.to_numeric(result[torque_col], errors="coerce")
        rpm = pd.to_numeric(result[rpm_col], errors="coerce")
        valid_mask = wob.notna() & torque.notna() & rpm.notna()
        if valid_mask.sum() < 10:
            raise ValueError("有效数据点过少，无法进行卡钻分析。")

        result["卡钻_钻压异常"] = self._score_signal_change(wob, direction="rise")
        result["卡钻_扭矩异常"] = self._score_signal_change(torque, direction="rise")
        result["卡钻_转速异常"] = self._score_signal_change(rpm, direction="drop")

        coupled = (0.6 * result["卡钻_扭矩异常"] + 0.4 * result["卡钻_转速异常"]).clip(0, 1)
        risk_raw = (
            0.45 * result["卡钻_扭矩异常"]
            + 0.35 * result["卡钻_转速异常"]
            + 0.15 * result["卡钻_钻压异常"]
            + 0.05 * coupled
        ).clip(0, 1)

        result["卡钻风险值"] = risk_raw.where(valid_mask)
        result["卡钻风险趋势"] = result["卡钻风险值"].rolling(window=15, min_periods=1, center=True).median()
        result["卡钻风险等级"] = pd.cut(
            result["卡钻风险趋势"],
            bins=[-float("inf"), 0.25, 0.45, 0.60, float("inf")],
            labels=["正常", "关注", "预警", "高风险"],
            include_lowest=True,
        ).astype("object")

        component_cols = ["卡钻_扭矩异常", "卡钻_转速异常", "卡钻_钻压异常"]
        dominant_idx = result[component_cols].fillna(0).idxmax(axis=1)
        dominant_map = {
            "卡钻_扭矩异常": "扭矩抬升",
            "卡钻_转速异常": "转速下降",
            "卡钻_钻压异常": "钻压抬升",
        }
        result["卡钻主导因素"] = dominant_idx.map(dominant_map)
        result.loc[result["卡钻风险趋势"].fillna(0) < 0.25, "卡钻主导因素"] = "正常波动"

        if time_col and time_col in result.columns:
            result["卡钻分析时间"] = pd.to_datetime(result[time_col], errors="coerce")
        return result

    def _build_summary_text(self):
        if self.df_output.empty:
            return "当前状态：未得到有效结果。"
        risk_series = self.df_output["卡钻风险趋势"].dropna()
        if risk_series.empty:
            return "当前状态：未得到有效结果。"
        high_ratio = (self.df_output["卡钻风险等级"] == "高风险").mean()
        warn_ratio = self.df_output["卡钻风险等级"].isin(["预警", "高风险"]).mean()
        return (
            f"当前状态：卡钻分析完成。P50={risk_series.median():.2f}，"
            f"P90={risk_series.quantile(0.9):.2f}，预警及以上占比 {warn_ratio:.1%}，高风险占比 {high_ratio:.1%}。"
        )

    def _get_plot_data(self):
        plot_df = self.df_output.loc[self.df_output["卡钻风险值"].notna()].copy()
        if plot_df.empty:
            return np.array([]), np.array([]), np.array([]), False

        if "卡钻分析时间" in plot_df.columns:
            time_series = pd.to_datetime(plot_df["卡钻分析时间"], errors="coerce").dropna()
            if len(time_series) > 1:
                plot_df = plot_df.loc[time_series.index]
                return (
                    (time_series.astype("int64") // 10**9).to_numpy(dtype=float),
                    plot_df["卡钻风险值"].to_numpy(dtype=float),
                    plot_df["卡钻风险趋势"].to_numpy(dtype=float),
                    True,
                )

        return (
            plot_df.index.to_numpy(dtype=float),
            plot_df["卡钻风险值"].to_numpy(dtype=float),
            plot_df["卡钻风险趋势"].to_numpy(dtype=float),
            False,
        )

    def _sample_plot_data(self, x_data, y_raw, y_smooth):
        if len(x_data) <= self.max_points:
            return x_data, y_raw, y_smooth
        step = max(1, len(x_data) // self.max_points)
        return x_data[::step], y_raw[::step], y_smooth[::step]

    def clear_plot(self):
        while self.plot_layout.count():
            item = self.plot_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.plot_widget = None

    def _draw_plot(self):
        self.clear_plot()
        x_data, y_raw, y_smooth, use_time_axis = self._get_plot_data()
        if len(x_data) == 0:
            return

        x_data, y_raw, y_smooth = self._sample_plot_data(x_data, y_raw, y_smooth)
        axis_items = {"bottom": DateTimeAxisItem(orientation="bottom")} if use_time_axis else None
        self.plot_widget = pg.PlotWidget(axisItems=axis_items)
        self.plot_widget.setBackground("w")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.35)
        self.plot_widget.setClipToView(True)
        self.plot_widget.setDownsampling(mode="peak")
        self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_widget.setLabel("left", "卡钻风险值")
        self.plot_widget.setLabel("bottom", "时间" if use_time_axis else "样本点")
        self.plot_widget.plot(x_data, y_raw, pen=pg.mkPen(color=QColor(0, 114, 189), width=1.0, cosmetic=True))
        self.plot_widget.plot(x_data, y_smooth, pen=pg.mkPen(color=QColor(217, 83, 25), width=2.0, cosmetic=True))
        for threshold, color in [(0.25, "#7cb342"), (0.45, "#f9a825"), (0.60, "#d84315")]:
            self.plot_widget.addItem(pg.InfiniteLine(pos=threshold, angle=0, pen=pg.mkPen(color=color, width=1, style=Qt.DashLine)))
        self.plot_layout.addWidget(self.plot_widget)

    def on_analyze(self):
        if self.df_source.empty:
            QMessageBox.warning(self, "提示", "请先加载数据。")
            return
        try:
            columns = self._get_selected_columns()
            self._start_background_task(
                "卡钻分析",
                "正在计算卡钻风险，请稍候...",
                self._calculate_stuck_pipe_risk,
                self._on_analyze_finished,
                self._on_analyze_failed,
                *columns,
            )
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"卡钻分析失败：{exc}")

    def _on_analyze_finished(self, df_output):
        self.df_output = df_output
        self.ui.label_summary.setText(self._build_summary_text())
        self._draw_plot()
        QMessageBox.information(self, "成功", "卡钻分析完成。")

    def _on_analyze_failed(self, message):
        QMessageBox.critical(self, "错误", f"卡钻分析失败：{message}")

    def on_transfer(self):
        if self.df_output.empty:
            QMessageBox.warning(self, "提示", "请先完成卡钻分析。")
            return

        success = True
        if hasattr(self.node, "LoadData"):
            success = bool(self.node.LoadData(self.df_output))
        else:
            self.node.data = {"value": self.df_output}
        if not success:
            QMessageBox.critical(self, "错误", "结果传递失败。")
            return

        if hasattr(self.node, "eval"):
            self.node.eval()
        if hasattr(self.node, "evalChildren"):
            self.node.evalChildren()
        QMessageBox.information(self, "成功", f"结果已传递：{self.df_output.shape}")

    def closeEvent(self, event):
        self.hide()
        event.ignore()


def _stuck_pipe_draw_plot_with_legend(self):
    self.clear_plot()
    x_data, y_raw, y_smooth, use_time_axis = self._get_plot_data()
    if len(x_data) == 0:
        return

    x_data, y_raw, y_smooth = self._sample_plot_data(x_data, y_raw, y_smooth)
    axis_items = {"bottom": DateTimeAxisItem(orientation="bottom")} if use_time_axis else None
    self.plot_widget = pg.PlotWidget(axisItems=axis_items)
    self.plot_widget.setBackground("w")
    self.plot_widget.showGrid(x=True, y=True, alpha=0.35)
    self.plot_widget.setClipToView(True)
    self.plot_widget.setDownsampling(mode="peak")
    self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.plot_widget.setLabel("left", "卡钻风险值")
    self.plot_widget.setLabel("bottom", "时间" if use_time_axis else "样本点")
    self.plot_widget.addLegend(offset=(10, 10))

    self.plot_widget.plot(
        x_data,
        y_raw,
        pen=pg.mkPen(color=QColor(0, 114, 189), width=1.0, cosmetic=True),
        name="原始风险值",
    )
    self.plot_widget.plot(
        x_data,
        y_smooth,
        pen=pg.mkPen(color=QColor(217, 83, 25), width=2.0, cosmetic=True),
        name="平滑风险趋势",
    )

    threshold_configs = [
        (0.25, "#7cb342", "正常/关注阈值"),
        (0.45, "#f9a825", "关注/预警阈值"),
        (0.60, "#d84315", "预警/高风险阈值"),
    ]
    for threshold, color, label in threshold_configs:
        line = pg.InfiniteLine(
            pos=threshold,
            angle=0,
            pen=pg.mkPen(color=color, width=1, style=Qt.DashLine),
        )
        self.plot_widget.addItem(line)
        legend = self.plot_widget.plot([x_data[0], x_data[-1]], [threshold, threshold], pen=pg.mkPen(color=color, width=1, style=Qt.DashLine), name=label)
        legend.hide()

    self.plot_layout.addWidget(self.plot_widget)


Win_OilFuncStuckPipe._draw_plot = _stuck_pipe_draw_plot_with_legend


def _stuck_pipe_ensure_time_label(self):
    if getattr(self, "label_time_range", None) is None:
        self.label_time_range = QLabel("当前选中时间：无", self.ui.widget_right)
        self.label_time_range.setAlignment(Qt.AlignCenter)
        self.label_time_range.setMinimumHeight(40)
        self.label_time_range.setStyleSheet("border: 1px solid #cccccc; border-radius: 4px; padding: 5px;")
        insert_index = self.ui.verticalLayout_right.indexOf(self.ui.widget_plot)
        if insert_index < 0:
            self.ui.verticalLayout_right.addWidget(self.label_time_range)
        else:
            self.ui.verticalLayout_right.insertWidget(insert_index, self.label_time_range)


def _stuck_pipe_update_time_range_label(self, x_data):
    if not getattr(self, "linear_region", None) or len(x_data) == 0 or not getattr(self, "_use_time_axis", False):
        self.label_time_range.setText("当前选中时间：无")
        return

    min_time_num, max_time_num = self.linear_region.getRegion()
    start_time = pd.to_datetime(min_time_num, unit="s", errors="coerce")
    end_time = pd.to_datetime(max_time_num, unit="s", errors="coerce")
    if pd.isna(start_time) or pd.isna(end_time):
        self.label_time_range.setText("当前选中时间：无")
        return
    self.label_time_range.setText(
        f"当前选中时间：\n{start_time.strftime('%Y-%m-%d %H:%M:%S')}\n至\n{end_time.strftime('%Y-%m-%d %H:%M:%S')}"
    )


def _stuck_pipe_draw_plot_single(self):
    self.clear_plot()
    self._stuck_pipe_ensure_time_label()
    x_data, y_raw, y_smooth, use_time_axis = self._get_plot_data()
    self._use_time_axis = use_time_axis
    if len(x_data) == 0:
        self.label_time_range.setText("当前选中时间：无")
        return

    x_data, y_raw, y_smooth = self._sample_plot_data(x_data, y_raw, y_smooth)
    axis_items = {"bottom": DateTimeAxisItem(orientation="bottom")} if use_time_axis else None
    self.plot_widget = pg.PlotWidget(axisItems=axis_items)
    self.plot_widget.setBackground("w")
    self.plot_widget.showGrid(x=True, y=True, alpha=0.35)
    self.plot_widget.setClipToView(True)
    self.plot_widget.setDownsampling(mode="peak")
    self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.plot_widget.setLabel("left", "卡钻风险值")
    self.plot_widget.setLabel("bottom", "时间" if use_time_axis else "样本点")
    self.plot_widget.plot(x_data, y_raw, pen=pg.mkPen(color=QColor(0, 114, 189), width=1.5, cosmetic=True))

    for threshold, color in [(0.25, "#7cb342"), (0.45, "#f9a825"), (0.60, "#d84315")]:
        self.plot_widget.addItem(
            pg.InfiniteLine(pos=threshold, angle=0, pen=pg.mkPen(color=color, width=1, style=Qt.DashLine))
        )

    self.linear_region = None
    if use_time_axis and len(x_data) > 1:
        min_time = float(x_data.min())
        max_time = float(x_data.max())
        default_right = min_time + max((max_time - min_time) * 0.1, 1.0)
        self.linear_region = pg.LinearRegionItem(
            [min_time, min(default_right, max_time)],
            pen=pg.mkPen(QColor(0, 0, 0), width=1.5),
            brush=pg.mkBrush(QColor(0, 0, 255, 30)),
            movable=True,
        )
        self.linear_region.sigRegionChanged.connect(lambda: self._update_time_range_label(x_data))
        self.plot_widget.addItem(self.linear_region)

    self.plot_layout.addWidget(self.plot_widget)
    self._update_time_range_label(x_data)


Win_OilFuncStuckPipe._stuck_pipe_ensure_time_label = _stuck_pipe_ensure_time_label
Win_OilFuncStuckPipe._update_time_range_label = _stuck_pipe_update_time_range_label
Win_OilFuncStuckPipe._draw_plot = _stuck_pipe_draw_plot_single


def create_stuck_pipe_window(node):
    return Win_OilFuncStuckPipe(node)


_orig_stuck_pipe_on_analyze_finished = Win_OilFuncStuckPipe._on_analyze_finished


def _stuck_pipe_draw_plot_v2(self):
    self.clear_plot()
    self._stuck_pipe_ensure_time_label()
    x_data, y_raw, y_smooth, use_time_axis = self._get_plot_data()
    self._use_time_axis = use_time_axis
    if len(x_data) == 0:
        self.label_time_range.setText("当前选中时间：无")
        return

    if len(x_data) > 4000:
        step = max(1, len(x_data) // 4000)
        x_data = x_data[::step]
        y_raw = y_raw[::step]

    axis_items = {"bottom": DateTimeAxisItem(orientation="bottom")} if use_time_axis else None
    self.plot_widget = pg.PlotWidget(axisItems=axis_items)
    self.plot_widget.setBackground("w")
    self.plot_widget.showGrid(x=True, y=True, alpha=0.25)
    self.plot_widget.setClipToView(True)
    self.plot_widget.setDownsampling(mode="peak")
    self.plot_widget.setLabel("left", "卡钻风险值")
    self.plot_widget.setLabel("bottom", "时间" if use_time_axis else "样本点")
    self.plot_widget.plot(
        x_data,
        y_raw,
        pen=pg.mkPen(color=QColor(0, 114, 189), width=1.3, cosmetic=True),
        connect="finite",
        skipFiniteCheck=True,
    )

    for threshold, color in [(0.25, "#7cb342"), (0.45, "#f9a825"), (0.60, "#d84315")]:
        self.plot_widget.addItem(
            pg.InfiniteLine(pos=threshold, angle=0, pen=pg.mkPen(color=color, width=1, style=Qt.DashLine))
        )

    self.linear_region = None
    if use_time_axis and len(x_data) > 1:
        min_time = float(x_data.min())
        max_time = float(x_data.max())
        default_right = min_time + max((max_time - min_time) * 0.1, 1.0)
        self.linear_region = pg.LinearRegionItem(
            [min_time, min(default_right, max_time)],
            pen=pg.mkPen(QColor(0, 0, 0), width=1.2),
            brush=pg.mkBrush(QColor(0, 0, 255, 20)),
            movable=True,
        )
        self.linear_region.sigRegionChangeFinished.connect(lambda: self._update_time_range_label(x_data))
        self.plot_widget.addItem(self.linear_region)

    self.plot_layout.addWidget(self.plot_widget)
    self._update_time_range_label(x_data)


def _stuck_pipe_on_analyze_finished_v2(self, df_output):
    _orig_stuck_pipe_on_analyze_finished(self, df_output)
    if hasattr(self.node, "markValid"):
        self.node.markValid()
    if hasattr(self.node, "markDirty"):
        self.node.markDirty(False)
    if hasattr(self.node, "markInvalid"):
        self.node.markInvalid(False)


Win_OilFuncStuckPipe._draw_plot = _stuck_pipe_draw_plot_v2
Win_OilFuncStuckPipe._on_analyze_finished = _stuck_pipe_on_analyze_finished_v2


def _stuck_pipe_init_text_v3(self):
    font = QFont()
    font.setPointSize(9)
    self.ui.label_standard.setFont(font)
    self.ui.label_standard.setTextFormat(Qt.RichText)
    self.ui.label_standard.setText(
        """
        <html><body style="line-height:1.55;">
        <p><b>卡钻风险值标准：</b></p>
        <p>1. 风险值 &lt; 0.25：正常。</p>
        <p>2. 0.25 ≤ 风险值 &lt; 0.45：关注。</p>
        <p>3. 0.45 ≤ 风险值 &lt; 0.60：可能危险。</p>
        <p>4. 风险值 ≥ 0.60：异常。</p>
        <p><b>图中颜色说明：</b></p>
        <p>蓝色散点表示正常或关注数据；橙色散点表示可能危险；红色散点表示异常。</p>
        </body></html>
        """
    )


def _stuck_pipe_draw_plot_v3(self):
    self.clear_plot()
    self._stuck_pipe_ensure_time_label()
    x_data, y_raw, y_smooth, use_time_axis = self._get_plot_data()
    self._use_time_axis = use_time_axis
    if len(x_data) == 0:
        self.label_time_range.setText("当前选中时间：无")
        return

    if len(x_data) > 5000:
        step = max(1, len(x_data) // 5000)
        x_data = x_data[::step]
        y_raw = y_raw[::step]

    axis_items = {"bottom": DateTimeAxisItem(orientation="bottom")} if use_time_axis else None
    self.plot_widget = pg.PlotWidget(axisItems=axis_items)
    self.plot_widget.setBackground("w")
    self.plot_widget.showGrid(x=True, y=True, alpha=0.25)
    self.plot_widget.setClipToView(True)
    self.plot_widget.setDownsampling(mode="peak")
    self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.plot_widget.setLabel("left", "卡钻风险值")
    self.plot_widget.setLabel("bottom", "时间" if use_time_axis else "样本点")

    normal_mask = y_raw < 0.45
    warning_mask = (y_raw >= 0.45) & (y_raw < 0.60)
    abnormal_mask = y_raw >= 0.60

    if normal_mask.any():
        self.plot_widget.addItem(
            pg.ScatterPlotItem(
                x=x_data[normal_mask],
                y=y_raw[normal_mask],
                size=6,
                pen=pg.mkPen(QColor(0, 114, 189), width=1.2),
                brush=pg.mkBrush(QColor(0, 114, 189, 160)),
            )
        )
    if warning_mask.any():
        self.plot_widget.addItem(
            pg.ScatterPlotItem(
                x=x_data[warning_mask],
                y=y_raw[warning_mask],
                size=7,
                pen=pg.mkPen(QColor(245, 166, 35), width=1.3),
                brush=pg.mkBrush(QColor(245, 166, 35, 180)),
            )
        )
    if abnormal_mask.any():
        self.plot_widget.addItem(
            pg.ScatterPlotItem(
                x=x_data[abnormal_mask],
                y=y_raw[abnormal_mask],
                size=8,
                pen=pg.mkPen(QColor(217, 83, 25), width=1.4),
                brush=pg.mkBrush(QColor(217, 83, 25, 190)),
            )
        )

    for threshold, color in [(0.25, "#7cb342"), (0.45, "#f9a825"), (0.60, "#d84315")]:
        self.plot_widget.addItem(
            pg.InfiniteLine(
                pos=threshold,
                angle=0,
                pen=pg.mkPen(color=color, width=2.2, style=Qt.DashLine),
            )
        )

    self.linear_region = None
    if use_time_axis and len(x_data) > 1:
        min_time = float(x_data.min())
        max_time = float(x_data.max())
        default_right = min_time + max((max_time - min_time) * 0.1, 1.0)
        self.linear_region = pg.LinearRegionItem(
            [min_time, min(default_right, max_time)],
            pen=pg.mkPen(QColor(0, 0, 0), width=1.2),
            brush=pg.mkBrush(QColor(0, 0, 255, 20)),
            movable=True,
        )
        self.linear_region.sigRegionChangeFinished.connect(lambda: self._update_time_range_label(x_data))
        self.plot_widget.addItem(self.linear_region)

    self.plot_layout.addWidget(self.plot_widget)
    self._update_time_range_label(x_data)


Win_OilFuncStuckPipe._init_text = _stuck_pipe_init_text_v3
Win_OilFuncStuckPipe._draw_plot = _stuck_pipe_draw_plot_v3
