import pandas as pd
from PyQt5.QtCore import QAbstractTableModel, Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QInputDialog,
    QMenu,
    QMessageBox,
    QTableWidgetItem,
    QWidget,
)

from dataanalysis.buttonNode import ButtonNode
from dataanalysis.ui.dataTable_ui import Ui_DataTable


class Win_DataTable(QWidget):
    def __init__(self, node: ButtonNode):
        super().__init__()
        self.ui = Ui_DataTable()
        self.ui.setupUi(self)
        self.setWindowTitle("DataAnalysis [Data table]")

        self.title = None
        self.node = node
        self.df = pd.DataFrame()
        self._df = pd.DataFrame()
        self.row_start = 0
        self.row_end = 0
        self.columnsName = []
        self.selectColumns = []
        self._view_row_index = []
        self._view_columns = []
        self._view_source_columns = []

        self._init_ui_state()
        self._bind_signals()

    def _init_ui_state(self):
        self.ui.groupBox_2.setMaximumWidth(620)
        self.ui.tW_original.setMinimumWidth(240)
        self.ui.tW_original.setMaximumWidth(280)
        self.ui.tW_select.setMinimumWidth(240)
        self.ui.tW_select.setMaximumWidth(280)
        self.ui.horizontalLayout_4.setStretch(0, 0)
        self.ui.horizontalLayout_4.setStretch(1, 1)

        self.ui.btn_Transfer.setEnabled(False)
        self.ui.btn_updateData.setEnabled(False)

        self.ui.tV_DataShow.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        self.ui.tV_DataShow.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.ui.tV_DataShow.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.ui.tV_DataShow.setAlternatingRowColors(True)
        self.ui.tV_DataShow.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.ui.tV_DataShow.horizontalHeader().setStretchLastSection(False)
        self.ui.tV_DataShow.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.ui.tV_DataShow.verticalHeader().setDefaultSectionSize(26)

        self.ui.tV_DataShow.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.tV_DataShow.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.tV_DataShow.verticalHeader().setContextMenuPolicy(Qt.CustomContextMenu)

        self.ui.tW_original.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ui.tW_select.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ui.tW_original.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ui.tW_select.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ui.tW_original.setColumnCount(1)
        self.ui.tW_select.setColumnCount(1)
        self.ui.tW_original.setRowCount(0)
        self.ui.tW_select.setRowCount(0)

        self.ui.tV_DataShow.setToolTip(
            "右侧预览表支持直接编辑。\n双击列标题可改名，右键行头/列头可新增或删除行列。"
        )

    def _bind_signals(self):
        self.ui.btn_Load.clicked.connect(self.on_Load)
        self.ui.btn_Transfer.clicked.connect(self.on_Transfer)
        self.ui.btn_select.clicked.connect(self.on_Select)
        self.ui.btn_delete.clicked.connect(self.on_Delete)
        self.ui.btn_updateData.clicked.connect(self.on_UpdateData)
        self.ui.tV_DataShow.horizontalHeader().sectionDoubleClicked.connect(self.on_RenameColumn)
        self.ui.tV_DataShow.customContextMenuRequested.connect(self.on_TableContextMenu)
        self.ui.tV_DataShow.horizontalHeader().customContextMenuRequested.connect(self.on_ColumnHeaderMenu)
        self.ui.tV_DataShow.verticalHeader().customContextMenuRequested.connect(self.on_RowHeaderMenu)

    def _apply_selected_columns(self):
        if self.df.empty:
            return pd.DataFrame()

        if not self.selectColumns:
            return self.df.copy()

        valid_columns = [column for column in self.selectColumns if column in self.df.columns]
        if not valid_columns:
            return self.df.copy()

        return self.df.loc[:, valid_columns].copy()

    def _apply_row_range(self, df: pd.DataFrame):
        if df.empty:
            return df.copy()

        start = int(self.ui.lE_row_start.text())
        end = int(self.ui.lE_row_end.text())
        start = max(0, start)
        end = min(max(len(df) - 1, 0), end)

        if start > end:
            raise ValueError("start_after_end")

        self.row_start = start
        self.row_end = end
        self.ui.lE_row_start.setText(str(start))
        self.ui.lE_row_end.setText(str(end))
        return df.iloc[start : end + 1].copy()

    def _refresh_selected_table(self):
        self.ui.tW_select.setRowCount(0)
        for column in self.selectColumns:
            row_count = self.ui.tW_select.rowCount()
            self.ui.tW_select.insertRow(row_count)
            self.ui.tW_select.setItem(row_count, 0, QTableWidgetItem(str(column)))

    def _refresh_original_table(self):
        self.ui.tW_original.setRowCount(0)
        for column in self.columnsName:
            row_count = self.ui.tW_original.rowCount()
            self.ui.tW_original.insertRow(row_count)
            self.ui.tW_original.setItem(row_count, 0, QTableWidgetItem(str(column)))

    def _convert_value(self, source_column, value_text):
        if source_column is None or source_column not in self.df.columns:
            return "" if value_text is None else str(value_text)

        dtype = self.df[source_column].dtype
        text = "" if value_text is None else str(value_text).strip()

        if text == "":
            if pd.api.types.is_numeric_dtype(dtype):
                return pd.NA
            if pd.api.types.is_datetime64_any_dtype(dtype):
                return pd.NaT
            return ""

        if pd.api.types.is_integer_dtype(dtype):
            return int(float(text))
        if pd.api.types.is_float_dtype(dtype):
            return float(text)
        if pd.api.types.is_bool_dtype(dtype):
            lowered = text.lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
            raise ValueError("布尔值请输入 True/False 或 1/0")
        if pd.api.types.is_datetime64_any_dtype(dtype):
            return pd.to_datetime(text)
        return text

    def _refresh_preview(self):
        if "source_columns" not in self._df.attrs:
            self._df.attrs["source_columns"] = list(self._df.columns)
        self.on_tableView(self.title, self._df)
        self.node.markDirty()

    def _insert_row(self, insert_at):
        if self._df.empty and self._df.columns.empty:
            QMessageBox.information(self, "提示", "请先加载并生成预览数据后再新增行。")
            return

        insert_at = max(0, min(insert_at, len(self._df)))
        new_row = pd.DataFrame([{col: "" for col in self._df.columns}])
        top = self._df.iloc[:insert_at]
        bottom = self._df.iloc[insert_at:]
        self._df = pd.concat([top, new_row, bottom], ignore_index=True)
        self._df.attrs["source_columns"] = list(self._view_source_columns)
        self._refresh_preview()

    def _delete_rows(self, row_indexes):
        if self._df.empty:
            return
        if not row_indexes:
            QMessageBox.information(self, "提示", "请先选择要删除的行。")
            return

        self._df = self._df.drop(index=sorted(set(row_indexes))).reset_index(drop=True)
        self._df.attrs["source_columns"] = list(self._view_source_columns)
        self._refresh_preview()

    def _insert_column(self, insert_at=None):
        if self._df.empty:
            QMessageBox.information(self, "提示", "请先加载并生成预览数据后再新增列。")
            return

        new_name, ok = QInputDialog.getText(self, "新增列", "请输入新列名称：")
        if not ok:
            return

        new_name = new_name.strip()
        if not new_name:
            QMessageBox.warning(self, "提示", "列名不能为空。")
            return
        if new_name in self._df.columns:
            QMessageBox.warning(self, "提示", "列名已存在，请使用其他名称。")
            return

        if insert_at is None:
            insert_at = len(self._df.columns)
        insert_at = max(0, min(insert_at, len(self._df.columns)))
        self._df.insert(insert_at, new_name, "")

        source_columns = list(self._view_source_columns)
        source_columns.insert(insert_at, None)
        self._df.attrs["source_columns"] = source_columns
        self._refresh_preview()

    def _delete_columns(self, column_indexes):
        if self._df.empty:
            return
        if not column_indexes:
            QMessageBox.information(self, "提示", "请先选择要删除的列。")
            return

        unique_indexes = sorted(set(column_indexes), reverse=True)
        column_names = [self._df.columns[idx] for idx in unique_indexes]
        self._df = self._df.drop(columns=column_names)

        source_columns = list(self._view_source_columns)
        for idx in unique_indexes:
            if 0 <= idx < len(source_columns):
                source_columns.pop(idx)
        self._df.attrs["source_columns"] = source_columns
        self._refresh_preview()

    def _selected_row_indexes(self):
        selection_model = self.ui.tV_DataShow.selectionModel()
        if selection_model is None:
            return []
        return sorted({index.row() for index in selection_model.selectedRows()})

    def _selected_column_indexes(self):
        selection_model = self.ui.tV_DataShow.selectionModel()
        if selection_model is None:
            return []
        return sorted({index.column() for index in selection_model.selectedColumns()})

    def _current_row(self):
        current = self.ui.tV_DataShow.currentIndex()
        return current.row() if current.isValid() else len(self._df)

    def _current_column(self):
        current = self.ui.tV_DataShow.currentIndex()
        return current.column() if current.isValid() else len(self._df.columns)

    def _handle_cell_update(self, row, column, value_text):
        if (
            row >= len(self._view_row_index)
            or column >= len(self._view_columns)
            or column >= len(self._view_source_columns)
        ):
            return False, "编辑位置超出范围"

        source_row = self._view_row_index[row]
        current_column = self._view_columns[column]
        source_column = self._view_source_columns[column]

        try:
            converted_value = self._convert_value(source_column, value_text)
        except Exception as exc:
            QMessageBox.warning(self, "提示", f"输入格式不正确：{exc}")
            return False, None

        try:
            self._df.at[source_row, current_column] = converted_value
            self.node.markDirty()
            return True, converted_value
        except Exception as exc:
            QMessageBox.warning(self, "提示", f"修改失败：{exc}")
            return False, None

    def on_Select(self):
        selected_items = self.ui.tW_original.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请先在左侧选择需要添加的列。")
            return

        contents = selected_items[0].text()
        if contents not in self.selectColumns:
            self.selectColumns.append(contents)
            self._refresh_selected_table()

    def on_Delete(self):
        if not self.selectColumns:
            QMessageBox.information(self, "提示", "当前没有已选列可删除。")
            return

        selected_items = self.ui.tW_select.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请先在右侧选择需要删除的列。")
            return

        contents = selected_items[0].text()
        if contents in self.selectColumns:
            self.selectColumns.remove(contents)
            self._refresh_selected_table()

    def on_UpdateData(self):
        if self.df.empty:
            QMessageBox.warning(self, "提示", "请先加载数据。")
            return

        try:
            self._df = self._apply_selected_columns()
            self._df = self._apply_row_range(self._df)
            self._df = self._df.reset_index(drop=True)
            self._df.attrs["source_columns"] = list(self._df.columns)
            self.on_tableView(self.title, self._df)
        except ValueError:
            QMessageBox.warning(self, "提示", "行号请输入有效整数，且起始行不能大于结束行。")

    def on_RenameColumn(self, section):
        if self._df.empty or section < 0 or section >= len(self._df.columns):
            return

        old_name = str(self._df.columns[section])
        new_name, ok = QInputDialog.getText(self, "修改列标题", "请输入新的列标题：", text=old_name)
        if not ok:
            return

        new_name = new_name.strip()
        if not new_name:
            QMessageBox.warning(self, "提示", "列标题不能为空。")
            return
        if new_name == old_name:
            return
        if new_name in self._df.columns:
            QMessageBox.warning(self, "提示", "列标题已存在，请使用其他名称。")
            return

        source_columns = list(self._view_source_columns)
        self._df.rename(columns={old_name: new_name}, inplace=True)
        self._df.attrs["source_columns"] = source_columns
        self._refresh_preview()

    def on_TableContextMenu(self, pos):
        if self._df.empty:
            return

        menu = QMenu(self)
        action_add_row = menu.addAction("新增一行")
        action_delete_rows = menu.addAction("删除选中行")
        menu.addSeparator()
        action_add_col = menu.addAction("新增一列")
        action_delete_cols = menu.addAction("删除选中列")
        action = menu.exec_(self.ui.tV_DataShow.viewport().mapToGlobal(pos))

        if action == action_add_row:
            self._insert_row(self._current_row() + 1)
        elif action == action_delete_rows:
            self._delete_rows(self._selected_row_indexes())
        elif action == action_add_col:
            self._insert_column(self._current_column() + 1)
        elif action == action_delete_cols:
            self._delete_columns(self._selected_column_indexes())

    def on_ColumnHeaderMenu(self, pos):
        if self._df.empty:
            return

        column = self.ui.tV_DataShow.horizontalHeader().logicalIndexAt(pos)
        menu = QMenu(self)
        action_rename = menu.addAction("修改列标题")
        action_add_left = menu.addAction("在左侧新增列")
        action_add_right = menu.addAction("在右侧新增列")
        action_delete = menu.addAction("删除当前列")
        action = menu.exec_(self.ui.tV_DataShow.horizontalHeader().mapToGlobal(pos))

        if action == action_rename and column >= 0:
            self.on_RenameColumn(column)
        elif action == action_add_left:
            self._insert_column(column if column >= 0 else 0)
        elif action == action_add_right:
            self._insert_column((column + 1) if column >= 0 else len(self._df.columns))
        elif action == action_delete and column >= 0:
            self._delete_columns([column])

    def on_RowHeaderMenu(self, pos):
        if self._df.empty:
            return

        row = self.ui.tV_DataShow.verticalHeader().logicalIndexAt(pos)
        menu = QMenu(self)
        action_add_above = menu.addAction("在上方新增行")
        action_add_below = menu.addAction("在下方新增行")
        action_delete = menu.addAction("删除当前行")
        action_delete_selected = menu.addAction("删除选中行")
        action = menu.exec_(self.ui.tV_DataShow.verticalHeader().mapToGlobal(pos))

        if action == action_add_above:
            self._insert_row(row if row >= 0 else 0)
        elif action == action_add_below:
            self._insert_row((row + 1) if row >= 0 else len(self._df))
        elif action == action_delete and row >= 0:
            self._delete_rows([row])
        elif action == action_delete_selected:
            self._delete_rows(self._selected_row_indexes())

    def on_Load(self):
        input_node = self.node.getInput(0)
        if input_node is None:
            self.node.markDirty()
            self.node.markInvalid()
            QMessageBox.warning(self, "警告", "上游节点没有可用数据。")
            return

        try:
            result = input_node.serialize()
            self.df = result["value"]
            self.title = result["title"]

            if not isinstance(self.df, pd.DataFrame):
                QMessageBox.warning(self, "警告", "加载结果不是有效的数据表。")
                return

            self._df = self.df.copy().reset_index(drop=True)
            self._df.attrs["source_columns"] = list(self._df.columns)
            self.on_tableView(self.title, self._df)
            self.row_start = 0
            self.row_end = max(self.df.shape[0] - 1, 0)
            self.ui.lE_row_start.setText(str(self.row_start))
            self.ui.lE_row_end.setText(str(self.row_end))

            self.columnsName = list(self.df.columns.values)
            self.selectColumns = []

            self.ui.tW_original.clear()
            self.ui.tW_select.clear()
            self.ui.tW_original.setColumnCount(1)
            self.ui.tW_select.setColumnCount(1)
            self.ui.tW_original.setRowCount(0)
            self.ui.tW_select.setRowCount(0)
            self.ui.tW_original.setHorizontalHeaderLabels(["参数"])
            self.ui.tW_select.setHorizontalHeaderLabels(["参数"])
            self._refresh_original_table()

            if self.columnsName:
                self.ui.tW_original.selectRow(0)

            self.ui.btn_Transfer.setEnabled(True)
            self.ui.btn_updateData.setEnabled(True)
            self.node.eval()
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"数据加载失败：{exc}")

    def on_tableView(self, title, df):
        self._view_row_index = list(df.index)
        self._view_columns = list(df.columns)
        self._view_source_columns = list(df.attrs.get("source_columns", df.columns))
        self.model = PandasModel(df, self._handle_cell_update)
        self.ui.tV_DataShow.setModel(self.model)
        self.ui.tV_DataShow.resizeColumnsToContents()

    def on_Transfer(self):
        if self._df.empty:
            QMessageBox.warning(self, "提示", "请先加载或更新数据。")
            return

        try:
            transfer_df = self._df.copy().reset_index(drop=True)
            if self.node.LoadData(transfer_df):
                self.node.eval()
                self.node.evalChildren()
                QMessageBox.information(
                    self,
                    "传递完成",
                    f"数据传递成功。\n共传递 {transfer_df.shape[0]} 行、{transfer_df.shape[1]} 列数据。",
                    QMessageBox.Ok,
                )
            else:
                QMessageBox.warning(
                    self,
                    "传递失败",
                    "数据传递过程中出现错误，请检查后重试。",
                    QMessageBox.Ok,
                )
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"数据传递失败：{exc}")


class PandasModel(QAbstractTableModel):
    def __init__(self, data: pd.DataFrame, update_callback=None):
        super().__init__()
        self._data = data if isinstance(data, pd.DataFrame) else pd.DataFrame()
        self._update_callback = update_callback

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        if role in (Qt.DisplayRole, Qt.EditRole):
            value = self._data.iloc[index.row(), index.column()]
            if pd.isna(value):
                return ""
            return str(value)
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or role != Qt.EditRole:
            return False

        if self._update_callback is not None:
            ok, result = self._update_callback(index.row(), index.column(), value)
            if not ok:
                return False
            new_value = result
        else:
            new_value = value

        self._data.iat[index.row(), index.column()] = new_value
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        return True

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._data.columns[section]
        if orientation == Qt.Vertical:
            return section + 1
        return None
