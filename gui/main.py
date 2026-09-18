"""
main.py
App GUI cua Guzz (giao dien Fluent giong GoogleAITranscribe, PySide6-Fluent-Widgets).

    runtime\\python\\pythonw.exe gui\\main.py                 # mo cua so
    runtime\\python\\pythonw.exe gui\\main.py "a.m4a" "b.mp3" # mo va them san file vao danh sach

Chi mot ban chay cung luc: ban thu hai ket noi toi QLocalServer cua ban dang
chay, gui danh sach file (neu co) roi tu thoat. Nho vay "Open with Guzz" hay keo
file tha len shortcut deu vao chung mot danh sach.
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paths  # noqa: E402,F401  (dua APP_DIR va gui\ vao sys.path)

from PySide6.QtCore import QProcess, QRect, QTimer  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtNetwork import QLocalServer, QLocalSocket  # noqa: E402
from PySide6.QtWidgets import QApplication, QSystemTrayIcon  # noqa: E402
from qfluentwidgets import (  # noqa: E402
    FluentIcon, FluentWindow, InfoBar, InfoBarPosition, MessageBox, NavigationItemPosition, PushButton,
)

import cau_hinh as chh  # noqa: E402
import chuyen_doi as cd  # noqa: E402
import google_ai as ga  # noqa: E402
import han_muc  # noqa: E402
import win_taskbar  # noqa: E402
from i18n import bo_dich, dat_ngon_ngu, tr  # noqa: E402
from log_bridge import QtLogHandler  # noqa: E402
from paths import APP_DIR, CONFIG_PATH, DATA_DIR, ICON_PATH, PHIEN_BAN, dam_bao_du_lieu  # noqa: E402
from su_kien import doc_trang_thai, ghi_trang_thai, su_kien  # noqa: E402

from pages.audio import TrangAmThanh  # noqa: E402
from pages.chuyen_doi import TrangChuyenDoi  # noqa: E402
from pages.google_ai import TrangGoogleAI  # noqa: E402
from pages.han_muc import TrangHanMuc  # noqa: E402
from pages.logs import TrangNhatKy  # noqa: E402
from pages.nguoi_noi import TrangNguoiNoi  # noqa: E402
from pages.settings import TrangCaiDat, ap_dung_giao_dien  # noqa: E402

KHOA_INSTANCE_DUY_NHAT = "Guzz_SingleInstance_v1"


def _doc_cau_hinh_an_toan() -> chh.CauHinh:
    try:
        return chh.doc_cau_hinh(CONFIG_PATH)
    except Exception:
        return chh.CauHinh()


def _gui_cho_ban_dang_chay(cac_file: list[str]) -> bool:
    """Tra ve True neu da co mot ban dang chay (va da gui danh sach file cho no)."""
    socket = QLocalSocket()
    socket.connectToServer(KHOA_INSTANCE_DUY_NHAT)
    if not socket.waitForConnected(300):
        return False
    socket.write(("\n".join(cac_file) or "\n").encode("utf-8"))
    socket.flush()
    socket.waitForBytesWritten(1000)
    socket.disconnectFromServer()
    return True


class CuaSoChinh(FluentWindow):
    def __init__(self, ch: chh.CauHinh):
        super().__init__()
        self.setWindowIcon(QIcon(ICON_PATH))
        self.resize(1120, 800)
        self.setMinimumSize(900, 620)
        self.tray: QSystemTrayIcon | None = None

        self.log_handler = QtLogHandler()
        self._cai_dat_log(ch)

        self.trang_chuyen_doi = TrangChuyenDoi(self.log_handler, self)
        self.trang_am_thanh = TrangAmThanh(self)
        self.trang_google = TrangGoogleAI(self)
        self.trang_nguoi_noi = TrangNguoiNoi(self)
        self.trang_han_muc = TrangHanMuc(self)
        self.trang_nhat_ky = TrangNhatKy(self.log_handler, self)
        self.trang_cai_dat = TrangCaiDat(self)

        self._cac_trang = [
            (self.trang_chuyen_doi, FluentIcon.MICROPHONE, "nav_convert", NavigationItemPosition.TOP),
            (self.trang_am_thanh, FluentIcon.MUSIC, "nav_audio", NavigationItemPosition.TOP),
            (self.trang_google, FluentIcon.ROBOT, "nav_google", NavigationItemPosition.TOP),
            (self.trang_nguoi_noi, FluentIcon.PEOPLE, "nav_speakers", NavigationItemPosition.TOP),
            (self.trang_han_muc, FluentIcon.SPEED_MEDIUM, "nav_usage", NavigationItemPosition.TOP),
            (self.trang_nhat_ky, FluentIcon.HISTORY, "nav_logs", NavigationItemPosition.TOP),
            (self.trang_cai_dat, FluentIcon.SETTING, "nav_settings", NavigationItemPosition.BOTTOM),
        ]
        for trang, icon, key, vi_tri in self._cac_trang:
            self.addSubInterface(trang, icon, tr(key), vi_tri)
        self._ten_trang = {"google": self.trang_google, "nguoi_noi": self.trang_nguoi_noi,
                           "am_thanh": self.trang_am_thanh, "cai_dat": self.trang_cai_dat,
                           "han_muc": self.trang_han_muc, "nhat_ky": self.trang_nhat_ky}

        self.setWindowTitle(tr("app_title"))
        self.setMicaEffectEnabled(ch.mica)
        # Phai dat truoc show() thi nut taskbar moi lay dung icon. Xem win_taskbar.
        win_taskbar.dat_app_id_cua_so(int(self.winId()))
        if ch.nho_cua_so:
            self._lay_lai_vi_tri()

        self.trang_chuyen_doi.het_hang_doi.connect(self._thong_bao_xong)
        for trang in (self.trang_chuyen_doi, self.trang_nguoi_noi, self.trang_han_muc):
            trang.can_mo_trang.connect(lambda ten: self.switchTo(self._ten_trang[ten]))
        self.trang_cai_dat.can_khoi_dong_lai.connect(self._khoi_dong_lai)
        self.trang_cai_dat.doi_mica.connect(self.setMicaEffectEnabled)
        bo_dich.doi_ngon_ngu.connect(self._doi_ngon_ngu)
        self._tao_local_server()
        QTimer.singleShot(800, self._nhac_api_key)

        # Luong chuyen doi khoa / mo khoa model, hoac khoa tu het han: bao cac trang ve lai o chon model.
        self._dau_hieu_han_muc = han_muc.so_theo_doi().dau_hieu()
        self.dong_ho_han_muc = QTimer(self)
        self.dong_ho_han_muc.setInterval(1000)
        self.dong_ho_han_muc.timeout.connect(self._kiem_tra_han_muc)
        self.dong_ho_han_muc.start()

    def _kiem_tra_han_muc(self):
        dau_hieu = han_muc.so_theo_doi().dau_hieu()
        if dau_hieu != self._dau_hieu_han_muc:
            self._dau_hieu_han_muc = dau_hieu
            su_kien.han_muc_doi.emit()

    def _cai_dat_log(self, ch: chh.CauHinh):
        try:
            cd.cai_dat_log(ch)
        except Exception as e:
            print(f"Khong cai duoc nhat ky: {e}", file=sys.stderr)
        cd.log.addHandler(self.log_handler)
        if not cd.log.level:
            cd.log.setLevel(logging.INFO)
        cd.log.info("=" * 70)
        cd.log.info("Guzz %s khoi dong. Du lieu: %s", PHIEN_BAN, DATA_DIR)

    # ------------------------------------------------------------ cua so

    def _lay_lai_vi_tri(self):
        tt = doc_trang_thai().get("cua_so")
        if not isinstance(tt, dict):
            return
        man_hinh = QApplication.primaryScreen().availableVirtualGeometry()
        x, y, w, h = (int(tt.get(k, 0)) for k in ("x", "y", "w", "h"))
        # Man hinh phu da rut ra thi khong dat cua so ra ngoai vung nhin thay.
        if w >= 900 and h >= 620 and man_hinh.intersects(QRect(x, y, w, h).adjusted(40, 40, -40, -40)):
            self.setGeometry(x, y, w, h)
        if tt.get("phong_to"):
            self.showMaximized()

    def _luu_vi_tri(self):
        g = self.normalGeometry() if self.isMaximized() else self.geometry()
        ghi_trang_thai(cua_so={"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height(),
                               "phong_to": self.isMaximized()})

    def them_file(self, cac_file: list[str]):
        if cac_file:
            self.switchTo(self.trang_chuyen_doi)
            self.trang_chuyen_doi.them_file(cac_file)

    def _nhac_api_key(self):
        if ga.lay_api_key():
            return
        thanh = InfoBar.warning(tr("app_title"), tr("conv_no_key"), parent=self.trang_chuyen_doi,
                                position=InfoBarPosition.TOP, duration=10000)
        nut = PushButton(tr("conv_go_google"))
        nut.clicked.connect(lambda: self.switchTo(self.trang_google))
        thanh.addWidget(nut)

    # ------------------------------------------------------------ mot ban duy nhat

    def _tao_local_server(self):
        QLocalServer.removeServer(KHOA_INSTANCE_DUY_NHAT)
        self.local_server = QLocalServer(self)
        self.local_server.listen(KHOA_INSTANCE_DUY_NHAT)
        self.local_server.newConnection.connect(self._ket_noi_moi)

    def _ket_noi_moi(self):
        socket = self.local_server.nextPendingConnection()
        if not socket:
            return
        du_lieu = b""
        if socket.bytesAvailable() > 0 or socket.waitForReadyRead(500):
            du_lieu = bytes(socket.readAll().data())
            while socket.waitForReadyRead(100):
                du_lieu += bytes(socket.readAll().data())
        socket.disconnectFromServer()
        self.showNormal()
        self.activateWindow()
        self.raise_()
        self.them_file([p for p in du_lieu.decode("utf-8", "replace").splitlines() if p.strip()])

    # ------------------------------------------------------------ thong bao

    def _thong_bao_xong(self, so_xong: int, so_loi: int, bi_dung: bool):
        if bi_dung:
            return
        ch = _doc_cau_hinh_an_toan()
        if ch.am_bao_khi_xong:
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION if so_loi else winsound.MB_ICONASTERISK)
            except Exception:
                QApplication.beep()
        if not ch.thong_bao_khi_xong:
            return
        QApplication.alert(self, 0)
        if self.isActiveWindow():
            return
        # Windows chi hien thong bao cua mot icon dang nam o khay; icon tu an khi mo lai cua so.
        if self.tray is None:
            self.tray = QSystemTrayIcon(QIcon(ICON_PATH), self)
            self.tray.setToolTip(tr("app_title"))
            self.tray.activated.connect(lambda _: (self.showNormal(), self.activateWindow()))
            self.tray.messageClicked.connect(lambda: (self.showNormal(), self.activateWindow()))
        self.tray.show()
        self.tray.showMessage(tr("app_title"), tr("notify_done", so_xong, so_loi),
                              QSystemTrayIcon.MessageIcon.Warning if so_loi else QSystemTrayIcon.MessageIcon.Information,
                              8000)

    def changeEvent(self, e):
        super().changeEvent(e)
        # FluentWindow goi changeEvent ngay trong __init__ cua lop cha, truoc khi co self.tray.
        if getattr(self, "tray", None) is not None and self.isActiveWindow():
            QTimer.singleShot(3000, lambda: self.tray.hide() if self.isActiveWindow() else None)

    # ------------------------------------------------------------ thoat

    def closeEvent(self, event):
        if self.trang_chuyen_doi.dang_chay():
            hop = MessageBox(tr("close_title"), tr("close_body"), self)
            hop.yesButton.setText(tr("close_yes"))
            hop.cancelButton.setText(tr("common_cancel"))
            if not hop.exec():
                event.ignore()
                return
            self.trang_chuyen_doi.yeu_cau_dung_va_cho(20000)
        if _doc_cau_hinh_an_toan().nho_cua_so:
            self._luu_vi_tri()
        self._don_dep()
        event.accept()
        super().closeEvent(event)

    def _don_dep(self):
        try:
            self.local_server.close()
            QLocalServer.removeServer(KHOA_INSTANCE_DUY_NHAT)
        except Exception:
            pass
        if self.tray is not None:
            self.tray.hide()

    def _khoi_dong_lai(self):
        if self.trang_chuyen_doi.dang_chay():
            InfoBar.warning(tr("app_title"), tr("restart_busy"), parent=self.stackedWidget.currentWidget(),
                            position=InfoBarPosition.TOP)
            return
        if _doc_cau_hinh_an_toan().nho_cua_so:
            self._luu_vi_tri()
        self._don_dep()
        QProcess.startDetached(sys.executable, [os.path.abspath(__file__)], APP_DIR)
        QApplication.instance().quit()

    def _doi_ngon_ngu(self, _ma):
        self.setWindowTitle(tr("app_title"))
        for trang, _, key, _ in self._cac_trang:
            item = self.navigationInterface.widget(trang.objectName())
            if item:
                item.setText(tr(key))


def main():
    loi_du_lieu = None
    try:
        dam_bao_du_lieu()
    except OSError as e:
        loi_du_lieu = e
    ch = _doc_cau_hinh_an_toan()
    if ch.ty_le != "auto":
        os.environ["QT_SCALE_FACTOR"] = ch.ty_le
    win_taskbar.dat_app_id_tien_trinh()

    app = QApplication(sys.argv)
    app.setApplicationName("Guzz")
    app.setWindowIcon(QIcon(ICON_PATH))

    cac_file = [os.path.abspath(a) for a in sys.argv[1:] if os.path.exists(a)]
    if _gui_cho_ban_dang_chay(cac_file):
        sys.exit(0)

    dat_ngon_ngu(ch.ngon_ngu_giao_dien)
    ap_dung_giao_dien(ch)

    cua_so = CuaSoChinh(ch)
    cua_so.show()
    if loi_du_lieu:
        cd.log.error("Khong tao duoc thu muc du lieu %s: %s", DATA_DIR, loi_du_lieu)
    if cac_file:
        cua_so.them_file(cac_file)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
