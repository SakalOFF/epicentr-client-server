import asyncio
import argparse
import json
import mysql.connector


class ClientServerProtocol(asyncio.Protocol):

    def __init__(self):
        self.connect_db()

    def connect_db(self):
        try:
            self.db = mysql.connector.connect(
                host='localhost',
                user='monitor',
                passwd='1234monitor',
                database='epicentr'
            )
        except mysql.connector.errors.DatabaseError:
            raise KeyboardInterrupt
        self.curr = self.db.cursor()

    @staticmethod
    def error():
        return json.dumps({'type': 'error'})

    def get_child_categories(self, category_url):
        if category_url is None:
            self.curr.execute("""select name, url, image_src from categories where parent_url is null""")
            response = self.curr.fetchall()[:-1]
            name = None
        else:
            self.curr.execute("""select children, name from categories where url = %s""", (category_url, ))
            children, name = self.curr.fetchall()[0]
            if children:
                self.curr.execute("""select name, url, image_src from categories where parent_url = %s""",
                                  (category_url, ))
                response = self.curr.fetchall()
            else:
                response = self.get_products(category_url)
        return {"type": "ok", "category": (name, category_url), "result": response}

    def get_products(self, category_url):
        self.curr.execute("select name, url, price, old_price, description, image_src "
                          "from products where category_url = %s", (category_url,))
        return self.curr.fetchall()

    def process_data(self, data):
        if isinstance(data, dict):
            if 'url' in data:
                return json.dumps(self.get_child_categories(data['url']), ensure_ascii=False)
        return self.error()

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        try:
            resp = self.process_data(json.loads(data.decode('utf-8')))
        except json.decoder.JSONDecodeError:
            resp = self.error()
        self.transport.write((str(resp) + '\n\n').encode('utf-8'))


def run_server(host, port):
    loop = asyncio.get_event_loop()
    coro = loop.create_server(
        ClientServerProtocol,
        host, port
    )

    server = loop.run_until_complete(coro)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    # parser.add_argument('--host')
    # parser.add_argument('--port')
    # args = parser.parse_args()
    # run_server(args.host, args.port)
    run_server('localhost', 7777)
