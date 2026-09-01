
from PyQt5.QtWidgets import QWidget,QDialog
from PyQt5 import QtWidgets,QtGui



class LoadingProgress(QDialog):
    def __init__(self,parent=None):
        super(LoadingProgress, self).__init__(parent)
        vbox = QtWidgets.QVBoxLayout(self)
        self.movieLabel = QtWidgets.QLabel()
        self.movie = QtGui.QMovie("icon/loading.gif")
        self.movieLabel.setMovie(self.movie)
        self.movie.start()
        vbox.addWidget(self.movieLabel)
        self.setLayout(vbox)