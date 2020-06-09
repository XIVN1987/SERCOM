#! python3
import os
import sys
import configparser

from PyQt5 import QtCore, QtGui, uic
from PyQt5.QtCore import pyqtSlot, Qt
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtChart import QChart, QChartView, QLineSeries

from serial import Serial
from serial.tools.list_ports import comports

N_CURVES = 4


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

        self.ser = Serial()

        self.initSetting()

        self.initQwtPlot()

        self.rcvbuff = b''

        self.tmrSer = QtCore.QTimer()
        self.tmrSer.setInterval(10)
        self.tmrSer.timeout.connect(self.on_tmrSer_timeout)
        self.tmrSer.start()

        self.tmrSer_Cnt = 0
    
    def initSetting(self):
        if not os.path.exists('setting.ini'):
            open('setting.ini', 'w', encoding='utf-8')
        
        self.conf = configparser.ConfigParser()
        self.conf.read('setting.ini', encoding='utf-8')

        if not self.conf.has_section('serial'):
            self.conf.add_section('serial')
            self.conf.set('serial', 'port', 'COM0')
            self.conf.set('serial', 'baud', '9600')

            self.conf.add_section('history')
            self.conf.set('history', 'hist1', '')
            self.conf.set('history', 'hist2', '')

        self.txtSend.setPlainText(self.conf.get('history', 'hist1'))

        index = self.cmbPort.findText(self.conf.get('serial', 'port'))
        self.cmbPort.setCurrentIndex(index if index != -1 else 0)
        self.cmbBaud.setCurrentIndex(self.cmbBaud.findText(self.conf.get('serial', 'baud')))
    
    def initQwtPlot(self):
        self.PlotData  = [[0]*1000 for i in range(N_CURVES)]
        self.PlotPoint = [[QtCore.QPointF(j, 0) for j in range(1000)] for i in range(N_CURVES)]

        self.PlotChart = QChart()

        self.ChartView = QChartView(self.PlotChart)
        self.ChartView.setVisible(False)
        self.vLayout0.insertWidget(0, self.ChartView)
        
        self.PlotCurve = [QLineSeries() for i in range(N_CURVES)]

    @pyqtSlot()
    def on_btnOpen_clicked(self):
        if not self.ser.is_open:
            try:
                self.ser.timeout = 1
                self.ser.xonxoff = 0
                self.ser.port = self.cmbPort.currentText().split()[0]
                self.ser.parity = self.cmbChek.currentText()[0]
                self.ser.baudrate = int(self.cmbBaud.currentText())
                self.ser.bytesize = int(self.cmbData.currentText())
                self.ser.stopbits = int(self.cmbStop.currentText())
                self.ser.open()
            except Exception as e:
                self.txtMain.clear()
                self.txtMain.insertPlainText(str(e))
            else:
                self.cmbPort.setEnabled(False)
                self.btnOpen.setText('关闭串口')
        else:
            self.ser.close()

            self.cmbPort.setEnabled(True)
            self.btnOpen.setText('打开串口')
    
    @pyqtSlot()
    def on_btnSend_clicked(self):
        if self.ser.is_open:
            text = self.txtSend.toPlainText()
            if self.chkHEXSend.isChecked():
                try:
                    text = ' '.join([chr(int(x,16)) for x in text.split()])
                except Exception as e:
                    print(e)
            else:
                text = text.replace('\n', '\r\n')
            
            self.ser.write(text.encode('latin'))
    
    def on_tmrSer_timeout(self):        
        if self.ser.is_open:
            num = self.ser.in_waiting
            if num > 0:
                self.rcvbuff += self.ser.read(num)
                
                if self.chkWavShow.checkState() == Qt.Unchecked:
                    if self.chkHEXShow.isChecked():
                        text = ' '.join(f'{x:02X}' for x in self.rcvbuff) + ' '
                        self.rcvbuff = b''
                    
                    else:
                        text = ''
                        while len(self.rcvbuff) > 1:
                            if self.rcvbuff[0] < 0x7F:
                                text += chr(self.rcvbuff[0])
                                self.rcvbuff = self.rcvbuff[1:]
                            
                            else:
                                try:
                                    hanzi = self.rcvbuff[:2].decode('gbk')
                                except Exception as e:
                                    text += f'\\x{self.rcvbuff[0]:02X}'
                                    self.rcvbuff = self.rcvbuff[1:]
                                else:
                                    text += hanzi
                                    self.rcvbuff = self.rcvbuff[2:]
                    
                    if len(self.txtMain.toPlainText()) > 25000: self.txtMain.clear()
                    self.txtMain.moveCursor(QtGui.QTextCursor.End)
                    self.txtMain.insertPlainText(text)
                
                else:
                    if self.rcvbuff.rfind(b',') == -1: return

                    try:
                        d = self.rcvbuff[0:self.rcvbuff.rfind(b',')].split(b',')    # [b'12', b'34'] or [b'12 34', b'56 78']
                        d = [[float(x) for x in X.strip().split()] for X in d]      # [[12], [34]]   or [[12, 34], [56, 78]]
                        for arr in d:
                            for i, x in enumerate(arr):
                                if i == N_CURVES: break

                                self.PlotData[i].pop(0)
                                self.PlotData[i].append(x)
                                self.PlotPoint[i].pop(0)
                                self.PlotPoint[i].append(QtCore.QPointF(999, x))
                        
                        self.rcvbuff = self.rcvbuff[self.rcvbuff.rfind(b',')+1:]

                        self.tmrSer_Cnt += 1
                        if self.tmrSer_Cnt % 4 == 0:
                            if len(d[-1]) != len(self.PlotChart.series()):
                                for series in self.PlotChart.series():
                                    self.PlotChart.removeSeries(series)
                                for i in range(min(len(d[-1]), N_CURVES)):
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
                            self.PlotChart.axisX().setRange(0000, 1000)
                    
                    except Exception as e:
                        self.rcvbuff = b''
                        print(e)
    
    @pyqtSlot(int)
    def on_chkWavShow_stateChanged(self, state):
        self.ChartView.setVisible(state == Qt.Checked)
        self.txtMain.setVisible(state == Qt.Unchecked)
    
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
    
    @pyqtSlot()
    def on_btnClear_clicked(self):
        self.txtMain.clear()
    
    def closeEvent(self, evt):
        self.ser.close()

        self.conf.set('serial', 'port', self.cmbPort.currentText())
        self.conf.set('serial', 'baud', self.cmbBaud.currentText())
        self.conf.set('history', 'hist1', self.txtSend.toPlainText())
        self.conf.write(open('setting.ini', 'w', encoding='utf-8'))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ser = SERCOM()
    ser.show()
    app.exec_()
