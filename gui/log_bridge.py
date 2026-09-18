"""
log_bridge.py
Handler logging dua nhat ky cua logger "Guzz" sang Qt Signal, de trang Chuyen
doi va trang Nhat ky hien thi truc tiep (lay tu GoogleAITranscribe).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal


class QtLogHandler(logging.Handler, QObject):
    dong_moi = Signal(str, int)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S")
        )

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        self.dong_moi.emit(msg, record.levelno)
