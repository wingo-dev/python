import os
import re
import csv
import sys
import json
import glob
import colorama
import requests
from config import config
from termcolor import colored
from bs4 import BeautifulSoup


class HEB:
    def __init__(self):
        self.cookies = {}
        self.stores = []
        self.store_ids = []
        self.list_id = None
        self.items_cache = None
        self.item_id_name_dict = None

    def login(self, verify=True):
        if not os.path.exists("cookies.txt"):
            prc("cookies.txt not found", "red")
            quit()

        with open("cookies.txt") as f:
            for cookie in json.loads(f.read()):
                self.cookies[cookie["name"]] = cookie["value"]

        prc("logging in", color="blue", end=": ")
        if verify:
            if self.check_login_status():
                prc("success", "green")
            else:
                prc("failed. copy fresh cookies", "red")
        else:
            prc("success", "green")

    def check_login_status(self):
        headers = {
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36",
            "Sec-Fetch-User": "?1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
        }

        params = {"q": "milk"}

        response = requests.get(
            "https://www.heb.com/search/",
            headers=headers,
            params=params,
            cookies=self.cookies,
        )
        list_ids = re.findall(r'(?<=data-shoppingListId=")(.*?)(?=")', response.text)
        print(self.cookies)
        if len(list_ids) > 0:
            self.list_id = list_ids[0]
            return True
        return False

    def search_stores(self, zip_code="77581"):
        prc(f"searching {zip_code}: ", color="cyan", end="")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://www.heb.com",
            "Referer": "https://www.heb.com/",
            "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        data = {
            "address": zip_code,
            "curbsideOnly": True,
            "radius": 100,
            "nextAvailableTimeslot": True,
            "includeMedical": False,
        }

        try:
            response = requests.post(
                "https://www.heb.com/commerce-api/v1/store/locator/address",
                headers=headers,
                json=data,
                timeout=10,
            )
            stores = response.json()["stores"]
        except:
            stores = []

        new_stores = []
        for store in stores:
            if store["store"]["id"] in self.store_ids:
                continue
            else:
                self.store_ids.append(store["store"]["id"])

            new_stores.append(
                {
                    "id": store["store"]["id"],
                    "name": store["store"]["name"],
                    "address": store["store"]["address1"],
                }
            )

        prc(
            [
                (f"found {len(stores)} stores", "yellow"),
                "|",
                (f"{len(new_stores)} new", "green"),
            ]
        )
        self.stores.extend(new_stores)

    @staticmethod
    def get_zip_codes():
        if not os.path.exists("input/zip-codes.csv"):
            prc("zip-codes.csv not found", "red")
            quit()

        with open("input/zip-codes.csv") as f:
            return f.read().strip().split("\n")

    def save_stores(self):
        with open("cache/stores.json", "w") as f:
            f.write(json.dumps(self.stores, indent=2))

    def load_stores(self):
        if not os.path.exists("cache/stores.json"):
            prc("stores must be searched first", "red")
            quit()

        with open("cache/stores.json") as f:
            self.stores = json.loads(f.read())

    def add_to_list(self, product_name):
        prc(f"{product_name}: ", color="cyan", end="")

        if product_name in self.items_cache:
            if self.items_cache[product_name] is None:
                prc("not found", "red")
            else:
                prc("already in list", "white")
            return

        product_details = self.search_item(product=product_name)
        if not product_details:
            prc("not found", "red")
            self.update_items_cache(
                {
                    "name": product_name,
                    "product_id": None,
                }
            )
            return

        product_id = product_details["product_id"]
        sku_id = product_details["sku_id"]
        quantity = product_details["quantity"]
        headers = {
            "Connection": "keep-alive",
            "Content-Length": "0",
            "Accept": "text/html, */*; q=0.01",
            "Origin": "https://www.heb.com",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36",
            "DNT": "1",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Referer": "https://www.heb.com/search/?q=milk",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
        }

        params = (
            ("productId", product_id),
            ("skuId", sku_id),
            ("listId", self.list_id),
            ("quantity", quantity),
            ("pageType", "pdp"),
        )

        res = requests.post(
            "https://www.heb.com/mylist/includes/addToList.jsp",
            headers=headers,
            params=params,
            cookies=self.cookies,
        )
        if res.status_code == 200:
            prc("added", "green")
        else:
            prc(
                [
                    ("failed to add", "red"),
                    "|",
                    (f"status code {res.status_code}", "yellow"),
                ]
            )

    def search_item(self, product):
        headers = {
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36",
            "Sec-Fetch-User": "?1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
        }

        params = {"q": product}

        response = requests.get(
            "https://www.heb.com/search/",
            headers=headers,
            params=params,
            cookies=self.cookies,
        )
        soup = BeautifulSoup(response.content, "html.parser")

        try:
            javascript = (
                soup.find("ul", {"class": "shoppingListSelector"})
                .find("li")
                .find("a")["onclick"]
            )
            # print(javascript)
            ids = re.findall(r"[0-9]+", javascript)

            product_details = {
                "name": product,
                "sku_id": ids[1],
                "product_id": ids[0],
                "quantity": 1,
            }
            self.update_items_cache(product_details)
            return product_details
        except AttributeError:
            return None

    def update_items_cache(self, product_details):
        self.items_cache[product_details["name"]] = product_details["product_id"]

        with open("cache/items.json", "w") as f:
            f.write(json.dumps(self.items_cache, indent=2))

    def load_items_cache(self):
        if os.path.exists("cache/items.json"):
            with open("cache/items.json") as f:
                self.items_cache = json.loads(f.read())
                self.item_id_name_dict = {v: k for k, v in self.items_cache.items()}
        else:
            self.items_cache = {}

    @staticmethod
    def get_item_names():
        if not os.path.exists("input/items.csv"):
            prc("items.csv not found", "red")
            quit()
        try:
            with open("input/items.csv", encoding="utf-8") as f:
                return f.read().strip().split("\n")
        except UnicodeDecodeError:
            with open("input/items.csv", encoding="cp1252") as f:
                return f.read().strip().split("\n")

    @staticmethod
    def clear_items_cache():
        if os.path.exists("cache/items.json"):
            os.remove("cache/items.json")
        prc("items cache cleared", "green")
        prc("you need to clear the list manually on the website", "yellow")

    def change_store(self, store_id):
        headers = {
            "Connection": "keep-alive",
            "Accept": "application/json, text/plain, */*",
            "DNT": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://www.heb.com",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.heb.com/",
            "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        data = '{"ignoreCartChangeWarnings":false,"pickupStoreId":"%s"}' % store_id

        for x in range(2):
            response = requests.post(
                "https://www.heb.com/commerce-api/v1/cart/fulfillment/pickup",
                headers=headers,
                cookies=self.cookies,
                data=data,
            )
        for k, v in response.cookies.items():
            self.cookies[k] = v

    def get_aisles(self, store_object):
        prc(
            [
                ("getting aisles for:", "blue"),
                (f'{store_object["name"]} ({store_object["id"]})', "cyan"),
            ],
            end="",
        )

        filename = f'{store_object["name"].replace("/", "")}-{store_object["id"]}.csv'
        if not overwrite and os.path.exists(f"aisle_data/{filename}"):
            prc(": already scraped", "yellow")
            return

        headers = {
            "Connection": "keep-alive",
            "Accept": "text/html, */*; q=0.01",
            "DNT": "1",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://www.heb.com",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.heb.com/my-list/shopping-list",
            "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        self.change_store(store_object["id"])

        how_many = 15
        aisles = []
        while True:
            data = {
                "isLoadMore": "true",
                "slectedList": self.list_id,
                "viewAsList": "true",
                "listType": "SHOPPINGLIST",
                "sortOrder": "DEPARTMENT",
                "howMany": how_many,
                "shoppingListBlockClass": "shopping-list",
            }

            response = requests.post(
                "https://www.heb.com/mylist/includes/allListItems.jsp",
                headers=headers,
                cookies=self.cookies,
                data=data,
            )
            soup = BeautifulSoup(response.content, "html.parser")

            if how_many == 15:
                try:
                    list_size = int(soup.find("span", {"id": "listSize"}).text.strip())
                    # print(f'list size: {list_size}')
                except:
                    prc(
                        "something went wrong. copy new cookies and try again...", "red"
                    )
                    quit()
            items = soup.find("ol", {"id": "shopping-list-item-list"}).find_all("li")

            for item in items:
                iid = item.find("a", {"class": "sl-item__name-link"})["href"].split(
                    "/"
                )[-1]
                try:
                    aisle = item.find("p", {"class": "sl-item__location-message"}).text
                except:
                    continue
                if aisle.startswith("Aisle"):
                    aisle = aisle[5:].strip()
                if aisle == "Item not available in store":
                    how_many = list_size + 15
                    continue

                # print(f'{self.item_id_name_dict.get(iid)}: {aisle}')
                aisles.append([self.item_id_name_dict.get(iid), aisle])
            if how_many > list_size:
                break
            else:
                how_many += 15
        with open(f"aisle_data/{filename}", "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            for row in aisles:
                writer.writerow(row)
        prc(f": saved {len(aisles)} items", "green")


class Importer:
    def __init__(self):
        self.session = requests.session()
        self.import_session = requests.session()
        self.files = None
        self.form_body_template = None

    def login(self):
        sys.stdout.write(
            colored("\rlogging in to speedshopperapp dashboard...", "yellow")
        )
        sys.stdout.flush()

        self.session.headers = {
            "Referer": "https://www.speedshopperapp.com/app/admin/login",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.97 Safari/537.36",
        }

        payload = {
            "username": config.import_username,
            "password": config.import_password,
        }

        response = self.session.post(
            "https://www.speedshopperapp.com/app/admin/login", data=payload
        )

        if "<title>Dashboard</title>" in response.text:
            sys.stdout.write(colored("\rlogged in successfully!".ljust(50), "green"))
            sys.stdout.flush()
            print("\r")
            self.import_session.headers = {
                "Host": "www.speedshopperapp.com",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:70.0) Gecko/20100101 Firefox/70.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Content-Type": "multipart/form-data; boundary=---------------------------1267546269709",
                "Origin": "https://www.speedshopperapp.com",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            self.import_session.cookies = self.session.cookies
        else:
            sys.stdout.write(colored("\rfailed to log in!".ljust(50), "red"))
            sys.stdout.flush()
            print("\r")
            quit()

    def get_files(self):
        self.files = glob.glob("aisle_data/*.csv")
        if len(self.files) == 0:
            prc("no csv files found under aisle_data folder", "red")
            quit()
        count = len(self.files)
        prc(f'{count} {"file" if count == 1 else "files"} found', "green")

    def search_store(self, address="", name=""):
        """searches the website for all available stores and saves their details for quick access"""

        data = {
            "draw": "2",
            "columns[0][data]": "0",
            "columns[0][name]": "",
            "columns[0][searchable]": "true",
            "columns[0][orderable]": "true",
            "columns[0][search][value]": "",
            "columns[0][search][regex]": "false",
            "columns[1][data]": "1",
            "columns[1][name]": "",
            "columns[1][searchable]": "true",
            "columns[1][orderable]": "true",
            "columns[1][search][value]": "",
            "columns[1][search][regex]": "false",
            "columns[2][data]": "2",
            "columns[2][name]": "",
            "columns[2][searchable]": "true",
            "columns[2][orderable]": "true",
            "columns[2][search][value]": "",
            "columns[2][search][regex]": "false",
            "columns[3][data]": "3",
            "columns[3][name]": "",
            "columns[3][searchable]": "true",
            "columns[3][orderable]": "true",
            "columns[3][search][value]": "",
            "columns[3][search][regex]": "false",
            "columns[4][data]": "4",
            "columns[4][name]": "",
            "columns[4][searchable]": "true",
            "columns[4][orderable]": "true",
            "columns[4][search][value]": "",
            "columns[4][search][regex]": "false",
            "columns[5][data]": "5",
            "columns[5][name]": "",
            "columns[5][searchable]": "true",
            "columns[5][orderable]": "true",
            "columns[5][search][value]": "",
            "columns[5][search][regex]": "false",
            "columns[6][data]": "6",
            "columns[6][name]": "",
            "columns[6][searchable]": "true",
            "columns[6][orderable]": "true",
            "columns[6][search][value]": "",
            "columns[6][search][regex]": "false",
            "columns[7][data]": "7",
            "columns[7][name]": "",
            "columns[7][searchable]": "true",
            "columns[7][orderable]": "true",
            "columns[7][search][value]": "",
            "columns[7][search][regex]": "false",
            "columns[8][data]": "8",
            "columns[8][name]": "",
            "columns[8][searchable]": "true",
            "columns[8][orderable]": "false",
            "columns[8][search][value]": "",
            "columns[8][search][regex]": "false",
            "order[0][column]": "0",
            "order[0][dir]": "asc",
            "start": "0",
            "length": "50000",
            "search[value]": "",
            "search[regex]": "false",
            "name": name,
            "address": address,
        }

        res = self.session.post(
            "https://www.speedshopperapp.com/app/admin/stores/getstores", data=data
        )

        try:
            data = res.json()["data"][0]
            return re.search(r"[0-9]+", data[4]).group()
        except IndexError:
            return None

    def import_file(self, file_path, filename, store_id):
        """imports a csv file in the website"""
        response = self.import_session.post(
            "https://www.speedshopperapp.com/app/admin/stores/importFile",
            data=self.get_form_body(file_path, filename, store_id),
        )

        if "Imported items successfully" in response.text:
            return True
        return False

    def get_form_body(self, file_path, file_name, store_id):
        if not self.form_body_template:
            if os.path.exists("config/request-body.txt"):
                with open("config/request-body.txt", encoding="utf-8") as f:
                    self.form_body_template = f.read().strip()
            else:
                prc("request-body.txt not found", "red")
                quit()

        with open(file_path, encoding="utf-8-sig") as f:
            data = f.read().strip()

        # remove items with "char" in name
        data = "\n".join(
            [
                line
                for line in data.split("\n")
                if "char" not in line.lower() and "c " not in line.lower()
            ]
        )

        body = self.form_body_template % (config.import_id, file_name, data, store_id)
        # print('-' * 100)
        # print(body)
        # print('-' * 100)
        return body.encode("utf-8")


class Address:
    def __init__(self):
        self.store_addresses = {}
        self.get_store_addresses()

    def get_address(self, store_id):
        return self.store_addresses.get(store_id)

    def get_store_addresses(self):
        if os.path.exists("cache/stores.json"):
            with open("cache/stores.json") as f:
                stores = json.loads(f.read())
                for store in stores:
                    self.store_addresses[store["id"]] = store["address"]
        else:
            prc("stores.json not found in cache folder", "red")
            quit()


def prc(text, color="grey", end="\n", sep=" "):
    if isinstance(text, str):
        print(colored(text, color), end=end)
    elif isinstance(text, list):
        msg_list = []
        for line in text:
            if len(line) == 1 or isinstance(line, str):
                msg_list.append(colored(line, "grey"))
            else:
                msg_list.append(colored(line[0], line[1]))
        msg = sep.join(msg_list)
        print(msg, end=end)


if __name__ == "__main__":
    colorama.init()
    heb = HEB()

    print(colored("choose an option:", "blue", attrs=["bold", "underline"]))
    prc("1. add items", "cyan")
    prc("2. clear items cache", "cyan")
    prc("3. search stores", "cyan")
    prc("4. get aisles", "cyan")
    prc("5. import", "cyan")
    print(colored("option: ", color="blue", attrs=["blink"]), end="")
    option = input()

    if option == "1":
        heb.login()
        heb.load_items_cache()
        item_names = heb.get_item_names()
        for i, item_name in enumerate(item_names):
            prc(f"{i + 1} of {len(item_names)} | ", "yellow", end="")
            heb.add_to_list(item_name)
    elif option == "2":
        heb.clear_items_cache()
    elif option == "3":
        zip_codes = heb.get_zip_codes()
        for zip_code in zip_codes:
            heb.search_stores(zip_code)
        prc(f"total {len(heb.stores)} stores found", "green")
        heb.save_stores()
    elif option == "4":
        prc([("overwrite past data?", "blue"), ("[y/n]: ", "yellow")], end="")
        overwrite = input().lower() == "y"

        heb.login()
        heb.load_stores()
        heb.load_items_cache()
        for store in heb.stores:
            heb.get_aisles(store)
    elif option == "5":
        address = Address()
        importer = Importer()
        importer.login()
        importer.get_files()
        prc("-" * 75, "cyan")
        for file in importer.files:
            filename = file.split("\\")[-1]
            print(colored("filename:", "blue"), colored(filename, "magenta"))
            store_id = filename[:-4].split("-")[-1]
            print(colored("store id:", "blue"), colored(store_id, "magenta"))
            street_address = address.get_address(store_id=store_id)
            print(
                colored("street address:", "blue"), colored(street_address, "magenta")
            )
            site_id = importer.search_store(address=street_address)
            if not site_id:
                prc("store not found on speedshopperapp", "yellow")
                prc("-" * 75, "cyan")
                continue
            prc("import url: ", "blue", end="")
            prc(
                f"https://www.speedshopperapp.com/app/admin/stores/import/{site_id}",
                "magenta",
            )
            success = importer.import_file(file, filename, site_id)
            if success:
                prc("imported successfully", "green")
            else:
                prc("failed to import", "red")
            prc("-" * 75, "cyan")
    else:
        prc("choose a valid option", "red")
