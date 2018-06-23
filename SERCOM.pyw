#coding: utf-8
''' 升级记录
2015.07.27  1、添加波特率记录功能
            2、整理编码相关内容：setting.ini文件为GBK编码（Win系统下建立文件的默认编码）、
            Qt控件间为Unicode、串口发送和接收为GBK编码的字节流
2015.07.28  1、添加closeEvent，把对setting.ini的写全部移到此函数中去
2015.11.24  1、self.PlotBuff += text下添加if self.PlotBuff.rfind(',') == -1: return
'''
import os
import sys
import ConfigParser

import sip
sip.setapi('QString', 2)
from PyQt4 import QtCore, QtGui, uic
from PyQt4.Qwt5 import QwtPlot, QwtPlotCurve

from serial import Serial
from serial.tools.list_ports import comports


'''
class SERCOM(QtGui.QWidget):
    def __init__(self, parent=None):
        super(SERCOM, self).__init__(parent)
        
        uic.loadUi('SERCOM.ui', self)
'''
from SERCOM_UI import Ui_SERCOM
class SERCOM(QtGui.QWidget, Ui_SERCOM):
    def __init__(self, parent=None):
        super(SERCOM, self).__init__(parent)
        
        self.setupUi(self)

        for port, desc, hwid in comports(): self.cmbCOMM.addItem(port)

        self.ser = Serial()

        self.initSetting()

        self.initQwtPlot()

        self.buffer = ''    #串口接收缓存

        self.tmrSer = QtCore.QTimer()
        self.tmrSer.setInterval(20)
        self.tmrSer.timeout.connect(self.on_tmrSer_timeout)
        self.tmrSer.start()
    
    def initSetting(self):
        if not os.path.exists('setting.ini'):
            open('setting.ini', 'w')
        
        self.conf = ConfigParser.ConfigParser()
        self.conf.read('setting.ini')
        
        if not self.conf.has_section('globals'):
            self.conf.add_section('globals')
            self.conf.set('globals', 'serial',   'COM0')
            self.conf.set('globals', 'baudrate', '9600')
            self.conf.set('globals', 'historys', '[]')
        index = self.cmbCOMM.findText(self.conf.get('globals', 'serial'))
        self.cmbCOMM.setCurrentIndex(index if index != -1 else 0)
        self.cmbBaud.setCurrentIndex(self.cmbBaud.findText(self.conf.get('globals', 'baudrate')))
        for text in eval(self.conf.get('globals', 'historys')): self.cmbSend.insertItem(10, text)
    
    def initQwtPlot(self):
        self.PlotBuff = ''
        self.PlotData = [0]*1000
        
        self.qwtPlot = QwtPlot(self)
        self.vLayout0.insertWidget(0, self.qwtPlot)
        
        self.PlotCurve = QwtPlotCurve()
        self.PlotCurve.attach(self.qwtPlot)
        self.PlotCurve.setData(range(1, len(self.PlotData)+1), self.PlotData)

        self.on_cmbMode_currentIndexChanged(u'文本')

    @QtCore.pyqtSlot()
    def on_btnOpen_clicked(self):
        if not self.ser.is_open:
            try:
                self.ser.timeout = 1
                self.ser.xonxoff = 0
                self.ser.port = self.cmbCOMM.currentText()
                self.ser.parity = self.cmbChek.currentText()[0]
                self.ser.baudrate = int(self.cmbBaud.currentText())
                self.ser.bytesize = int(self.cmbData.currentText())
                self.ser.stopbits = int(self.cmbStop.currentText())
                self.ser.open()
            except Exception as e:
                print e
            else:                
                self.cmbCOMM.setEnabled(False)
                self.btnOpen.setText(u'关闭串口')
                self.lblStat.setPixmap(QtGui.QPixmap("./Image/inopening.png"))
        else:
            self.ser.close()

            self.cmbCOMM.setEnabled(True)
            self.btnOpen.setText(u'打开串口')
            self.lblStat.setPixmap(QtGui.QPixmap("./Image/inclosing.png"))
    
    @QtCore.pyqtSlot()
    def on_btnSend_clicked(self):
        if self.ser.is_open:
            text = self.cmbSend.currentText()
            if self.chkHEXSend.isChecked():
                bytes = ' '.join([chr(int(x,16)) for x in text.split()])
            else:
                bytes = text.encode('gbk') + ('\n' if self.chkSendLF.isChecked() else '')
            
            self.ser.write(bytes)

            if self.cmbSend.itemText(0) != text:
                self.cmbSend.insertItem(0, text)
                self.cmbSend.setCurrentIndex(0)
    
    def on_tmrSer_timeout(self):        
        if self.ser.is_open:
            num = self.ser.in_waiting
            if num > 0:
                bytes = self.ser.read(num)
                
                if self.mode == u'文本':
                    if self.chkHEXShow.isChecked():
                        text = ' '.join('%02X' %ord(c) for c in bytes) + ' '
                    else:
                        text = ''
                        self.buffer += bytes
                        while len(self.buffer) > 1:
                            if ord(self.buffer[0]) < 0x7F:
                                text += self.buffer[0]
                                self.buffer = self.buffer[1:]
                            else:
                                try:
                                    hanzi = self.buffer[:2].decode('gbk')
                                except Exception as e:
                                    text += '\\x%02X' %ord(self.buffer[0])
                                    self.buffer = self.buffer[1:]
                                else:
                                    text += hanzi
                                    self.buffer = self.buffer[2:]

                        if len(self.buffer) > 0:
                            if ord(self.buffer[0]) < 0x7F:
                                text += self.buffer[0]
                                self.buffer = self.buffer[1:]
                    
                    if len(self.txtMain.toPlainText()) > 25000: self.txtMain.clear()
                    self.txtMain.moveCursor(QtGui.QTextCursor.End)
                    self.txtMain.insertPlainText(text)
                else:
                    self.PlotBuff += bytes
                    if self.PlotBuff.rfind(',') == -1: return
                    try:
                        d = [int(x) for x in self.PlotBuff[0:self.PlotBuff.rfind(',')].split(',')]
                        for x in d:
                            self.PlotData.pop(0)
                            self.PlotData.append(x)        
                    except:
                        self.PlotBuff = ''
                    else:
                        self.PlotBuff = self.PlotBuff[self.PlotBuff.rfind(',')+1:]
                    
                    self.PlotCurve.setData(range(1, len(self.PlotData)+1), self.PlotData)
                    self.qwtPlot.replot()
    
    @QtCore.pyqtSlot(str)
    def on_cmbMode_currentIndexChanged(self, text):
        self.mode = text
        self.txtMain.setVisible(self.mode == u'文本')
        self.qwtPlot.setVisible(self.mode == u'波形')
    
    @QtCore.pyqtSlot(str)
    def on_cmbBaud_currentIndexChanged(self, text):
        self.ser.baudrate = int(text)
    
    @QtCore.pyqtSlot(str)
    def on_cmbData_currentIndexChanged(self, text):
        self.ser.bytesize = int(text)
    
    @QtCore.pyqtSlot(str)
    def on_cmbChek_currentIndexChanged(self, text):
        self.ser.parity = text[0]
    
    @QtCore.pyqtSlot(str)
    def on_cmbStop_currentIndexChanged(self, text):
        self.ser.stopbits = int(text)
    
    @QtCore.pyqtSlot()
    def on_btnClear_clicked(self):
        self.txtMain.clear()
    
    def closeEvent(self, evt):
        self.ser.close()

        self.conf.set('globals', 'serial',   self.cmbCOMM.currentText())
        self.conf.set('globals', 'baudrate', self.cmbBaud.currentText())

        histerys = []
        for i in range(min(10, self.cmbSend.count())):
            histerys.append(self.cmbSend.itemText(i))
        self.conf.set('globals', 'historys', repr(histerys))

        self.conf.write(open('setting.ini', 'w'))


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    ser = SERCOM()
    ser.show()
    app.exec_()