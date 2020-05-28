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

        self.buffer = b''    #串口接收缓存

        self.tmrSer = QtCore.QTimer()
        self.tmrSer.setInterval(10)
        self.tmrSer.timeout.connect(self.on_tmrSer_timeout)
        self.tmrSer.start()
    
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
        self.PlotData = [0]*1000

        self.PlotChart = QChart()
        self.PlotChart.legend().hide()

        self.ChartView = QChartView(self.PlotChart)
        self.ChartView.setVisible(False)
        self.vLayout0.insertWidget(0, self.ChartView)
        
        self.PlotCurve = QLineSeries()
        self.PlotCurve.setColor(Qt.red)
        self.PlotChart.addSeries(self.PlotCurve)

        self.PlotChart.createDefaultAxes()
        self.PlotChart.axisX().setLabelFormat('%d')

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
                self.buffer += self.ser.read(num)
                
                if self.chkWavShow.checkState() == Qt.Unchecked:
                    if self.chkHEXShow.isChecked():
                        text = ' '.join(f'{x:02X}' for x in self.buffer) + ' '
                        self.buffer = b''
                    else:
                        text = ''
                        while len(self.buffer) > 1:
                            if self.buffer[0] < 0x7F:
                                text += chr(self.buffer[0])
                                self.buffer = self.buffer[1:]
                            else:
                                try:
                                    hanzi = self.buffer[:2].decode('gbk')
                                except Exception as e:
                                    text += f'\\x{self.buffer[0]:02X}'
                                    self.buffer = self.buffer[1:]
                                else:
                                    text += hanzi
                                    self.buffer = self.buffer[2:]
                    
                    if len(self.txtMain.toPlainText()) > 25000: self.txtMain.clear()
                    self.txtMain.moveCursor(QtGui.QTextCursor.End)
                    self.txtMain.insertPlainText(text)
                
                else:
                    if self.buffer.rfind(b',') == -1: return

                    try:
                        d = [int(x) for x in self.buffer[0:self.buffer.rfind(b',')].split(b',')]
                        for x in d:
                            self.PlotData.pop(0)
                            self.PlotData.append(x)
                    except Exception as e:
                        self.buffer = b''
                        print(str(e))
                    else:
                        self.buffer = self.buffer[self.buffer.rfind(b',')+1:]
                    
                    points = [QtCore.QPoint(i, v) for i, v in enumerate(self.PlotData)]
                    
                    self.PlotCurve.replace(points)
                    self.PlotChart.axisX().setMax(len(self.PlotData))
                    self.PlotChart.axisY().setRange(min(self.PlotData), max(self.PlotData))
    
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
