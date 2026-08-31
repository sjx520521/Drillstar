from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtWidgets import QApplication, QProgressDialog


class FunctionWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class BusyTaskMixin:
    def _start_background_task(self, title, text, func, on_success, on_error=None, *args, **kwargs):
        if getattr(self, "_busy_worker", None) is not None and self._busy_worker.isRunning():
            return False

        dialog = QProgressDialog(text, "", 0, 0, self)
        dialog.setWindowTitle(title)
        dialog.setWindowModality(Qt.ApplicationModal)
        dialog.setCancelButton(None)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setValue(0)

        worker = FunctionWorker(func, *args, **kwargs)
        self._busy_dialog = dialog
        self._busy_worker = worker

        def _cleanup():
            if getattr(self, "_busy_dialog", None) is not None:
                self._busy_dialog.close()
                self._busy_dialog.deleteLater()
                self._busy_dialog = None
            QApplication.restoreOverrideCursor()
            self._busy_worker = None

        def _handle_success(result):
            _cleanup()
            on_success(result)

        def _handle_error(message):
            _cleanup()
            if on_error is not None:
                on_error(message)

        worker.succeeded.connect(_handle_success)
        worker.failed.connect(_handle_error)
        worker.finished.connect(worker.deleteLater)

        QApplication.setOverrideCursor(Qt.WaitCursor)
        dialog.show()
        worker.start()
        return True
