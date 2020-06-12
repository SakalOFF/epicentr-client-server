from functools import partial
from collections import deque
from client import *
import sys
import socket
import select
import json
import tempfile
import requests
import shutil
import os
import webbrowser


class ClientError(Exception):
    pass


class MyStory:

    story = deque()
    capacity = 20

    def append(self, element):
        if len(self.story) >= self.capacity:
            self.story.popleft()
        if len(self.story) == 0 or self.story[-1] != element:
            self.story.append(element)

    def pop_last(self):
        if len(self.story) <= 1:
            return {'url': None}
        self.story.pop()
        return self.story[-1]

    def get_last(self):
        if len(self.story) != 0:
            return self.story[-1]
        return {'url': None}


class Client(QtWidgets.QMainWindow):

    HOST = "localhost"
    PORT = 7777
    main_categories = None
    __socket = None
    current_items = None
    story = MyStory()
    image_dir = tempfile.TemporaryDirectory()

    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        self.ui = Ui_mainWindow()
        self.ui.setupUi(self)
        self.create_connection()
        self.get_catalog()
        self.ui.Catalog.currentIndexChanged.connect(self.combobox_item_clicked_action)
        self.ui.backButton.clicked.connect(self.back)
        self.ui.rightArrow.clicked.connect(self.nex_page)
        self.ui.leftArrow.clicked.connect(self.previous_page)

    def __del__(self):
        os.remove(self.image_dir.name)

    def create_connection(self):
        try:
            self.__socket = socket.create_connection((self.HOST, self.PORT), 4)
        except ConnectionError:
            self.set_error_label()

    def get_pictures(self, elements):
        for element in elements:
            file_url = element[-1]
            file_name = file_url.split('/')[-1]
            r = requests.get(file_url, stream=True)
            if r.status_code == 200:
                r.raw.decode_content = True
                file_path = os.path.join(self.image_dir.name, file_name)
                with open(file_path, "wb") as file:
                    shutil.copyfileobj(r.raw, file)

    def __send(self, struct):
        try:
            self.__socket.send(json.dumps(struct).encode("utf8"))
            answer = b""
            while not answer.endswith(b"\n\n"):
                try:
                    ready = select.select([self.__socket], [], [], 3)
                    if ready[0]:
                        answer += self.__socket.recv(1024)
                    else:
                        raise socket.error
                except socket.error:
                    raise ClientError("Error reading data from socket")
            answer = json.loads(answer.decode().strip())
            if answer['type'] == 'ok' and ('category' in answer):
                return answer
            else:
                raise KeyError
        except (KeyError, ClientError, ConnectionError):
            self.set_error_label()

    def get_catalog(self):
        request = {"url": None}
        if self.__socket:
            answer = self.__send(request)
            if answer:
                self.set_catalog(answer)
        else:
            self.set_error_label()

    def set_catalog(self, catalog):
        self.main_categories = catalog['result']
        for i in range(len(catalog['result'])):
            self.ui.Catalog.addItem(catalog['result'][i][0])
        self.set_elements(catalog)

    def clear_grid(self):
        for i in reversed(range(self.ui.gridLayout.count())):
            item = self.ui.gridLayout.itemAt(i)
            if isinstance(item, QtWidgets.QGridLayout):
                for j in reversed(range(item.count())):
                    item.itemAt(j).widget().setParent(None)
                    item.layout().setParent(None)
            else:
                self.ui.gridLayout.itemAt(i).widget().setParent(None)

    def set_error_label(self):
        self.clear_grid()
        self.ui.ErrorLabel = QtWidgets.QLabel(self.ui.gridLayoutWidget)
        font = QtGui.QFont()
        font.setPointSize(20)
        self.ui.ErrorLabel.setFont(font)
        self.ui.ErrorLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.ui.ErrorLabel.setObjectName("ErrorLabel")
        self.ui.gridLayout.addWidget(self.ui.ErrorLabel, 0, 0, 1, 3)
        self.ui.ErrorLabel.setText("Sorry... Something went wrong :(")
        self.ui.RetryButton = QtWidgets.QPushButton(self.ui.gridLayoutWidget)
        self.ui.RetryButton.setEnabled(True)
        self.ui.RetryButton.setText("")
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("icons8-synchronize-50.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.ui.RetryButton.setIcon(icon)
        self.ui.RetryButton.setIconSize(QtCore.QSize(30, 30))
        self.ui.RetryButton.setObjectName("RetryButton")
        self.ui.gridLayout.addWidget(self.ui.RetryButton, 1, 1, 1, 1)
        self.ui.RetryButton.clicked.connect(self.retry_action)

    def get_category_url(self, name):
        for category in self.main_categories:
            if category[0] == name:
                return category[1]

    def combobox_item_clicked_action(self):
        if self.ui.Catalog.currentIndex() != 0:
            name = self.ui.Catalog.currentText()
            url = None
            if name != 'Каталог':
                url = self.get_category_url(name)
            request = {'url': url}
            answer = self.__send(request)
            if answer:
                self.set_elements(answer)

    def retry_action(self):
        if not self.__socket:
            self.create_connection()
            self.get_catalog()
        else:
            answer = None
            try:
                self.__socket = socket.create_connection((self.HOST, self.PORT), 4)
            except ConnectionError:
                self.set_error_label()
            else:
                answer = self.__send(self.story.get_last())
            if answer:
                self.set_elements(answer)

    def back(self):
        request = self.story.pop_last()
        answer = self.__send(request)
        if answer:
            self.ui.CategoryName.setText(answer['category'][0])
            self.set_elements(answer)

    def set_elements(self, category):
        self.story.append({'url': category['category'][1]})
        self.ui.Catalog.setCurrentIndex(0)
        if not category['category'][0]:
            name = 'Каталог'
        else:
            name = category['category'][0]
        self.ui.CategoryName.setText(name)
        max_pages = len(category['result'])//9 if len(category['result']) % 9 == 0 else len(category['result'])//9 + 1
        self.ui.maxPages.setText(str(max_pages))
        self.current_items = category['result']
        self.set_page(1)

    def set_page(self, number):
        index = (number - 1) * 9
        self.__set_table(self.current_items[index:index + 9])
        self.ui.currentPage.setText(str(number))
        if str(number) == self.ui.maxPages.text() == '1':
            self.ui.rightArrow.setEnabled(False)
            self.ui.leftArrow.setEnabled(False)
        elif str(number) == self.ui.maxPages.text():
            self.ui.rightArrow.setEnabled(False)
            self.ui.leftArrow.setEnabled(True)
        elif str(number) == '1':
            self.ui.leftArrow.setEnabled(False)
            self.ui.rightArrow.setEnabled(True)
        else:
            self.ui.rightArrow.setEnabled(True)
            self.ui.leftArrow.setEnabled(True)

    def nex_page(self):
        self.set_page(int(self.ui.currentPage.text()) + 1)

    def previous_page(self):
        self.set_page(int(self.ui.currentPage.text()) - 1)

    def item_action(self, url):
        request = {"url": url}
        answer = self.__send(request)
        if answer:
            self.set_elements(answer)

    @staticmethod
    def count_rows(name, row_length):
        while True:
            if name[0].isspace() or name[-1].isspace():
                name.strip()
                continue
            break
        if name[0].islower():
            name = name[0].upper() + name[1:]
        multiplier = 1
        if len(name) > row_length:
            counter = 0
            for index in range(len(name)):
                counter += 1
                if counter >= row_length:
                    if name[index] == ' ':
                        name = name[:index] + '\n' + name[index + 1:]
                        counter = 0
                        multiplier += 1
        return name, multiplier

    @staticmethod
    def open_in_browser(url):
        webbrowser.open(url)

    def __set_table(self, elements):
        self.clear_grid()
        self.get_pictures(elements)
        for i in range(3):
            for j in range(3):
                index = i*3 + j
                self.ui.verticalLayout = QtWidgets.QGridLayout()
                self.ui.verticalLayout.setObjectName("verticalLayout")
                self.ui.label = QtWidgets.QLabel(self.ui.gridLayoutWidget)
                self.ui.label.setObjectName("label")
                self.ui.label.setAlignment(QtCore.Qt.AlignCenter)
                if index >= len(elements):
                    pixmap = QtGui.QPixmap()
                    pixmap.fill(QtCore.Qt.white)
                    self.ui.label.setPixmap(pixmap)
                self.ui.verticalLayout.addWidget(self.ui.label, 0, 0, 1, 2)
                if index < len(elements):
                    self.ui.commandLinkButton = QtWidgets.QCommandLinkButton(self.ui.gridLayoutWidget)
                    self.ui.commandLinkButton.setObjectName("commandLinkButton")
                    font = QtGui.QFont()
                    font.setPointSize(12 if len(elements[0]) == 3 else 10)
                    self.ui.commandLinkButton.setFont(font)
                    if len(elements[0]) == 3:
                        self.ui.commandLinkButton.clicked.connect(partial(self.item_action, elements[index][1]))
                        self.ui.verticalLayout.addWidget(self.ui.commandLinkButton, 1, 0, 1, 2)
                    else:
                        self.ui.commandLinkButton.clicked.connect(partial(self.open_in_browser, elements[index][1]))
                        self.ui.label_price = QtWidgets.QLabel(self.ui.gridLayoutWidget)
                        self.ui.label_price.setObjectName("label")
                        self.ui.label_price.setAlignment(QtCore.Qt.AlignCenter)
                        self.ui.label_price.setFont(font)
                        self.ui.label_price.setMaximumHeight(26)
                        if elements[index][3]:
                            self.ui.verticalLayout.addWidget(self.ui.label_price, 1, 0, 1, 1)

                            self.ui.label_old_price = QtWidgets.QLabel(self.ui.gridLayoutWidget)
                            self.ui.label_old_price.setObjectName("label")
                            self.ui.label_old_price.setAlignment(QtCore.Qt.AlignCenter)
                            self.ui.label_old_price.setMaximumHeight(26)
                            self.ui.verticalLayout.addWidget(self.ui.label_old_price, 1, 1, 1, 1)
                        else:
                            self.ui.verticalLayout.addWidget(self.ui.label_price, 1, 0, 1, 2)
                        self.ui.verticalLayout.addWidget(self.ui.commandLinkButton, 2, 0, 1, 2)

                self.ui.gridLayout.addLayout(self.ui.verticalLayout, i, j, 1, 1)
        for i in range(len(elements)):
            pixmap = QtGui.QPixmap()
            flag = pixmap.load(os.path.join(self.image_dir.name, elements[i][-1].split('/')[-1]))
            if not flag:
                pixmap.fill(QtCore.Qt.white)
            multiplier = 4.5 if len(elements[0]) == 3 else 5.5
            new_height = self.height() // multiplier
            new_width = self.width() // multiplier
            pixmap = pixmap.scaled(new_width, new_height, QtCore.Qt.KeepAspectRatio)
            self.ui.gridLayout.itemAt(i).itemAt(0).widget().setPixmap(pixmap)
            self.ui.gridLayout.itemAt(i).itemAt(0).widget().setMinimumHeight(new_height)
            self.ui.gridLayout.itemAt(i).setSpacing(10)
            name = elements[i][0]
            name, multiplier = self.count_rows(name, 25 if len(elements[0]) == 3 else 30)
            if len(elements[0]) == 3:
                self.ui.gridLayout.itemAt(i).itemAt(1).widget().setText(name)
                self.ui.gridLayout.itemAt(i).itemAt(1).widget().setMinimumHeight(multiplier * 26)
            else:
                self.ui.gridLayout.itemAt(i).itemAtPosition(2, 0).widget().setMinimumHeight(multiplier * 26)
                self.ui.gridLayout.itemAt(i).itemAtPosition(2, 0).widget().setText(name)
                price = elements[i][2]
                old_price = elements[i][3]
                font = QtGui.QFont("Calibri", 16)
                if old_price:
                    self.ui.gridLayout.itemAt(i).itemAtPosition(1, 0).widget().setFont(font)
                    font.setStrikeOut(True)
                    self.ui.gridLayout.itemAt(i).itemAtPosition(1, 1).widget().setFont(font)
                    self.ui.gridLayout.itemAt(i).itemAtPosition(1, 1).widget().setText(old_price)
                    self.ui.gridLayout.itemAt(i).itemAtPosition(1, 1).widget().setStyleSheet('color: red')
                self.ui.gridLayout.itemAt(i).itemAtPosition(1, 0).widget().setText(price)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    MyApp = Client()
    MyApp.show()
    sys.exit(app.exec_())
