# gui/worker.py (全新文件)

import traceback
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable

class WorkerSignals(QObject):
    """
    定义从工作线程发出的信号。
    - finished: 当工作完成时发出。
    - error: 当发生错误时发出。
    - result: 发出计算结果。
    """
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)

class Worker(QRunnable):
    """
    一个可运行的工作线程，用于执行耗时任务。
    它接收一个函数和其参数，并在一个独立的线程中运行它。
    """
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        """
        在线程池中执行任务的核心逻辑。
        """
        try:
            # 执行传入的函数
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            # 如果函数执行出错，捕获异常并通过 'error' 信号发送出去
            traceback.print_exc()
            self.signals.error.emit((type(e), e, traceback.format_exc()))
        else:
            # 如果函数成功执行，通过 'result' 信号发送结果
            self.signals.result.emit(result)
        finally:
            # 无论成功还是失败，最后都发送 'finished' 信号
            self.signals.finished.emit()
