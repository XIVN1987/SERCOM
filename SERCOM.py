#! python3
import os
import sys
import time
import queue
import socket
import datetime
import threading
import collections
import configparser

from PyQt5 import QtCore, QtGui, uic
from PyQt5.QtCore import pyqtSlot, Qt
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtChart import QChart, QChartView, QLineSeries

from serial import Serial
from serial.tools.list_ports import comports


'''
from SERCOM_UI import Ui_SERCOM
class SERCOM(QWidget, Ui_SERCOM):
    def __init__(self, parent=None):
        super(SERCOM, self).__init__(parent)
        
        self.setupUi(self)
'''
class SERCOM(QWidget):
    def __init__(self, parent=None):
        super(SERCOM, self).__init__(parent)
        
        uic.loadUi('SERCOM.ui', self)

        for port, desc, hwid in comports():
            self.cmbPort.addItem(f'{port} ({desc[:desc.index("(")]})')
        self.cmbPort.addItems(['UDP Client', 'UDP Server'])

        self.ser = Serial()

        self.initSetting()

        self.initQwtPlot()

        self.closed = True      # 通信接口是否关闭
        self.exited = False     # 应用程序是否退出

        self.rcvbuff = b''
        self.rcvfile = None

        self.rcvQueue = queue.Queue()

        threading.Thread(target=self.thread_sock_rcv).start()    # call sock.recvfrom() in on_tmrRecv_timeout will hang GUI

        self.tmrRecv = QtCore.QTimer()
        self.tmrRecv.setInterval(10)
        self.tmrRecv.timeout.connect(self.on_tmrRecv_timeout)
        self.tmrRecv.start()

        self.tmrRecv_Cnt = 0
        self.tmrRecv_Sav = 0
        self.AutoInterval = 0   # 自动发送时间间隔，单位 10ms
    
    def initSetting(self):
        if not os.path.exists('setting.ini'):
            open('setting.ini', 'w', encoding='utf-8')
        
        self.conf = configparser.ConfigParser()
        self.conf.read('setting.ini', encoding='utf-8')

        if not self.conf.has_section('serial'):
            self.conf.add_section('serial')
            self.conf.set('serial', 'port', 'COM0')
            self.conf.set('serial', 'baud', '57600')

            self.conf.add_section('network')
            self.conf.set('network', 'ip', '[]')
            self.conf.set('network', 'port', '9000')

            self.conf.add_section('encode')
            self.conf.set('encode', 'input', 'ASCII')
            self.conf.set('encode', 'output', 'ASCII')
            self.conf.set('encode', 'oenter', r'\r\n')  # output enter (line feed)

            self.conf.add_section('display')
            self.conf.set('display', 'ncurve', '4')
            self.conf.set('display', 'npoint', '1000')

            self.conf.add_section('others')
            self.conf.set('others', 'savedir', '.')
            self.conf.set('others', 'history', '11 22 33 AA BB CC')

        self.txtSend.setPlainText(self.conf.get('others', 'history'))

        self.savedir = self.conf.get('others', 'savedir')

        self.N_CURVE = int(self.conf.get('display', 'ncurve'), 10)
        self.N_POINT = int(self.conf.get('display', 'npoint'), 10)

        self.cmbICode.setCurrentIndex(self.cmbICode.findText(self.conf.get('encode', 'input')))
        self.cmbOCode.setCurrentIndex(self.cmbOCode.findText(self.conf.get('encode', 'output')))
        self.cmbEnter.setCurrentIndex(self.cmbEnter.findText(self.conf.get('encode', 'oenter')))

        index = self.cmbPort.findText(self.conf.get('serial', 'port'))
        self.cmbPort.setCurrentIndex(index if index != -1 else 0)
        self.cmbBaud.setCurrentIndex(self.cmbBaud.findText(self.conf.get('serial', 'baud')))

        ips = eval(self.conf.get('network', 'ip')) + socket.gethostbyname_ex(socket.gethostname())[2]
        self.cmbIP.addItems(list(collections.OrderedDict.fromkeys(ips[:20])))   # 保留顺序去重
        self.linPort.setText(self.conf.get('network', 'port'))

    def initQwtPlot(self):
        self.PlotData  = [[0]*self.N_POINT for i in range(self.N_CURVE)]
        self.PlotPoint = [[QtCore.QPointF(j, 0) for j in range(self.N_POINT)] for i in range(self.N_CURVE)]

        self.PlotChart = QChart()

        self.ChartView = QChartView(self.PlotChart)
        self.ChartView.setVisible(False)
        self.vLayout.insertWidget(0, self.ChartView)
        
        self.PlotCurve = [QLineSeries() for i in range(self.N_CURVE)]

    @pyqtSlot()
    def on_btnOpen_clicked(self):
        port = self.cmbPort.currentText()
        if self.closed:
            try:
                if port == 'UDP Server':
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    self.sock.bind((self.cmbIP.currentText(), int(self.linPort.text())))
                elif port == 'UDP Client':
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                else:
                    self.ser.timeout = 1
                    self.ser.xonxoff = 0
                    self.ser.port = self.cmbPort.currentText().split()[0]
                    self.ser.parity = self.cmbChek.currentText()[0]
                    self.ser.baudrate = int(self.cmbBaud.currentText())
                    self.ser.bytesize = int(self.cmbData.currentText())
                    self.ser.stopbits = int(self.cmbStop.currentText())
                    self.ser.open()

                if self.chkSave.isChecked():
                    self.rcvfile = open(os.path.join(self.savedir, datetime.datetime.now().strftime("rcv_%y%m%d%H%M%S.txt")), 'w')
            
            except Exception as e:
                self.txtMain.clear()
                self.txtMain.insertPlainText(str(e))
            
            else:
                self.closed = False

                self.cmbPort.setEnabled(False)

                if port == 'UDP Server':
                    self.btnOpen.setText('停止监听')
                elif port == 'UDP Client':
                    self.btnOpen.setText('断开连接')
                else:
                    self.btnOpen.setText('关闭串口')

                if port in ('UDP Server', 'UDP Client'):
                    self.cmbIP.setEnabled(False)
                    self.linPort.setEnabled(False)

        else:
            self.closed = True

            self.cmbPort.setEnabled(True)

            if port == 'UDP Server':
                self.btnOpen.setText('开启监听')
            elif port == 'UDP Client':
                self.btnOpen.setText('建立连接')
            else:
                self.btnOpen.setText('打开串口')

            if port in ('UDP Server', 'UDP Client'):
                    self.cmbIP.setEnabled(True)
                    self.linPort.setEnabled(True)

            if self.rcvfile and not self.rcvfile.closed:
                self.rcvfile.close()
            
            if port in ('UDP Server', 'UDP Client'):
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except Exception as e:
                    print(e)
                
                try:
                    self.sock.close()
                except Exception as e:
                    print(e)

            else:
                self.ser.close()
    
    @pyqtSlot()
    def on_btnSend_clicked(self):
        if not self.closed:
            text = self.txtSend.toPlainText()
            try:
                if self.cmbOCode.currentText() == 'HEX':
                    bstr = bytes([int(x, 16) for x in text.split()])   # for example, text = '55 AA 5A'
                else:
                    text = text.replace('\n', self.cmbEnter.currentText().replace(r'\r', '\r').replace(r'\n', '\n'))
                    bstr = text.encode(self.cmbOCode.currentText())
            except Exception as e:
                print(e)
                return

            port = self.cmbPort.currentText()
            try:
                if port == 'UDP Server':
                    self.sock.sendto(bstr, self.clinAddr)
                elif port == 'UDP Client':
                    self.sock.sendto(bstr, (self.cmbIP.currentText(), int(self.linPort.text())))
                else:
                    self.ser.write(bstr)
            except Exception as e:
                print(e)
    
    def thread_sock_rcv(self):
        while not self.exited:
            port = self.cmbPort.currentText()
            if not self.closed:
                try:
                    if port == 'UDP Server':
                        rcvdbytes, self.clinAddr = self.sock.recvfrom(1024)
                        self.rcvQueue.put(rcvdbytes)

                    elif port == 'UDP Client':
                        rcvdbytes, addr = self.sock.recvfrom(1024)
                        self.rcvQueue.put(rcvdbytes)

                except Exception as e:
                    print(e)

            time.sleep(0.01)

    def on_tmrRecv_timeout(self):
        self.tmrRecv_Cnt += 1
        
        port = self.cmbPort.currentText()
        if not self.closed:
            try:
                if port in ('UDP Server', 'UDP Client'):
                    rcvdbytes = self.rcvQueue.get(block=False)
                else:
                    rcvdbytes = self.ser.read(self.ser.in_waiting)
            except Exception as e:
                rcvdbytes = b''

            if rcvdbytes:
                if self.rcvfile and not self.rcvfile.closed:
                    self.rcvfile.write(rcvdbytes.decode('latin-1'))
                
                self.rcvbuff += rcvdbytes
                
                if self.chkWave.isChecked():
                    if b',' in self.rcvbuff:
                        try:
                            d = self.rcvbuff[0:self.rcvbuff.rfind(b',')].split(b',')        # [b'12', b'34'] or [b'12 34', b'56 78']
                            if self.cmbICode.currentText() != 'HEX':
                                d = [[float(x)   for x in X.strip().split()] for X in d]    # [[12], [34]]   or [[12, 34], [56, 78]]
                            else:
                                d = [[int(x, 16) for x in X.strip().split()] for X in d]    # for example, d = [b'12', b'AA', b'5A5A']
                            for arr in d:
                                for i, x in enumerate(arr):
                                    if i == self.N_CURVE: break

                                    self.PlotData[i].pop(0)
                                    self.PlotData[i].append(x)
                                    self.PlotPoint[i].pop(0)
                                    self.PlotPoint[i].append(QtCore.QPointF(999, x))
                            
                            self.rcvbuff = self.rcvbuff[self.rcvbuff.rfind(b',')+1:]

                            if self.tmrRecv_Cnt - self.tmrRecv_Sav > 3:
                                self.tmrRecv_Sav = self.tmrRecv_Cnt
                                if len(d[-1]) != len(self.PlotChart.series()):
                                    for series in self.PlotChart.series():
                                        self.PlotChart.removeSeries(series)
                                    for i in range(min(len(d[-1]), self.N_CURVE)):
                                        self.PlotCurve[i].setName(f'Curve {i+1}')
                                        self.PlotChart.addSeries(self.PlotCurve[i])
                                    self.PlotChart.createDefaultAxes()

                                for i in range(len(self.PlotChart.series())):
                                    for j, point in enumerate(self.PlotPoint[i]):
                                        point.setX(j)
                                
                                    self.PlotCurve[i].replace(self.PlotPoint[i])
                                
                                miny = min([min(d) for d in self.PlotData[:len(self.PlotChart.series())]])
                                maxy = max([max(d) for d in self.PlotData[:len(self.PlotChart.series())]])
                                self.PlotChart.axisY().setRange(miny, maxy)
                                self.PlotChart.axisX().setRange(0000, self.N_POINT)
                        
                        except Exception as e:
                            self.rcvbuff = b''
                            print(e)

                else:
                    text = ''
                    if self.cmbICode.currentText() == 'ASCII':
                        text = ''.join([chr(x) for x in self.rcvbuff])
                        self.rcvbuff = b''

                    elif self.cmbICode.currentText() == 'HEX':
                        text = ' '.join([f'{x:02X}' for x in self.rcvbuff]) + ' '
                        self.rcvbuff = b''

                    elif self.cmbICode.currentText() == 'GBK':
                        while len(self.rcvbuff):
                            if self.rcvbuff[0:1].decode('GBK', 'ignore'):
                                text += self.rcvbuff[0:1].decode('GBK')
                                self.rcvbuff = self.rcvbuff[1:]

                            elif len(self.rcvbuff) > 1 and self.rcvbuff[0:2].decode('GBK', 'ignore'):
                                text += self.rcvbuff[0:2].decode('GBK')
                                self.rcvbuff = self.rcvbuff[2:]

                            elif len(self.rcvbuff) > 1:
                                text += chr(self.rcvbuff[0])
                                self.rcvbuff = self.rcvbuff[1:]

                            else:
                                break

                    elif self.cmbICode.currentText() == 'UTF-8':
                        while len(self.rcvbuff):
                            if self.rcvbuff[0:1].decode('UTF-8', 'ignore'):
                                text += self.rcvbuff[0:1].decode('UTF-8')
                                self.rcvbuff = self.rcvbuff[1:]

                            elif len(self.rcvbuff) > 1 and self.rcvbuff[0:2].decode('UTF-8', 'ignore'):
                                text += self.rcvbuff[0:2].decode('UTF-8')
                                self.rcvbuff = self.rcvbuff[2:]

                            elif len(self.rcvbuff) > 2 and self.rcvbuff[0:3].decode('UTF-8', 'ignore'):
                                text += self.rcvbuff[0:3].decode('UTF-8')
                                self.rcvbuff = self.rcvbuff[3:]

                            elif len(self.rcvbuff) > 3 and self.rcvbuff[0:4].decode('UTF-8', 'ignore'):
                                text += self.rcvbuff[0:4].decode('UTF-8')
                                self.rcvbuff = self.rcvbuff[4:]

                            elif len(self.rcvbuff) > 3:
                                text += chr(self.rcvbuff[0])
                                self.rcvbuff = self.rcvbuff[1:]

                            else:
                                break
                    
                    if len(self.txtMain.toPlainText()) > 25000: self.txtMain.clear()
                    self.txtMain.moveCursor(QtGui.QTextCursor.End)
                    self.txtMain.insertPlainText(text)

            if self.AutoInterval and self.tmrRecv_Cnt % self.AutoInterval == 0:
                self.on_btnSend_clicked()

        else:
            if self.tmrRecv_Cnt % 100 == 0:
                if len(comports()) + 2 != self.cmbPort.count():
                    self.cmbPort.clear()
                    for port, desc, hwid in comports():
                        self.cmbPort.addItem(f'{port} ({desc[:desc.index("(")]})')
                    self.cmbPort.addItems(['UDP Client', 'UDP Server'])

    @pyqtSlot(int)
    def on_chkWave_stateChanged(self, state):
        self.ChartView.setVisible(state == Qt.Checked)
        self.txtMain.setVisible(state == Qt.Unchecked)
    
    @pyqtSlot(str)
    def on_cmbPort_currentIndexChanged(self, text):
        if text in ('UDP Client', 'UDP Server'):
            self.hWidget2.setVisible(False)
            self.hLayout2.removeWidget(self.btnClear)
            self.hLayout2.removeWidget(self.chkSave)

            self.hLayout3.addWidget(self.btnClear)
            self.hLayout3.addWidget(self.chkSave)
            self.hWidget3.setVisible(True)

            self.cmbBaud.setEnabled(False)

            if 'Server' in text:
                self.btnOpen.setText('开启监听')
            else:
                self.btnOpen.setText('建立连接')

        else:
            self.hWidget3.setVisible(False)
            self.hLayout3.removeWidget(self.btnClear)
            self.hLayout3.removeWidget(self.chkSave)

            self.hLayout2.addWidget(self.btnClear)
            self.hLayout2.addWidget(self.chkSave)
            self.hWidget2.setVisible(True)

            self.cmbBaud.setEnabled(True)

            self.btnOpen.setText('打开串口')

    @pyqtSlot(str)
    def on_cmbBaud_currentIndexChanged(self, text):
        self.ser.baudrate = int(text)
    
    @pyqtSlot(str)
    def on_cmbData_currentIndexChanged(self, text):
        self.ser.bytesize = int(text)
    
    @pyqtSlot(str)
    def on_cmbChek_currentIndexChanged(self, text):
        self.ser.parity = text[0]
    
    @pyqtSlot(str)
    def on_cmbStop_currentIndexChanged(self, text):
        self.ser.stopbits = int(text)
    
    @pyqtSlot(str)
    def on_cmbAuto_currentIndexChanged(self, text):
        if text == 'NO Auto':
            self.AutoInterval = 0

        elif text.endswith('s'):
            self.AutoInterval = float(text[:-1]) * 100

        elif text.endswith('m'):
            self.AutoInterval = float(text[:-1]) * 100 * 60

        self.AutoInterval = int(self.AutoInterval)

    @pyqtSlot()
    def on_btnClear_clicked(self):
        self.txtMain.clear()
    
    def closeEvent(self, evt):
        if self.rcvfile and not self.rcvfile.closed:
            self.rcvfile.close()

        self.exited = True

        self.ser.close()

        self.conf.set('serial', 'port', self.cmbPort.currentText())
        self.conf.set('serial', 'baud', self.cmbBaud.currentText())
        self.conf.set('encode', 'input', self.cmbICode.currentText())
        self.conf.set('encode', 'output', self.cmbOCode.currentText())
        self.conf.set('encode', 'oenter', self.cmbEnter.currentText())
        self.conf.set('others', 'history', self.txtSend.toPlainText())

        self.conf.set('network', 'ip', repr([self.cmbIP.currentText()] + [self.cmbIP.itemText(i) for i in range(self.cmbIP.count())]))
        self.conf.set('network', 'port', self.linPort.text())

        self.conf.write(open('setting.ini', 'w', encoding='utf-8'))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ser = SERCOM()
    ser.show()
    app.exec_()
